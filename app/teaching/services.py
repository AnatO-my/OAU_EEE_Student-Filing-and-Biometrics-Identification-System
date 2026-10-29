"""Versioned course communication and teaching resources, scoped at every read."""
import hashlib
from pathlib import Path
from urllib.parse import urlparse
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from academics.current_session import current_session_name
from attendance.models import CourseRoster, CourseStaffAssignment
from attendance.services import lock_calendar
from students.models import Student
from .models import (Announcement, MessageVersion, MessageReceipt, Notification,
                     Material, MaterialVersion, TimetableEntry, TimetableRevision)


def active(user):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("An active account is required.")


def staff(user, capability):
    active(user)
    if not user.is_staff or not user.has_perm("teaching." + capability):
        raise PermissionDenied("Authorised teaching staff access is required.")


def course_access(user, offering, capability=None):
    active(user)
    if user.is_staff:
        if capability:
            staff(user, capability)
        if user.is_superuser:
            return True
        if offering.academic_session.name == current_session_name() and CourseStaffAssignment.objects.filter(offering=offering, staff=user, is_active=True).exists():
            return True
    elif not capability and CourseRoster.objects.filter(offering=offering, students__user=user, students__is_active=True).exists():
        return True
    raise PermissionDenied("This course is outside your assigned or enrolled scope.")


def bounded(value, limit, label):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValidationError(f"Supply {label} of at most {limit} characters.")
    return value.strip()


def recipients(user, audience):
    allowed = {"students", "staff", "student_ids", "staff_ids", "level", "offering_ids"}
    if not isinstance(audience, dict) or set(audience) - allowed:
        raise ValidationError("Choose a supported message audience.")
    students = Student.objects.filter(is_active=True, user__is_active=True)
    staff_users = get_user_model().objects.filter(is_active=True, is_staff=True)
    if audience.get("level"):
        students = students.filter(current_level=audience["level"])
        staff_users = staff_users.filter(adviser_assignments__level=audience["level"], adviser_assignments__academic_session=current_session_name(), adviser_assignments__is_active=True)
    if audience.get("offering_ids"):
        from academics.models import CourseOffering
        offerings = list(CourseOffering.objects.select_related("academic_session").filter(pk__in=audience["offering_ids"]))
        if len(offerings) != len(set(audience["offering_ids"])):
            raise ValidationError("Choose existing course offerings.")
        for offering in offerings:
            course_access(user, offering, "publish_message")
        ids = CourseRoster.objects.filter(offering__in=offerings).values_list("students", flat=True)
        students = students.filter(pk__in=ids)
        staff_users = staff_users.filter(coursestaffassignment__offering__in=offerings, coursestaffassignment__is_active=True)
    selected = set()
    if audience.get("students") or audience.get("student_ids"):
        if audience.get("student_ids"):
            found = students.filter(pk__in=audience["student_ids"])
            if found.count() != len(set(audience["student_ids"])):
                raise ValidationError("Some selected student recipients are unavailable or outside the filters.")
            students = found
        selected.update(students.values_list("user_id", flat=True))
    if audience.get("staff") or audience.get("staff_ids"):
        if audience.get("staff_ids"):
            found = staff_users.filter(pk__in=audience["staff_ids"])
            if found.distinct().count() != len(set(audience["staff_ids"])):
                raise ValidationError("Some selected staff recipients are unavailable or outside the filters.")
            staff_users = found
        selected.update(staff_users.values_list("pk", flat=True))
    selected.discard(None)
    if not selected or len(selected) > 10000:
        raise ValidationError("Choose between 1 and 10000 active portal recipients.")
    return selected


