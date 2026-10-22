# OAU EEE software: a practical developer handbook

**Audience:** high-school learners, beginner programmers, intermediate contributors and project coordinators.  
**Purpose:** explain what to write, where to put it, how the tools cooperate, and how several people can build the system without guessing each other's names or rules.  
**Basis:** `oau-software-architecture-walkthrough.pdf`, supplied project walkthrough, 92 pages.  
**Status:** educational implementation guide for a proposed architecture, not a report of completed software. Examples use fictional data.  
**Prepared:** 2 October 2026.

## Contents

1. [How to use this handbook](#1-how-to-use-this-handbook)
2. [The whole system in ordinary language](#2-the-whole-system-in-ordinary-language)
3. [What each tool does](#3-what-each-tool-does)
4. [Names, types and shared meanings](#4-names-types-and-shared-meanings)
5. [Creating and using a database](#5-creating-and-using-a-database)
6. [The files inside a Django module](#6-the-files-inside-a-django-module)
7. [A connected student feature](#7-a-connected-student-feature)
8. [Accounts and access](#8-accounts-and-access)
9. [Students and relationships](#9-students-and-relationships)
10. [Academics and historical meaning](#10-academics-and-historical-meaning)
11. [Imports, duplicates and review](#11-imports-duplicates-and-review)
12. [Reporting and protected files](#12-reporting-and-protected-files)
13. [Identity, contracts and simulators](#13-identity-contracts-and-simulators)
14. [Audit and accountability](#14-audit-and-accountability)
15. [HTML, CSS, JavaScript and HTMX](#15-html-css-javascript-and-htmx)
16. [Testing and debugging](#16-testing-and-debugging)
17. [Parallel work and communication](#17-parallel-work-and-communication)
18. [Configuration, packaging and deployment](#18-configuration-packaging-and-deployment)
19. [A practical build progression](#19-a-practical-build-progression)
20. [Task cards people can pick up](#20-task-cards-people-can-pick-up)
21. [Syntax and semantics reference](#21-syntax-and-semantics-reference)
22. [Decisions and reference material](#22-decisions-and-reference-material)

## 1. How to use this handbook

Do not learn the whole document before contributing. Choose one work card, read the relevant section, explain its input and output in ordinary language, and attempt the smallest example.

For each assignment, follow this sequence:

1. State the behaviour: “a blank student name is refused.”
2. Write examples: a normal name, spaces only, and the wrong input type.
3. Agree names, types, permissions and failure meanings.
4. Write pseudocode: instructions in ordinary language.
5. Implement the smallest behaviour.
6. Check it with tests.
7. Connect it to its caller.
8. Ask a reviewer to inspect the behaviour and boundaries.

### Example labels

- **Connected teaching example:** code in Section 7 that shares the same field and function names. It needs a configured Django project, installed apps and database migrations before running.
- **Standalone exercise:** ordinary Python that can run without Django.
- **Illustrative fragment:** explains one idea; surrounding models, imports or policies must be supplied before it can become a working feature.
- **Proposed interface:** an agreement to discuss, not an approved implementation or device protocol.

A code block without the full application around it is not a ready-made production system. The aim is to make its missing pieces explicit rather than hide them.

## 2. The whole system in ordinary language

Imagine a departmental office. The browser is the counter where staff submit requests. Django is the staff following the rules. PostgreSQL is the structured records room. Protected file storage holds received spreadsheets and generated reports. Audit is the accountable record of important actions.

The proposed software is a **modular monolith**: several responsibility areas delivered as one application. Hardware and firmware are separate projects connected through an identity API.

| Part | Owns | Example request |
|---|---|---|
| `accounts/` | Staff identity, roles and access rules | “May this staff member change a profile?” |
| `students/` | Stable student identity, profiles, contacts and guardian links | “Which student does this external identifier refer to?” |
| `academics/` | Curriculum versions, periods, offerings, attempts and results | “What is this student's result for this particular attempt?” |
| `imports/` | Incoming files, staging, validation and review | “Which rows can be accepted, and which conflict?” |
| `reporting/` | Authorised reports and export jobs | “Produce these permitted semester records.” |
| `identity/` | Device messages and credential-to-student resolution | “Does this active device's matched credential resolve?” |
| `audit/` | Trace of important actions | “Who accepted this correction, and why?” |

The browser and terminal do not receive PostgreSQL credentials. The server mediates their requests. Matching a fingerprint identifies a student only after appropriate evidence and mapping checks; it does not give staff permission to edit academic records.

The walkthrough's first demonstration should connect one fictional student, one offering and one registration, with a permitted operation, a refused operation, a safe repeated import and an audit record. A mock identity exchange can proceed separately.

## 3. What each tool does

| Tool or concept | What it is | Project job | First useful exercise |
|---|---|---|---|
| Python | Programming language | Rules, imports, services, queries and tests | Validate one incoming dictionary |
| Django | Python web framework | Models, forms, request handling, accounts and migrations | Create and retrieve one fictional student |
| ORM | Django's object-relational mapping | Translate model operations into database queries | Read `Student.objects.get(...)` |
| PostgreSQL | Database server | Store related facts and enforce constraints | Connect to a local fictional-data database |
| SQL | Database query language | Inspect stored facts, joins and constraints | Select a student by stable ID |
| Psycopg | PostgreSQL driver for Python | Carry Django's database operations to PostgreSQL | Recognise its dependency in setup |
| HTML | Document markup | Labels, forms, tables and page structure | Label a student-name input |
| Django templates | Server-rendered presentation language | Insert permitted values into HTML | Render a student's name |
| CSS | Styling language | Layout, appearance and responsive presentation | Style an error message |
| Bootstrap | Optional styling/component toolkit | Reusable form and table appearance | Apply an agreed form style |
| JavaScript | Browser programming language | Small interactive behaviour | Display a form character count |
| HTMX | Optional browser library | Request HTML fragments and replace part of a page | Refresh a permitted student list |
| HTTP / HTTPS | Request-response protocol / protected transport | Browser and device communication | Explain GET versus POST |
| JSON | Structured text interchange format | Device messages and structured API responses | Read a fictional no-match message |
| Django REST Framework | API toolkit for Django | Message parsing, serializers and API handlers | Validate a fictional message shape |
| Git | Local version history | Branches, commits and merging | Commit one small change |
| GitHub | Shared repository/review service | Pull requests, tasks and automated checks | Review a proposed field change |
| VS Code or another editor | Code workbench | Editing, navigation and debugging | Break at a failing validation line |
| Django test runner | Test execution tool | Run model, service and access tests | Run a single module's tests |
| `psql` | PostgreSQL command-line client | Inspect a development database | Show tables and execute a read query |
| Database GUI | Optional database inspection tool | Visualise tables and relationships | Inspect synthetic data |
| Python `csv` | Standard-library file tool | Read and write CSV rows | Read three fictional import rows |
| XLSX library | Later dependency, chosen by the team | Read Excel workbooks | Preserve text identifiers and blank scores |
| Private file store | Protected persistent storage | Import files and generated reports | Store a file reference in a batch record |
| Queue and worker | Optional deferred-job machinery | Process long imports or exports | Explain request, job and completion |
| Celery and Redis-compatible broker | One proposed worker arrangement | Schedule and deliver deferred jobs | Simulate a retry without duplicated acceptance |
| Linux and hosting server | Runtime environment | Run the application and services | Follow startup and health-check instructions |

The source proposes Django 5.2 as its documentation baseline. This handbook uses 5.2 documentation for examples; it does not select the final dependency versions or claim that a version audit has been completed. Pin and review compatible versions at implementation.

## 4. Names, types and shared meanings

### 4.1 A variable name is a local label; a contract field is a shared promise

```python
student_name = "Ada Example"
```

`student_name` is a Python name pointing to a value. Another function can use `display_name` internally without breaking this function.

But if an agreed JSON message contains `student_id`, changing that key to `student_number` changes the interface. A model field, public function parameter, CSV canonical column or API field can have callers elsewhere.

Agree **shared interfaces**, not every temporary variable.

### 4.2 Start with meaning, then choose a type

| Proposed field | Meaning | Python representation | Django field | Typical PostgreSQL type | Wire/file representation |
|---|---|---|---|---|---|
| `student_id` | Stable internal student reference | `UUID` | `UUIDField` | `uuid` | UUID string |
| `identifier_value` | External identifier such as matriculation number | `str` | `CharField` | `varchar` | Text, preserve leading zeros |
| `full_name` | Profile display name | `str` | `CharField` | `varchar` | Text |
| `phone_number` | Contact text, including prefixes | `str` | `CharField` | `varchar` | Text; never integer arithmetic |
| `admission_year` | Recorded year, not inferred current level | `int` | `PositiveSmallIntegerField` | Small integer with relevant constraints | Integer |
| `score` | Recorded numeric score | `Decimal` | `DecimalField` | `numeric` | Prefer agreed decimal string |
| `is_active` | Binary operational state where appropriate | `bool` | `BooleanField` | `boolean` | `true` / `false` |
| `occurred_at` | Time an event occurred | Aware `datetime` | `DateTimeField` | Timestamp with time zone | ISO 8601 timestamp |
| `period_id` | Reference to an academic period | Related object's key | `ForeignKey` | Referenced key type | Agreed key string/integer |
| `diagnostic_code` | Controlled outcome explanation | `str` or enumeration | `CharField` with reviewed values | `varchar` | Stable code, not free-form exception text |

This is a teaching proposal. Agree exact names, lengths, ranges and representations before publishing them as project contracts.

A phone number looks numeric but is an identifier. `"08001234567"` preserves its first zero; an integer would not.

A name is not a unique identifier: two students can have the same name.

### 4.3 Use one stable student key in the connected examples

This handbook uses:

```python
student_id = models.UUIDField(
    primary_key=True,
    default=uuid.uuid4,
    editable=False,
)
```

Here `student_id` is the primary key itself. Therefore `student.pk` and `student.student_id` refer to the same key.

This differs from a design with an automatic integer `id` plus a separate unique `student_id`. Either can be designed deliberately; do not mix the two conventions accidentally. UUIDs do not provide authorisation or guarantee that a request is permitted.

External identifiers belong in separate records so corrections do not change the student's stable identity.

### 4.4 Data dictionary entry people can agree

Store something like this in `docs/data-dictionary.md`:

```markdown
### student_id
- Owner: students module
- Meaning: stable internal student identity
- Python type: uuid.UUID
- Database type: uuid, primary key
- JSON form: UUID string
- Created by: server
- Changes allowed: no routine reassignment
- External matriculation number: stored separately
- Consumers: academics, identity, reporting, audit references
- Decision status: proposed; requires data reviewer agreement
```

Every shared field needs meaning, owner, type, missing-value rules, validation, change rules and consumers. The dictionary explains meaning; actual models and executable contracts must agree with it.

### 4.5 Missing is different from zero

- `None`: Python's absence value.
- `null`: JSON's absence value.
- SQL `NULL`: database absence/unknown value.
- `""`: empty text.
- `0`: actual numeric zero.
- `"unknown"`: a meaningful state only if the team defines it.

A missing score must not silently become zero. An unknown result is not proof of a failed course.

`blank=True` concerns validation accepting an empty field. `null=True` concerns database storage of `NULL`. For optional text, a single empty-string convention is often clearer than permitting both empty string and NULL. For an optional numeric value, NULL may express absence. Record the chosen convention.

### 4.6 Python type hints describe intent, not automatic enforcement

```python
def normalise_name(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("full_name must be text")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("full_name is required")
    return cleaned
```

`value: str` and `-> str` help readers and checking tools. The `isinstance` check actually rejects a wrong runtime type. The function trims outer whitespace; it does not guess name order, remove accents or merge internal spaces.

### 4.7 Naming conventions

| Kind | Convention | Example |
|---|---|---|
| Python variable/function | `snake_case` | `create_student` |
| Python class | `PascalCase` | `StudentProfile` |
| Constant | `UPPER_SNAKE_CASE` | `MAX_UPLOAD_BYTES` |
| Python module | Lowercase descriptive name | `resolution.py` |
| JSON fields in this proposal | Agreed `snake_case` | `credential_ref` |
| Boolean name | Clearly state the question | `is_active`, `can_export` |
| Relationship field | Entity name | `student` |
| Generated foreign-key attribute | Entity plus `_id` | `student_id` |

Django's `profile.student` gives the related object. `profile.student_id` gives its stored key. With our UUID student key, that foreign-key value is a UUID.

## 5. Creating and using a database

### 5.1 Five different things beginners often combine

| Thing | Meaning |
|---|---|
| PostgreSQL installation/service | The database server program running somewhere |
| Database | A named container inside that server, such as `eee_dev` |
| Schema | A namespace inside a database, commonly `public` |
| Table | A collection of one type of record |
| Row | One stored record |

Provisioning creates the server/database/user. Django migrations create and evolve application tables. Python services create individual rows.

### 5.2 Example local provisioning

**Development illustration:** PostgreSQL must already be running, and an authorised local administrator must execute these. Installation/authentication steps differ by operating system.

Inside `psql`, connected to an administrative database:

```sql
CREATE ROLE eee_dev_user LOGIN;
```

Then use the `psql` command below to enter a local password interactively:

```text
\password eee_dev_user
```

Then SQL:

```sql
CREATE DATABASE eee_dev OWNER eee_dev_user;
```

This creates a database, not the student tables. Development testing may require a role permitted to create the separate test database, or a pre-provisioned test database arrangement. Do not grant production credentials extra privileges merely to make local tests easier.

### 5.3 Tell Django where PostgreSQL is

**Configuration fragment:** included in an otherwise complete settings module.

```python
import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}
```

`os.environ["DB_NAME"]` reads configuration supplied to the process. It fails visibly if required configuration is missing. A `.env` file is not automatically loaded by Python or Django; the launch process or an explicitly selected loader must load it.

### 5.4 Define models, generate instructions, apply them

From `software/app/`, after the app is configured:

```bash
python manage.py makemigrations students
python manage.py sqlmigrate students 0001
python manage.py migrate
python manage.py showmigrations
```

`makemigrations` creates Python migration files. `sqlmigrate` displays the SQL for an existing migration; it does not apply it. `migrate` changes the connected database. `showmigrations` displays recorded application status.

Review generated migrations. Adding required fields to existing data, changing identifiers or removing columns can require a staged change and a data migration. Never resolve a shared migration problem simply by deleting applied migration files.

### 5.5 Django and SQL express related operations

```python
student = Student.objects.get(student_id=some_uuid)
```

Conceptual SQL equivalent:

```sql
SELECT * FROM students_student WHERE student_id = $1;
```

The database driver supplies `$1` as a bound parameter. Do not concatenate untrusted values into SQL strings.

A foreign key connects records. A uniqueness constraint forbids a defined duplicate. An index helps selected lookups. A transaction groups operations so they commit together or roll back together.

Two developers' local databases are separate. Git shares model and migration instructions, not their running records. Each developer applies the same reviewed migrations to their own fictional-data database.

## 6. The files inside a Django module

The walkthrough's structure is a convention, not a demand for empty files.

| File | What goes here | What should stay elsewhere |
|---|---|---|
| `models.py` | Entities, relationships, constraints | HTTP request parsing |
| `migrations/*.py` | Reviewed database-structure/data changes | Untracked manual live-table edits |
| `services.py` | Important operations and business rules | HTML layout |
| `queries.py` | Reusable permission-aware record selection | Mutation hidden inside a list lookup |
| `forms.py` | Human-input conversion and validation | Sole enforcement of permissions |
| `views.py` | Coordinate request, permission, input, service and response | A second copy of academic rules |
| `urls.py` | Addresses mapped to handlers | Database querying |
| `api/serializers.py` | Structured message fields and shape validation | Assuming a valid shape proves identity |
| `api/views.py` | API request/response coordination | Unrestricted academic export |
| `tests/test_models.py` | Relationships and constraints | Assertions that merely repeat every line |
| `tests/test_services.py` | Operations, failures and state changes | Live departmental data |
| `tests/test_access.py` | Allowed/refused callers and scope | Relying only on hidden buttons |

Additional conventional Django files may include `apps.py`, `admin.py` and `__init__.py`. `apps.py` identifies the app configuration. `admin.py` configures administrative editing if permitted; the admin is not automatically the departmental product interface. `__init__.py` identifies ordinary Python packages and may be empty.

Choose either `services.py` or a `services/` package for the same module name. Do not create both. The identity module already proposes a package because its operations divide naturally into requests, outcomes and resolution.

## 7. A connected student feature

### 7.1 Agree the behaviour first

**Teaching contract:** an authenticated staff member with Django's `students.add_student` permission may create a fictional student and profile. Blank names are refused. The stable ID is server-generated. The creation and audit event commit together.

This example uses a simple global permission. It is not a complete multi-programme record-scoping policy. The final system must implement the reviewed scopes.

### 7.2 `students/models.py`: describe records

```python
import uuid
from django.db import models


class Student(models.Model):
    student_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class StudentProfile(models.Model):
    student = models.OneToOneField(
        Student, on_delete=models.PROTECT, related_name="profile"
    )
    full_name = models.CharField(max_length=200)
```

`uuid.uuid4` without parentheses supplies a function Django can call for each new student. `uuid.uuid4()` would calculate a value immediately instead of supplying the generator.

`OneToOneField` allows at most one profile linked to a student. It does not by itself require every student to have a profile; the creation service supplies both. `PROTECT` refuses deletion that would break protected relationships. Retention/deactivation rules still need agreement.

### 7.3 `audit/models.py`: a minimal accountable event

```python
import uuid
from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=100)
    reason = models.TextField()
    correlation_id = models.UUIDField(default=uuid.uuid4)
    occurred_at = models.DateTimeField(auto_now_add=True)
```

A generic `target_id` is text because different target types may use different keys. This convenience is not a database-enforced foreign key to every target. The audit design must specify target validity, access and retention.

### 7.4 `students/services.py`: perform the operation

```python
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from audit.models import AuditEvent
from .models import Student, StudentProfile


def create_student(*, actor, full_name, reason="Initial registration"):
    if not actor.is_authenticated or not actor.has_perm("students.add_student"):
        raise PermissionDenied("Student creation is not permitted")

    if not isinstance(full_name, str):
        raise ValidationError({"full_name": "Name must be text"})
    cleaned_name = full_name.strip()
    if not cleaned_name or len(cleaned_name) > 200:
        raise ValidationError({"full_name": "Enter a name of 1 to 200 characters"})
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError({"reason": "A reason is required"})

    with transaction.atomic():
        student = Student.objects.create()
        profile = StudentProfile(student=student, full_name=cleaned_name)
        profile.full_clean()
        profile.save()
        AuditEvent.objects.create(
            actor=actor,
            action="student.created",
            target_type="student",
            target_id=str(student.student_id),
            reason=reason.strip(),
        )
    return student
```

The bare `*` makes subsequent arguments keyword-only. Calling `create_student(actor=staff, full_name="Ada Example")` is clearer than relying on argument positions.

`transaction.atomic()` groups the three writes. If the audit insert fails, the student/profile writes roll back. The permission check is inside the service so a caller cannot bypass it merely by skipping the browser view.

`full_clean()` validates the model instance. `save()` and `objects.create()` do not automatically perform every model validation. Database constraints still matter, especially when requests run concurrently.

### 7.5 `students/forms.py`: receive human input

```python
from django import forms


class StudentCreateForm(forms.Form):
    full_name = forms.CharField(max_length=200, label="Student name")
```

The form produces `cleaned_data`. It does not create a student by itself. The service also validates because imports or future API callers may not use this form.

### 7.6 `students/queries.py`: authorised lookup

```python
from django.core.exceptions import PermissionDenied
from .models import Student


def get_student_for_staff(*, actor, student_id):
    if not actor.is_authenticated or not actor.has_perm("students.view_student"):
        raise PermissionDenied("Student viewing is not permitted")
    return Student.objects.select_related("profile").get(student_id=student_id)
```

`select_related` retrieves the linked profile efficiently. `.get()` returns one object or raises `Student.DoesNotExist` when missing. A real scoped implementation filters to the caller's permitted population before retrieving.

### 7.7 `students/views.py`: connect request and operation

```python
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from .forms import StudentCreateForm
from .models import Student
from .queries import get_student_for_staff
from .services import create_student


@login_required
@permission_required("students.add_student", raise_exception=True)
@require_http_methods(["GET", "POST"])
def student_create(request):
    form = StudentCreateForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            student = create_student(actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("students:detail", student_id=student.student_id)
    return render(request, "students/create.html", {"form": form})


@login_required
@permission_required("students.view_student", raise_exception=True)
def student_detail(request, student_id):
    try:
        student = get_student_for_staff(actor=request.user, student_id=student_id)
    except Student.DoesNotExist as exc:
        raise Http404("Student not found") from exc
    return render(request, "students/detail.html", {"student": student})
```

`**form.cleaned_data` expands named values into keyword arguments. It works because the form field `full_name` matches the service parameter. An unreviewed added field could break this call; explicit argument mapping is preferable as forms grow.

The redirect assumes the caller also has viewing permission. Otherwise creation can succeed but the detail page is refused. Decide the intended post-creation destination and role combination.

### 7.8 `students/urls.py` and `config/urls.py`: connect addresses

```python
# students/urls.py
from django.urls import path
from . import views

app_name = "students"
urlpatterns = [
    path("new/", views.student_create, name="create"),
    path("<uuid:student_id>/", views.student_detail, name="detail"),
]
```

```python
# Relevant additions in config/urls.py
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("students/", include("students.urls")),
]
```

The UUID converter rejects an invalid URL shape and passes a UUID value to the view. It does not establish permission or prove that the student exists. Include the project's other routes rather than replacing them blindly.

### 7.9 Templates

```html
<!-- app/templates/base.html -->
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{% block title %}EEE records{% endblock %}</title></head>
<body><main>{% block content %}{% endblock %}</main></body>
</html>
```

```html
<!-- app/templates/students/create.html -->
{% extends "base.html" %}
{% block content %}
<h1>Register student</h1>
<form method="post">
  {% csrf_token %}
  {{ form.as_p }}
  <button type="submit">Register</button>
</form>
{% endblock %}
```

```html
<!-- app/templates/students/detail.html -->
{% extends "base.html" %}
{% block content %}
<h1>{{ student.profile.full_name }}</h1>
<p>Internal reference: {{ student.student_id }}</p>
{% endblock %}
```

A login template at `templates/registration/login.html` must also render the login form with a CSRF token. Configure template search paths, middleware and authentication settings as part of setup.

### 7.10 What the feature actually demonstrates

One submitted `full_name` travels through HTML form submission, Django form cleaning, a service argument, a profile model field and the database. `student_id` is created on the server, stored as a UUID, used by the URL converter and passed to a restricted query.

The snippet intentionally leaves guardian management, external identifiers, detailed staff scope, deactivation, retention and full audit protections to their own assignments. It is a connected educational starting point, not the entire student module.

## 8. Accounts and access

Use Django's authentication foundations rather than inventing plaintext password storage. Decide early whether a custom user model is required; changing user models after many migrations is substantially harder.

| File | Small piece to write | Input/output or completion condition |
|---|---|---|
| `accounts/models.py` | Custom staff model or staff profile, only if needed | Clarified relationship to Django's user |
| `accounts/services.py` | Assign/revoke an agreed role | Authorised actor, target user, role; trace of change |
| `accounts/queries.py` | Resolve staff's permitted population | User in; permitted scope out |
| `accounts/forms.py` | Staff account/role input | Validated values, no direct privilege escalation |
| `accounts/views.py` | Coordinate authorised role maintenance | Refuse callers without management permission |
| `accounts/urls.py` | Login/account routes | Stable route names agreed with interface team |
| `accounts/tests/test_access.py` | Direct denied operation | Refusal even when browser controls are bypassed |

**Illustrative permission helper:**

```python
def can_export_records(user):
    return user.is_authenticated and user.has_perm("reporting.export_records")
```

`reporting.export_records` is a proposed custom permission. It must be defined and granted through the reviewed model/migration or permission setup; Django does not invent it because a string appears in code.

Authentication asks “who is this caller?” Authorisation asks “may this caller perform this action on these records?” Scope asks “which records and fields are included?” A successful login answers only the first question.

## 9. Students and relationships

The connected model keeps stable identity separate from profile data. Grow it through reviewed relationships.

| Entity | Proposed contents | Why separate it? |
|---|---|---|
| `Student` | Stable ID, active state, creation metadata | Links survive profile corrections |
| `ExternalIdentity` | Student, source system, identifier value, provenance | Matriculation/source IDs can be corrected or coexist |
| `StudentProfile` | Name, contacts and reviewed profile fields | Profile changes are not identity changes |
| `GuardianContact` | Guardian/contact details | Avoid one giant concatenated string |
| `StudentGuardianLink` | Student, guardian, relationship and purpose | A student may have several contacts; a contact may relate to several students |
| Academic history | Programme, cohort, level, status, effective period, source | Previous academic states remain explainable |

**Illustrative `ExternalIdentity` fragment:**

```python
class ExternalIdentity(models.Model):
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT)
    source_system = models.CharField(max_length=80)
    identifier_value = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_system", "identifier_value"],
                name="unique_external_identity_per_source",
            )
        ]
```

This example assumes identifiers are unique within a source. Confirm that assumption. Additional version/active-state history may be needed when identifiers change. Do not automatically merge two students based on an apparent identifier conflict.

Suggested first assignments:

1. Write and review the field dictionary.
2. Implement the identity/profile relationship.
3. Add external identity lookup.
4. Add a guardian and link through a service.
5. Test a missing optional phone/email without inventing one.
6. Model academic history with an academic reviewer; do not derive level from elapsed calendar years.

## 10. Academics and historical meaning

This module has more semantic difficulty than a simple list of scores. A programmer needs an Academic Data Steward to confirm institutional meanings.

| Entity | Small model content | Service/query assignment |
|---|---|---|
| `AcademicPeriod` | Session and semester identifiers | Resolve an explicit period; reject guessing from upload date |
| `Course` | Stable course identity | Locate the underlying course |
| `CourseVersion` | Course, versioned title, units and applicability | Preserve historical values |
| `CurriculumVersion` | Programme/cohort applicability and authority | Select the version applicable to the student |
| `CurriculumRule` | Requirement type, required course/group, rule parameters | Evaluate reviewed compulsory/elective logic |
| `CourseOffering` | Course version and academic period | Resolve the exact taught offering |
| `RegistrationAttempt` | Student, offering, attempt state and source | Distinguish repeated upload from genuine repeat |
| `ResultRevision` | Attempt, score/grade, source state, review state, replaced revision | Append a correction and select valid revisions |
| `Exemption` / `Substitution` | Affected requirement, student and authority | Apply an authorised exception |

### 10.1 Relationship fragment

```python
class RegistrationAttempt(models.Model):
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT)
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.PROTECT)
    source_reference = models.CharField(max_length=100)
```

The sample deliberately does not assert a universal uniqueness rule. If the institution permits only one registration per student per offering, that pair may be unique. If it permits multiple relevant attempt records, the key needs more information. Settle the meaning before constraining the table.

### 10.2 Scores require exact representation and a reviewed range

**Standalone exercise using an explicitly fictional 0–100 range:**

```python
from decimal import Decimal, InvalidOperation


def parse_demo_score(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("score is required")
    try:
        score = Decimal(value.strip())
    except InvalidOperation as exc:
        raise ValueError("score must be numeric") from exc
    if not score.is_finite() or not Decimal("0") <= score <= Decimal("100"):
        raise ValueError("score must be finite and between 0 and 100")
    return score
```

`Decimal` represents decimal values without ordinary binary floating-point approximation. `NaN` and infinity are rejected explicitly. Decide accepted decimal precision rather than silently rounding a source result. The 0–100 range is an exercise assumption, not a confirmed OAU rule.

### 10.3 Proposed important operations

```python
# Signatures to agree before implementation; bodies are not supplied here.
def register_attempt(*, actor, student_id, offering_id, source_reference): ...
def append_result_revision(*, actor, attempt_id, score, source_ref, reason): ...
def explain_outstanding_requirements(*, actor, student_id, period_id): ...
```

The ellipsis marks an unimplemented proposed interface. It must not be shipped as a working function.

An outstanding-requirement explanation must combine the applicable curriculum, historical attempts, selected valid result revisions and authorised exceptions. It should distinguish “requirement unmet” from “information incomplete.” A correction must not overwrite all history. Departmental acceptance and official university approval require distinct meanings.

Tests should include later genuine repeats, a changed course-unit version, revised results, an elective-group rule, a valid substitution and missing evidence.

## 11. Imports, duplicates and review

Incoming data is a claim awaiting checks, not automatically a trusted database update.

| File | Example contents | First assignment |
|---|---|---|
| `imports/models.py` | ImportBatch, StagingRow, provenance/conflict records | Store a fictional batch and row status |
| `imports/adapters.py` | Source-header mappings | Translate `Matric No` into a canonical external identifier field |
| `imports/validation.py` | Row shape/value validation | Return useful row errors |
| `imports/services.py` | Stage, review and accept batch operations | Accept only reviewed rows through academic services |
| `imports/queries.py` | Reviewer-scoped batch and conflict lookups | Show permitted review items |
| `imports/forms.py` | File upload and period input | Validate file selection and explicit period |
| `imports/views.py` / `urls.py` | Upload, preview and acceptance routes | Preview before acceptance |
| `imports/tests/` | Invalid rows, conflicts, repeats and rollback | Accept a file twice without duplicated records |

`adapters.py` and `validation.py` are suggested splits when the module grows; they are not mandatory empty files.

### 11.1 Standalone CSV reader

```python
import csv


def read_demo_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as stream:
        for row_number, row in enumerate(csv.DictReader(stream), start=2):
            yield row_number, row
```

`DictReader` uses CSV headers as dictionary keys. `start=2` treats the header as row 1. `yield` supplies one result at a time while keeping the file open until iteration finishes; it is unrelated to sending arguments into a test function.

An XLSX reader needs its own adapter. Excel numeric cells may already have lost leading zeros; formatting a lost value as text later cannot reliably reconstruct the original identifier.

### 11.2 Header adapter

```python
def adapt_demo_row(source_row):
    return {
        "external_identifier": source_row.get("Matric No", ""),
        "course_code": source_row.get("Course", ""),
        "score": source_row.get("Score", ""),
        "period_reference": source_row.get("Period", ""),
    }
```

This translation preserves the distinction between an external identifier and internal UUID. The next step resolves the identifier through the students module; the adapter must not pretend it is already a stable student key.

### 11.3 Shape validator

```python
def validate_demo_row(row):
    problems = []
    for field in ("external_identifier", "course_code", "period_reference"):
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{field} is required as text")
    try:
        parse_demo_score(row.get("score"))
    except ValueError as exc:
        problems.append(str(exc))
    return problems
```

This exercise assumes `parse_demo_score` from Section 10 is imported or included. It checks shape and values; it does not establish that the student/course exists, that the source is authorised, or that the result belongs to the correct attempt.

### 11.4 Four different duplicate problems

| Situation | Appropriate action |
|---|---|
| Same file bytes | Flag by checksum within the relevant source/workflow context |
| Same source record received again | Use the reviewed idempotency/uniqueness key |
| Same attempt, different score | Create a conflict/revision review, not silent overwrite |
| Same course, later genuine attempt | Keep a separate attempt |

A checksum can recognise bytes; it does not prove authority or correctness. A pre-insert “exists?” check alone cannot prevent simultaneous duplicate inserts. Use the agreed database key and transactional operation.

### 11.5 Acceptance work card

Input: authorised reviewer, batch ID and explicit selected rows.  
Output: acceptance summary with stable accepted references and unresolved rows.  
Rules: reviewed source and period, approved handling of partial batches, calls academic services, records provenance/audit, safe retry.  
Tests: repeated acceptance, invalid student, conflicting result, failure midway and concurrent/repeated delivery where relevant.

Portal integration remains unverified. Build fictional-file adapters first; do not assume the portal exposes an approved API.

## 12. Reporting and protected files

| File | Example contents |
|---|---|
| `reporting/models.py` | ExportJob: requester, selection, snapshot/version, status, private output reference, expiry |
| `reporting/queries.py` | Permission-aware report selection |
| `reporting/services.py` | Request, generate and authorise download operations |
| `reporting/writers.py` | CSV/XLSX formatting, when a split becomes useful |
| `reporting/views.py` / `urls.py` | Report request/status/download handlers |
| `reporting/tests/` | Forbidden fields, scope, revoked access and expired output |

### Standalone CSV formatting exercise

```python
import csv
import io


def build_demo_student_csv(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=["student_id", "full_name"])
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()
```

This receives rows already selected by an authorised query. The writer must not choose permissions. Values opened in spreadsheet software need an agreed formula-injection handling policy; raw CSV quoting does not by itself prevent that problem. This small exercise is not the final export writer.

Check permissions at request, generation and download as applicable. A role may be revoked while a job waits. A file reference is not a public URL. Reports intended to explain historical data should identify the selected data/rule version; request time alone does not freeze all inputs.

If a worker is added, enqueue after the database transaction commits and make retries safe. Avoid a job seeing a record that has not committed yet. The walkthrough leaves the worker optional for the first demonstration.

## 13. Identity, contracts and simulators

The location of fingerprint templates remains undecided in the supplied architecture. Do not infer that academic PostgreSQL tables should store them.

### 13.1 Responsibility map

| Location | Small assignment |
|---|---|
| `identity/models.py` | Device, credential mapping, check request and minimal event records |
| `identity/queries.py` | Restricted active mapping lookup within agreed device scope |
| `identity/services/requests.py` | Create, expire and validate check requests/challenges |
| `identity/services/outcomes.py` | Validate matched/no-match/error outcomes and repeated delivery |
| `identity/services/resolution.py` | Resolve checked credential mapping to stable student ID |
| `identity/api/serializers.py` | Validate message fields and outcome-dependent shape |
| `identity/api/views.py` | Authenticate device, call services, return minimal response |
| `contracts/identity-v1/` | Agreed schema, message examples, errors and version changes |
| `simulators/terminal/` | Pretend device to exercise software receiver |
| `simulators/receiver/` | Pretend receiver to exercise firmware sender |

### 13.2 Proposed message, not approved wire format

```json
{
  "contract_version": "identity-v1",
  "device_id": "D-DEMO-1",
  "request_id": "R-DEMO-1",
  "event_id": "E-DEMO-1",
  "challenge": "fictional-challenge",
  "outcome": "matched",
  "credential_ref": "C-DEMO-7"
}
```

These readable demo request IDs are placeholders; decide real identifier types, challenge encoding, timestamps, expiry, authentication and integrity mechanism before implementation. A body field claiming `device_id` is not proof of sender identity.

### 13.3 Serializer shape exercise

```python
from rest_framework import serializers


class DemoOutcomeSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=100)
    request_id = serializers.CharField(max_length=100)
    outcome = serializers.ChoiceField(choices=["matched", "no_match", "error"])
    credential_ref = serializers.CharField(required=False, max_length=100)

    def validate(self, attrs):
        matched = attrs["outcome"] == "matched"
        has_credential = "credential_ref" in attrs
        if matched and not has_credential:
            raise serializers.ValidationError("matched requires credential_ref")
        if not matched and has_credential:
            raise serializers.ValidationError("Only matched carries credential_ref")
        return attrs
```

This validates a subset of the fictional shape. It does not validate the challenge, authenticate a device, prevent replay, check mapping status or satisfy the full proposed message. Do not use it as the complete receiver.

### 13.4 The actual service sequence

1. Authenticate the sender using the agreed device mechanism.
2. Check registered/active/revoked device state.
3. Validate the message against the agreed contract.
4. Resolve its request/challenge and server-controlled expiry.
5. Apply the agreed event replay/idempotency policy.
6. Validate the outcome; no-match and error never produce a verified ID.
7. For a match, resolve the active device-scoped credential mapping.
8. Reject any inconsistent claimed student identity.
9. Store only the required minimal event/audit information.
10. Return the contract's minimal allowed response.
11. Apply separate staff permission checks to any subsequent academic action.

The same credential number on two devices must not accidentally resolve to the same student. Resolve through the agreed scope. Unknown mapping, revoked mapping and unavailable database are distinct outcomes. A timeout must not be interpreted as successful identification.

### 13.5 Shared fixtures unlock parallel hardware/software work

Suggested contract assets:

- `README.md`: endpoint, authentication, field meanings and outcomes.
- `outcome.schema.json`: executable agreed shape, if JSON Schema is chosen.
- `examples/matched.json`, `no-match.json`, `error.json`.
- `examples/invalid-missing-credential.json`.
- `errors.md`: malformed, unauthorised, expired, unresolved, unavailable meanings.
- `CHANGELOG.md`: compatibility changes.

Software developers use the terminal simulator. Firmware developers use the receiver simulator. Both run the same accepted/rejected fixtures. Simulators must be plainly identified and excluded from production trust assumptions.

Tests correspond to the supplied `test_device_auth.py`, `test_freshness.py`, `test_resolution.py`, `test_minimal_reply.py` and `test_unavailable.py`. They test communication and resolution, not fingerprint matching accuracy; physical matching needs separate evaluation.

## 14. Audit and accountability

An audit event answers: who, did what, to which target, when, for what reason, and as part of which operation?

A useful service interface is:

```python
# Proposed interface, implementation still required.
def record_event(*, actor, action, target_type, target_id, reason, correlation_id): ...
```

The connected student service writes directly for teaching simplicity. As the audit module grows, replace repeated writing code with a reviewed service. Keep action codes stable, such as `student.created` or `import.accepted`.

A correlation ID links related events without copying sensitive payloads into every log. Do not accept an arbitrary browser-supplied actor as authoritative; use the authenticated context.

Ordinary staff must not have update/delete access to audit history. A model alone does not make a table immutable; protect API/admin access and review infrastructure/database privileges. Audit history is not a backup. Test that failed transactional operations leave no misleading successful-change event.

## 15. HTML, CSS, JavaScript and HTMX

### 15.1 Syntax versus semantics in a form

```html
<label for="full-name">Student name</label>
<input id="full-name" name="full_name" type="text" required>
```

- `id="full-name"` connects the label and browser element.
- `name="full_name"` is the key submitted to the server.
- `required` assists the browser; server validation remains necessary.

The element ID and submitted field name need not match. The submitted name must match the receiving form or an explicit adapter.

### 15.2 CSS fragment in `static/css/site.css`

```css
.field-error {
  color: #a11a1a;
  font-weight: 600;
}
```

`.field-error` selects elements with that class. It styles presentation; it does not refuse a server operation. Bootstrap classes may be used alongside project styles after the version and asset-loading approach are agreed.

### 15.3 JavaScript fragment in `static/js/student-form.js`

```javascript
const input = document.querySelector('#full-name');
const counter = document.querySelector('#name-length');
if (input && counter) {
  input.addEventListener('input', () => {
    counter.textContent = String(input.value.length);
  });
}
```

This assumes a counter element exists. It displays a count; server-side validation enforces the actual limit. Use `textContent` for plain text rather than inserting untrusted HTML.

### 15.4 HTMX HTML-fragment exercise

```html
<button hx-get="/students/" hx-target="#student-list" hx-swap="innerHTML">
  Refresh permitted students
</button>
<div id="student-list"></div>
```

This assumes HTMX is loaded and `/students/` has a suitable permission-checked list handler returning the intended fragment. HTMX attributes cause an HTTP request; they do not make Python run inside the browser.

A normal GET reads data. A modifying POST requires the project's CSRF handling for browser-session requests. Agree whether a handler returns a full HTML page, an HTML fragment or JSON; swapping JSON into an HTML table is a contract mismatch.

## 16. Testing and debugging

### 16.1 Map the test location to the question

| Location | Example question |
|---|---|
| `students/tests/test_models.py` | Can two profiles link to the same student? |
| `students/tests/test_services.py` | Does a blank name create any records? |
| `students/tests/test_access.py` | Can staff without creation permission call the service/view? |
| `academics/tests/` | Does a genuine later attempt survive duplicate checks? |
| `tests/integration/` | Does corrected-import acceptance update the right attempt and audit it? |
| `tests/contracts/` | Do simulator and receiver agree on fields and outcomes? |
| `tests/permissions/` | Are prohibited students/fields absent from responses? |
| `tests/end_to_end/` | Can authorised staff complete the agreed fictional workflow? |
| `tests/performance/` | Does the agreed workload meet the measured target? |
| `tests/recovery/` | Do restart, retry and isolated restoration preserve correct behaviour? |

Unit tests focus on a small behaviour. Integration tests check connected parts. End-to-end tests exercise a user journey. Hardware matching accuracy is a separate test concern.

### 16.2 Tests for the connected student service

```python
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from audit.models import AuditEvent
from students.models import Student
from students.services import create_student


class CreateStudentTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username="demo-staff")
        permission = Permission.objects.get(
            content_type__app_label="students", codename="add_student"
        )
        self.actor.user_permissions.add(permission)

    def test_creates_profile_and_audit(self):
        student = create_student(actor=self.actor, full_name=" Ada Example ")
        self.assertEqual(student.profile.full_name, "Ada Example")
        self.assertTrue(AuditEvent.objects.filter(
            action="student.created", target_id=str(student.student_id)
        ).exists())

    def test_blank_name_creates_nothing(self):
        with self.assertRaises(ValidationError):
            create_student(actor=self.actor, full_name="   ")
        self.assertEqual(Student.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_unpermitted_actor_creates_nothing(self):
        outsider = get_user_model().objects.create_user(username="demo-outsider")
        with self.assertRaises(PermissionDenied):
            create_student(actor=outsider, full_name="Ada Example")
        self.assertEqual(Student.objects.count(), 0)
```

This assumes the initial standard-user demonstration and migrated apps. A custom user model may require different account-creation fields. Default model permissions are created by Django; these tests use them rather than assuming staff status grants every operation.

Add view access tests and a meaningful audit-failure rollback test as the feature matures.

### 16.3 Run tests deliberately

From `software/app/`:

```bash
python manage.py test students
python manage.py test students.tests.test_services
python manage.py check
python manage.py makemigrations --check --dry-run
```

Django uses a separate test database; test configuration and database privileges must be correct. `TestCase` provides database isolation. For cross-project tests outside `app/`, define import/discovery settings and package conventions in the test configuration rather than assuming discovery will find every folder.

### 16.4 Pytest and `yield`, if the team later selects pytest

The source uses Django's test runner as its baseline. Pytest is an optional later choice; Django use normally needs pytest-django and corresponding configuration.

Conceptual fixture example:

```python
import pytest


@pytest.fixture
def example_resource():
    resource = open_demo_resource()
    try:
        yield resource
    finally:
        resource.close()


def test_example(example_resource):
    assert example_resource.is_ready()
```

`open_demo_resource()` is a placeholder, not a supplied implementation. Pytest starts the fixture, takes the yielded value, and passes it as the test's named argument. After the test, execution resumes after `yield`; `finally` cleans up. `yield` itself does not send an argument into an arbitrary function. The framework coordinates that behaviour.

### 16.5 Debugging report format

Record: fictional input, environment, steps, expected outcome, actual outcome, traceback, and smallest reproducing test. Read the last traceback line, then follow the relevant project frames. Do not fix an exception by swallowing it and pretending success.

## 17. Parallel work and communication

### 17.1 Three different kinds of parallelism

- **Parallel development:** several people write separate pieces at the same time.
- **Concurrent requests:** several users or devices use the application at once.
- **Background jobs:** a worker runs longer work separately from a browser request.

Git helps the first. Database constraints/transactions and request design help the second. Queue/worker design helps the third. They are related but not interchangeable.

### 17.2 Contract-first collaboration

Before dividing a feature, agree this table:

| Item | Example |
|---|---|
| Feature | Create student |
| Owner | Students developer |
| Caller | Student registration view |
| Function | `create_student` |
| Inputs | Keyword-only `actor`, `full_name`, optional `reason` |
| Output | Saved `Student` with UUID `student_id` and profile |
| Failures | `PermissionDenied`, `ValidationError`; unexpected database failures are not success |
| Permission | `students.add_student`, plus reviewed scope where applicable |
| Side effects | Student, profile and audit event |
| Atomicity | Writes commit or roll back together |
| Examples | Valid name, blank name, denied actor |
| Status | Teaching agreement; refine before full implementation |

The Python developer writes the service, the interface developer writes the form/view, and the test contributor writes the examples against this agreement. None needs to guess whether the field is `name`, `student_name` or `full_name`.

### 17.3 Communication checkpoints

| When | Communicate | Record |
|---|---|---|
| Before coding | Meanings, names, types, rules and dependencies | Task card, data dictionary, interface signature |
| Before parallel implementation | Who owns shared files; expected return/failure forms | Owner/reviewer table |
| When blocked | Exact missing contract or function, temporary simulator/fixture | Issue with an example input/output |
| When changing a shared field | Why, affected consumers, migration and compatibility | Decision note and linked pull request |
| Before integration | Current examples, test command, prerequisites | Handoff note |
| During review | Behaviour, permissions, tests and unresolved decisions | Pull-request description |
| After merge | Required migrations/configuration changes | Setup/changelog entry |

A useful message is: “I need `resolve_external_identity(source_system, identifier_value)` to return a Student or an agreed not-found outcome. May we confirm the source namespace before I finish the adapter?” It identifies the decision instead of saying only “database part not ready.”

### 17.4 Local names versus boundary changes

Renaming a temporary loop variable is local. Renaming a service argument, model field, template context key or JSON key can affect other contributors. Search for consumers and announce the boundary change.

Use an adapter when the source uses a different name. Do not require a university spreadsheet to rename its header just because the project uses `identifier_value` internally.

### 17.5 Git workflow

From the repository root, with a clean or understood working tree:

```bash
git switch main
git pull --ff-only
git switch -c feature/student-create
```

After implementation and focused checks:

```bash
git status
git add software/app/students software/app/audit
git diff --cached
git commit -m "Add fictional student creation with audit"
```

Inspect staged changes; use specific paths. Opening a pull request is a review action, not deploying the application. A concise description states behaviour, linked task, tests, migration/configuration changes and remaining limitations.

One owner should coordinate a given shared model/migration change. Contributors to different modules can often proceed independently. If two migrations branch from the same predecessor, review and merge their dependency graph appropriately; do not blindly rename sequence numbers or delete files already applied elsewhere.

### 17.6 Stubs and fakes

A proposed function can raise `NotImplementedError` so missing work is visible. A test fake returns explicitly fictional outcomes. Never let a production authentication stub return `True` for every device.

Frontend work can use synthetic template context. Import work can use a fake identity resolver. Firmware work can use the receiver simulator. These unblock development while preserving an explicit boundary between demonstration and implementation.

### 17.7 Concurrent requests need database rules

Two requests can both ask “does this record exist?” and both hear “no” before either inserts. The solution is not only a Python `if` statement. Enforce the reviewed unique key in the database, use transactions, and handle the specific expected conflict without labelling every database failure a duplicate.

For multi-step revisions or acceptance, the service may need row locking and idempotency keys. Have a reviewer establish the transactional strategy. Git merge success says nothing about concurrent database safety.

## 18. Configuration, packaging and deployment

### 18.1 Repository files

| File/area | Example contents | Owner |
|---|---|---|
| `README.md` | Supported setup, installation, migration, test and start commands | Coordinator with developer review |
| `pyproject.toml` | Project metadata, dependencies and agreed tool settings | Backend/setup owner |
| `.env.example` | Configuration names and safe example values | Operations/backend |
| `app/manage.py` | Generated maintenance command entry point | Django setup owner |
| `config/settings/base.py` | Shared installed apps, middleware, templates and DB configuration | Backend/operations |
| `config/settings/local.py` | Explicit local overrides | Backend |
| `config/settings/test.py` | Isolated testing configuration | Tests/operations |
| `config/settings/staging.py` | Shared rehearsal configuration | Operations |
| `config/settings/production.py` | Reviewed live configuration | Operations |
| `config/urls.py` | Module route inclusion | Backend |
| `config/asgi.py` / `wsgi.py` | Hosting server entry points | Setup/operations |
| `deployment/` | Startup, configuration, health and recovery instructions | Operations |
| `docs/` | Dictionary, contracts, decisions and support guides | Shared, with named reviewers |

Environment filenames above are proposed conventions. Choose them once and use the same spelling in commands and hosting configuration.

### 18.2 Configuration example

```dotenv
DJANGO_SETTINGS_MODULE=config.settings.local
DJANGO_SECRET_KEY=replace-with-local-development-secret
DB_NAME=eee_dev
DB_USER=eee_dev_user
DB_PASSWORD=replace-locally
DB_HOST=localhost
DB_PORT=5432
```

This is `.env.example`, not real credentials. Actual values stay outside tracked source. Environment variables arrive as strings: `bool("False")` is `True` because non-empty strings are truthy. Parse configuration explicitly rather than assuming Python understands a textual Boolean.

```python
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
```

### 18.3 TOML example

```toml
[project]
name = "oau-eee-records"
version = "0.1.0"
description = "Departmental records system"
```

This is metadata only. The setup owner must supply reviewed Python requirements, dependency constraints, lock/install method and build/package configuration as applicable. Do not instruct `pip install -e .` until editable packaging is actually configured. TOML's `[section]` and `key = value` syntax configure tools; they are not Python statements.

### 18.4 Minimum Django setup around the examples

- Include `django.contrib.auth`, `contenttypes`, `sessions` and the project's apps in `INSTALLED_APPS`.
- Retain appropriate security, session, authentication and CSRF middleware.
- Configure the `app/templates/` directory in `TEMPLATES` and static settings.
- Select `AUTH_USER_MODEL` early if using a custom account model.
- Configure `DATABASES`, `SECRET_KEY`, timezone support and allowed hosts.
- Give packages the required `__init__.py` files and app configurations.
- Create/review/apply student and audit migrations.
- Configure the login route/template and post-login destination.

`manage.py` normally selects a default settings module. With split settings, agree the default or supply the module explicitly:

```bash
python manage.py check --settings=config.settings.local
```

Do not rebuild generated entry points unnecessarily. ASGI/WSGI connect the hosting server to the Django application; business logic belongs in modules.

### 18.5 Development, staging and production

Development is personal practice with synthetic data. Staging is a shared rehearsal. Production is approved departmental use. Each has separate configuration, credentials, databases and file storage.

The development `runserver` command is not the final production hosting arrangement. Production needs an agreed application server, HTTPS, static asset handling, private-file access, monitoring, backup and named operational ownership.

A useful recovery exercise restores the database and required private files into an isolated environment, then checks relationships, permissions and report references. A database-only restore may leave file references pointing to missing files.

## 19. A practical build progression

The architecture is the destination. The following sequence gives beginners representative contributions while deeper work receives appropriate review.

| Stage | Build | Learner contribution | Completion evidence |
|---|---|---|---|
| A | Dictionary and synthetic fixtures | Explain names/types and write fictional rows | Reviewers agree meanings and open decisions |
| B | Local Django/PostgreSQL setup | Follow setup and report missing instructions | Fresh environment starts and runs one test |
| C | Student/profile creation | Write name validator and service tests | Authorised creation, blank refusal and audit work |
| D | Scoped lookup/access | Write allowed/refused examples | Direct calls and HTTP requests respect scope |
| E | Period/course version/offering/attempt | Help create fixtures and constraints | Later genuine repeat remains distinct |
| F | Staged CSV import | Write adapter and validation | Preview shows errors; approved acceptance is repeat-safe |
| G | Minimal authorised report | Write formatting exercise | Only allowed rows/fields exported and downloadable |
| H | Identity contract/simulators | Produce valid and invalid message fixtures | Sender/receiver agree, failure outcomes are clear |
| I | Full identity checks | Assist failure tests under review | Unknown/revoked/expired/unavailable states fail appropriately |
| J | Connected demonstration/recovery | Execute test checklist | Walkthrough's small demonstration and isolated restore succeed |

Identity contract/simulator work can start alongside C–G after the stable-key agreement. UI layout can start with synthetic context. Detailed academic modelling needs semantic review before imports publish real academic state.

Move on when you can explain the behaviour, implement a bounded part and show evidence. Reading every technology description is not a prerequisite for writing a row validator.

## 20. Task cards people can pick up

### Card 01 — Define stable student identity

**Owner:** data/student developer; reviewer: backend/data reviewer.  
**Write:** dictionary entry, Student model and migration.  
**Agree:** key type, server generation, external ID separation, correction rules.  
**Verify:** new students receive distinct stable keys; relationships use that key.  
**Handoff:** exact model field/type and migration dependency.

### Card 02 — Validate a profile name

**Owner:** beginner Python contributor with review.  
**Write:** `normalise_name` and cases for valid text, spaces only, wrong type and agreed length.  
**Output:** cleaned text or clear validation failure.  
**Do not decide:** name order, uniqueness or identity merging.  
**Handoff:** function signature and exception type.

### Card 03 — Create student with audit

**Owner:** backend/student developer.  
**Write:** Section 7 service and tests.  
**Depends on:** student/profile/audit models and permission agreement.  
**Verify:** authorised operation; denied actor; blank input; rollback when required write fails.  
**Handoff:** saved Student object and agreed failure forms.

### Card 04 — Add guardian relationship

**Owner:** student developer.  
**Write:** contact/link models, service and relationship tests.  
**Agree:** optional values, allowed relationship meanings and access purposes.  
**Verify:** several contacts can link to one student without overwriting each other.

### Card 05 — Resolve exact course offering

**Owner:** academic developer; reviewer: Academic Data Steward and technical peer.  
**Write:** period/course version/offering model/query.  
**Agree:** reference names and historical applicability.  
**Verify:** same course in two periods resolves to different offerings.

### Card 06 — Preserve repeated attempts

**Owner:** academic developer.  
**Write:** registration service and reviewed uniqueness constraint.  
**Verify:** same source record re-imported does not duplicate; genuine later attempt survives.  
**Handoff:** stable attempt reference for result/import services.

### Card 07 — Read and validate fictional CSV

**Owner:** beginner/intermediate import contributor.  
**Write:** reader, header adapter and row errors.  
**Depends on:** canonical field dictionary.  
**Verify:** leading-zero identifiers stay text; missing score stays missing; row number is reported.  
**Handoff:** staged row format, not direct academic-table writes.

### Card 08 — Accept a reviewed batch

**Owner:** import/backend developer.  
**Write:** transactional acceptance that calls academic services.  
**Agree:** source identity key, partial acceptance policy and correction rules.  
**Verify:** repeat-safe acceptance, conflict handling and required audit.

### Card 09 — Export permitted records

**Owner:** reporting developer with access review.  
**Write:** restricted query, output writer and download handler.  
**Agree:** permitted fields, snapshot/version meaning, expiry and spreadsheet text handling.  
**Verify:** prohibited fields absent; revoked download refused.

### Card 10 — Contract fixtures and simulator

**Owner:** API developer with firmware partner.  
**Write:** versioned examples, schema if chosen, simulator and contract tests.  
**Agree:** field types, authentication, challenge and error meanings.  
**Verify:** both sides accept and reject the same cases.

### Card 11 — Resolve a device credential

**Owner:** identity developer with specialist review.  
**Write:** active device-scoped mapping query and resolution service.  
**Verify:** same local credential on different devices does not confuse students; revoked/unknown mapping returns no verified ID; lookup failure is unavailable, not success.

### Card 12 — Document and practise recovery

**Owner:** operations developer; learner assists checklist.  
**Write:** isolated backup restoration procedure covering database and private files.  
**Verify:** relationships, access and required files after restoration.  
**Handoff:** exact steps, observed results and named operational responsibility.

## 21. Syntax and semantics reference

Syntax is how you write an expression. Semantics is what it means. Valid syntax can still implement the wrong institutional rule.

| Expression | Syntax explanation | Meaning in this project |
|---|---|---|
| `def validate_row(row):` | Define function with parameter | Reusable row check |
| `return problems` | Return a value to caller | List of detected issues |
| `raise ValidationError(...)` | Stop normal operation with exception | Explain refused input |
| `class Student(models.Model):` | Class inherits framework model | Describe stored student identity |
| `student.full_name` | Attribute access | Field/property, if defined |
| `row["full_name"]` | Dictionary key access | Value inside a parsed mapping |
| `row.get("score")` | Safe dictionary lookup | Missing key returns None by default |
| `Student.objects.filter(...)` | ORM query construction | Select matching records, normally lazily |
| `.get(...)` | Expect one matching object | Missing/multiple matches are errors |
| `.exists()` | Ask whether query matches | Existence, not uniqueness enforcement |
| `ForeignKey(...)` | Model relationship field | Link rather than duplicate related facts |
| `with transaction.atomic():` | Context manager | Group database changes |
| `@login_required` | Decorator | Add login check around view |
| `**cleaned_data` | Expand mapping into keywords | Keys must match callable parameters |
| `*` in parameters | Keyword-only separator | Make call sites explicit |
| `{{ student.student_id }}` | Template variable output | Render server-provided value |
| `{% csrf_token %}` | Template instruction | Browser-session form protection |
| `"student_id": "..."` | JSON member | Wire field; UUID encoded as text |
| `SELECT ... WHERE ...` | SQL query | Read records subject to query conditions |
| `[project]` | TOML table | Package/tool metadata |
| `DB_NAME=eee_dev` | Environment assignment format | Configuration string, not model data |
| `yield row` | Generator produces item and pauses | Stream file rows; resume on next iteration |

### Python, JSON, SQL and JavaScript differences

| Idea | Python | JSON | SQL | JavaScript |
|---|---|---|---|---|
| True | `True` | `true` | `TRUE` | `true` |
| False | `False` | `false` | `FALSE` | `false` |
| Absence | `None` | `null` | `NULL` | `null` / `undefined` with distinct meanings |
| Equality | `==` | No expressions | `=` in comparisons | Prefer deliberate `===` |
| Text | Single or double quoted | Double quoted | Single quoted literals | Single or double quoted |
| Mapping | `dict` | Object | Tables/columns, different abstraction | Object / Map |

JSON cannot directly represent a UUID object, Decimal or datetime. Encode them with agreed string/number formats. A Django serializer helps conversion, but field meanings still need agreement.

### One value crossing tools

A score enters CSV as `"72.50"`. An adapter retains the text. Validation converts it to `Decimal("72.50")`. A `DecimalField` stores it as PostgreSQL numeric. An API may return `"72.50"` under an agreed decimal-string contract. A template presents `72.50` to staff. A test checks exact accepted value and behaviour.

A field's representation can change between tools while its meaning remains consistent. Conversion is deliberate; guessing is not.

## 22. Decisions and reference material

### 22.1 Decisions still required

| Decision | Reviewer/owner | What is blocked |
|---|---|---|
| Stable key and external identity rules | Student/data reviewer | Shared relationships and import resolution |
| Staff roles and record/field scopes | Department/access reviewer | Production access behaviour |
| Sessions, semesters and academic history | Academic Data Steward | Period/level interpretation |
| Attempt identity and allowed repeats | Academic Data Steward + data reviewer | Uniqueness and safe re-import |
| Curriculum/elective/exemption rules | Academic authority | Outstanding-requirement evaluation |
| Result precision, validity and approval meanings | Academic authority | Result acceptance/calculation |
| Authorised sources and portal route | Department/integration owner | Live university-data adapter |
| Identity wire format/authentication/freshness | API and firmware reviewers | Actual terminal integration |
| Template storage/matching arrangement | Biometric/hardware reviewers | Biometric material handling |
| Hosting, backup and operational ownership | Institution/operations owner | Live deployment |
| Final dependency versions | Technical/setup owner | Reproducible environment |

Unresolved decisions should be recorded with owner, options, affected tasks and expected resolution. Synthetic examples can continue where they do not silently settle those decisions.

### 22.2 Source walkthrough map

| Handbook subject | Walkthrough pages |
|---|---|
| Database/file separation | 1–4, 27 |
| Tree and module conventions | 9–15 |
| Identity resolution and required tests | 16–21, 29–30, 68 |
| Modular monolith and boundaries | 23–26 |
| Tools and foundational knowledge | 33–50 |
| Data meanings and entities | 51–71 |
| Roles and growth | 73–80, 82 |
| Operations and first demonstration | 81, 83 |

The PDF is the architecture source. Field choices, function names, extra helper files and code fragments in this handbook are teaching proposals extending it, not claims copied from an implemented repository.

### 22.3 Official technical references

Use documentation matching the installed version. These links explain framework/tool mechanics; departmental meanings still come from the project's reviewed decisions.

- [Python tutorial](https://docs.python.org/3/tutorial/) — language fundamentals.
- [Python decimal](https://docs.python.org/3/library/decimal.html) — decimal representations.
- [Django models, 5.2](https://docs.djangoproject.com/en/5.2/topics/db/models/) — model definitions and relationships.
- [Django migrations, 5.2](https://docs.djangoproject.com/en/5.2/topics/migrations/) — model changes propagated to database structure.
- [Django transactions, 5.2](https://docs.djangoproject.com/en/5.2/topics/db/transactions/) — transaction boundaries.
- [Django testing, 5.2](https://docs.djangoproject.com/en/5.2/topics/testing/overview/) — test runner and test databases.
- [Django authentication, 5.2](https://docs.djangoproject.com/en/5.2/topics/auth/) — users and permissions.
- [Django REST Framework serializers](https://www.django-rest-framework.org/api-guide/serializers/) — structured conversion and validation.
- [PostgreSQL database creation](https://www.postgresql.org/docs/current/tutorial-createdb.html) — server/database distinction and creation.
- [HTMX documentation](https://htmx.org/docs/) — server interactions through HTML attributes.
- [Bootstrap documentation](https://getbootstrap.com/docs/) — presentation components.
- [Git book](https://git-scm.com/book/en/v2) — version-control workflow.

### 22.4 Teach-back questions

Before owning a task, explain in your own words:

1. What does my function receive and return?
2. Which names are local, and which are promises to other people?
3. Which rule comes from the department rather than the programming language?
4. Which layer checks input, access and database integrity?
5. What happens when information is missing or a dependency fails?
6. Which example would prove my code wrong?
7. How does my teammate call the piece I wrote?
8. Can repeated requests create duplicate state?
9. Which migration or configuration must another developer apply?
10. What remains unimplemented after my task is complete?

Being able to answer these questions is more useful than memorising every technology name. Begin with one small behaviour, make its boundaries visible, and grow the project through reviewed connections.

### Verification of this handbook

All 27 Python code blocks were checked for valid Python syntax. The standalone name, score and row-validation examples were exercised with valid and invalid fictional inputs. The connected Django example was reviewed for matching names and dependencies but was not executed: Django is not installed in the document-preparation environment. Database migrations, HTTP workflows and API fragments must be exercised in the configured project before adoption.
