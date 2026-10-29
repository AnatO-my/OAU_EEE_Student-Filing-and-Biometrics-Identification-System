"""Bounded private database storage for synthetic demo files, without a paid add-on.

Files remain behind existing authorized download views. There are no public URLs
or filesystem paths, and no persistent files are written to a function's /tmp.
"""
from pathlib import PurePosixPath
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.db import transaction


class DemoDatabaseStorage(Storage):
    @staticmethod
    def _validate_name(name):
        if not name or "\\" in name or "\x00" in name or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
            raise SuspiciousFileOperation("Invalid private file name.")

    def get_available_name(self, name, max_length=None):
        self._validate_name(name)
        key = f"demo-files/{uuid4().hex}{PurePosixPath(name).suffix[:10]}"
        if max_length is not None and len(key) > max_length:
            raise SuspiciousFileOperation("Private file name exceeds the field limit.")
        return key

    def _open(self, name, mode="rb"):
        if mode not in {"r", "rb"}:
            raise ValueError("Private demo files are immutable.")
        self._validate_name(name)
        from .models import StoredFile
        try:
            record = StoredFile.objects.get(pk=name)
        except StoredFile.DoesNotExist:
            raise FileNotFoundError(name) from None
        return ContentFile(bytes(record.content), name=name)

    def _save(self, name, content):
        self._validate_name(name)
        limit = settings.DEMO_FILE_MAX_BYTES
        data = content.read(limit + 1)
        if not data or len(data) > limit:
            raise ValidationError("Demo uploads must be nonempty and no larger than 3 MiB.")
        from .models import StorageBudget, StoredFile
        with transaction.atomic():
            budget, _ = StorageBudget.objects.get_or_create(pk=1)
            budget = StorageBudget.objects.select_for_update().get(pk=budget.pk)
            if budget.used_bytes + len(data) > settings.DEMO_STORAGE_MAX_BYTES:
                raise ValidationError("The demo's private file storage is full.")
            # A caller-supplied name never overwrites an existing document.
            StoredFile.objects.create(name=name, content=data, size=len(data))
            budget.used_bytes += len(data)
            budget.save(update_fields=["used_bytes"])
        return name

    def exists(self, name):
        self._validate_name(name)
        from .models import StoredFile
        return StoredFile.objects.filter(pk=name).exists()

    def size(self, name):
        self._validate_name(name)
        from .models import StoredFile
        try:
            return StoredFile.objects.values_list("size", flat=True).get(pk=name)
        except StoredFile.DoesNotExist:
            raise FileNotFoundError(name) from None

    def delete(self, name):
        self._validate_name(name)
        from .models import StorageBudget, StoredFile
        with transaction.atomic():
            budget, _ = StorageBudget.objects.get_or_create(pk=1)
            budget = StorageBudget.objects.select_for_update().get(pk=budget.pk)
            record = StoredFile.objects.filter(pk=name).first()
            if record is not None:
                budget.used_bytes = max(0, budget.used_bytes - record.size)
                record.delete()
                budget.save(update_fields=["used_bytes"])