@transaction.atomic
def publish(*, user, event_id, subject, body, audience, message=None, expected_version=0, withdrawn=False):
    lock_calendar()
    staff(user, "publish_message")
    subject = bounded(subject, 200, "a subject")
    body = "" if withdrawn else bounded(body, 20000, "a message")
    existing = MessageVersion.objects.filter(event_id=event_id).select_related("message").first()
    if existing:
        if (existing.message.sender_id, existing.subject, existing.body, existing.audience, existing.withdrawn, str(existing.message_id)) != (user.pk, subject, body, audience, withdrawn, str(message.pk) if message else str(existing.message_id)):
            raise ValidationError("This message event ID belongs to another publication.")
        return existing
    if message:
        message = Announcement.objects.select_for_update().get(pk=message.pk)
        if message.sender_id != user.pk:
            raise PermissionDenied("Only the author can revise or withdraw this message.")
        latest = message.versions.order_by("-version").first()
        if latest.version != expected_version:
            raise ValidationError("The message changed. Open the latest version before revising it.")
        if latest.withdrawn:
            raise ValidationError("A withdrawn message cannot be republished; create a new message.")
    elif expected_version != 0 or withdrawn:
        raise ValidationError("Choose an existing message to edit or withdraw.")
    ids = set(MessageReceipt.objects.filter(version__message=message).values_list("recipient_id", flat=True)) if withdrawn else recipients(user, audience)
    if not message:
        message = Announcement.objects.create(sender=user)
    version = MessageVersion.objects.create(message=message, version=expected_version + 1, event_id=event_id,
        subject=subject, body=body, audience=audience, withdrawn=withdrawn, actor=user)
    for account in get_user_model().objects.filter(pk__in=ids, is_active=True):
        receipt = MessageReceipt.objects.create(version=version, recipient=account)
        Notification.objects.create(receipt=receipt, destination=account.email,
            state="pending" if account.email else "skipped")
    return version


def message_visible(user, message):
    active(user)
    return message.sender_id == user.pk or MessageReceipt.objects.filter(version__message=message, recipient=user).exists()


@transaction.atomic
def open_message(*, user, message):
    active(user)
    message = Announcement.objects.select_for_update().get(pk=message.pk)
    if not message_visible(user, message):
        raise PermissionDenied("This message is private to its selected recipients.")
    version = message.versions.order_by("-version").first()
    receipt = version.receipts.filter(recipient=user).first()
    if message.sender_id != user.pk and not receipt:
        raise PermissionDenied("You are not a recipient of the current message version.")
    if receipt and not receipt.read_at:
        receipt.read_at = timezone.now()
        receipt.save(update_fields=["read_at"])
    return version


@transaction.atomic
def save_material(*, user, offering, event_id, title, reason, upload=None, material=None, expected_version=0, withdrawn=False):
    lock_calendar()
    course_access(user, offering, "manage_material")
    title, reason = bounded(title, 200, "a title"), bounded(reason, 1000, "a reason")
    if material:
        material = Material.objects.select_for_update().get(pk=material.pk)
        if material.offering_id != offering.pk:
            raise ValidationError("A material cannot move to another course.")
    data = b""
    filename = ""
    if not withdrawn:
        if not upload or upload.size > 20 * 1024 * 1024:
            raise ValidationError("Choose a material file up to 20 MiB.")
        filename = Path(upload.name.replace("\\", "/")).name[:255]
        extension = Path(filename).suffix.lower()
        if extension not in {".pdf", ".txt", ".csv", ".docx", ".pptx", ".xlsx"}:
            raise ValidationError("Use PDF, plain text, CSV or an Office document.")
        data = upload.read(20 * 1024 * 1024 + 1)
        if not data or len(data) > 20 * 1024 * 1024:
            raise ValidationError("The material is empty or too large.")
        if extension == ".pdf" and not data.startswith(b"%PDF-"):
            raise ValidationError("The material is not a PDF file.")
        if extension in {".docx", ".pptx", ".xlsx"} and not data.startswith(b"PK"):
            raise ValidationError("The material is not an Office document.")
    digest = hashlib.sha256(data).hexdigest() if data else ""
    old = MaterialVersion.objects.filter(event_id=event_id).select_related("material").first()
    if old:
        if (old.material.offering_id, old.actor_id, old.title, old.reason, old.sha256, old.withdrawn) != (offering.pk, user.pk, title, reason, digest, withdrawn) or (material and old.material_id != material.pk):
            raise ValidationError("This material event ID belongs to another upload.")
        return old
    if material:
        latest = material.versions.order_by("-version").first()
        if latest.version != expected_version:
            raise ValidationError("The material changed. Refresh its version before replacing it.")
    elif expected_version or withdrawn:
        raise ValidationError("Choose an existing material to replace or withdraw.")
    else:
        material = Material.objects.create(offering=offering, created_by=user)
    version = MaterialVersion(material=material, version=expected_version + 1, event_id=event_id,
        title=title, filename=filename, sha256=digest, withdrawn=withdrawn, actor=user, reason=reason)
    if data:
        version.file.save(filename, ContentFile(data), save=False)
    version.save()
    return version


def clashes(entry):
    if not entry.active:
        return []
    roster = CourseRoster.objects.filter(offering=entry.offering).first()
    student_ids = set(roster.students.values_list("pk", flat=True)) if roster else set()
    result = []
    for other in TimetableEntry.objects.filter(active=True, starts_at__lt=entry.ends_at, ends_at__gt=entry.starts_at).exclude(pk=entry.pk):
        if CourseRoster.objects.filter(offering=other.offering, students__in=student_ids).exists():
            result.append(other.pk)
    return result


@transaction.atomic
def save_timetable(*, user, offering, event_id, title, venue, starts_at, ends_at, active, reason, entry=None, expected_revision=0):
    lock_calendar()
    course_access(user, offering, "manage_timetable")
    title, venue, reason = bounded(title, 200, "a title"), bounded(venue, 200, "a venue"), bounded(reason, 1000, "a reason")
    if ends_at <= starts_at:
        raise ValidationError("The end time must follow the start time.")
    if not CourseRoster.objects.filter(offering=offering).exists():
        raise ValidationError("Confirm the course roster before checking student timetable overlaps.")
    snapshot = {"offering": offering.pk, "title": title, "venue": venue,
        "starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat(), "active": active}
    previous = TimetableRevision.objects.select_related("entry").filter(event_id=event_id).first()
    if previous:
        if previous.actor_id != user.pk or previous.snapshot != snapshot or previous.reason != reason or (entry and previous.entry_id != entry.pk):
            raise ValidationError("This timetable event ID belongs to another change.")
        return previous.entry
    if entry:
        entry = TimetableEntry.objects.select_for_update().get(pk=entry.pk)
        if entry.offering_id != offering.pk or entry.revisions.count() != expected_revision:
            raise ValidationError("The timetable entry changed or belongs to another course.")
        for field in ("title", "venue", "starts_at", "ends_at", "active"):
            setattr(entry, field, locals()[field])
        entry.save()
    else:
        if expected_revision:
            raise ValidationError("A new timetable entry starts at revision zero.")
        entry = TimetableEntry.objects.create(offering=offering, title=title, venue=venue, starts_at=starts_at, ends_at=ends_at, active=active)
    TimetableRevision.objects.create(entry=entry, event_id=event_id, snapshot=snapshot,
        clash_ids=clashes(entry), actor=user, reason=reason)
    return entry


def send_notification(notification_id):
    # Persist sending BEFORE the external side effect. Unknown outcomes are never
    # automatically resent; exact publish retries cannot create another outbox row.
    with transaction.atomic():
        item = Notification.objects.select_for_update().select_related("receipt__version__message", "receipt__recipient").get(pk=notification_id)
        if item.state != "pending":
            return item.state
        version, account = item.receipt.version, item.receipt.recipient
        latest = version.message.versions.order_by("-version").first()
        if latest.pk != version.pk or not account.is_active or account.email != item.destination:
            item.state = "skipped"
            item.save(update_fields=["state"])
            return item.state
        origin = getattr(settings, "TEACHING_PORTAL_URL", "http://localhost:5173/portal")
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValidationError("Configure a valid teaching portal URL before sending notifications.")
        if not version.withdrawn:
            try:
                publisher = get_user_model().objects.get(pk=version.actor_id)
                staff(publisher, "publish_message")
                still_selected = account.pk in recipients(publisher, version.audience)
            except (PermissionDenied, ValidationError):
                still_selected = False
            if not still_selected:
                item.state = "skipped"
                item.save(update_fields=["state"])
                return item.state
        item.state, item.attempted_at = "sending", timezone.now()
        item.save(update_fields=["state", "attempted_at"])
        destination, receipt_id = item.destination, item.receipt_id
        message_id = str(version.message_id)
        withdrawn = version.withdrawn
    try:
        sent = EmailMessage("Department message withdrawn" if withdrawn else "New department message",
            f"{'A department message was withdrawn.' if withdrawn else 'A department message is available.'}\nOpen the website: {origin.rstrip('/')}?section=messages&message={message_id}\nSign in to read it.",
            settings.DEFAULT_FROM_EMAIL, [destination], headers={"Message-ID": f"<teaching-{receipt_id}@department.invalid>"}).send(fail_silently=False)
        if sent != 1:
            raise RuntimeError("Email backend did not confirm one accepted notification.")
    except Exception:
        Notification.objects.filter(pk=notification_id, state="sending").update(state="unknown")
        return "unknown"
    Notification.objects.filter(pk=notification_id, state="sending").update(state="sent", sent_at=timezone.now())
    return "sent"
