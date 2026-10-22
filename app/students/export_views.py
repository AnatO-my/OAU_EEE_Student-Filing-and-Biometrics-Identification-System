import csv

from django.http import StreamingHttpResponse
from rest_framework.permissions import BasePermission

from .views import StudentListView


# Require both student-view and explicit student-export permissions.
class ExportStudentPermission(BasePermission):
    # Exports are limited to authenticated, active staff with both permissions.
    def has_permission(self, request, view):
        user = request.user
        return (user.is_authenticated and user.is_active and user.is_staff
                and user.has_perm("students.view_student")
                and user.has_perm("students.export_student"))


# Provide csv.writer with a file-like target that returns each generated row.
class Echo:
    # Return a CSV chunk directly for streaming in the HTTP response.
    def write(self, value):
        return value


# Convert values to safe CSV text, prefixing spreadsheet formula-like input.
def spreadsheet_cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


# Stream the filtered student list using an explicit, fixed export field set.
class StudentExportView(StudentListView):
    permission_classes = [ExportStudentPermission]
    http_method_names = ["get", "head", "options"]

    # Build a no-store CSV response without buffering the complete student list.
    def get(self, request, *args, **kwargs):
        students = self.filter_queryset(self.get_queryset())
        # Explicit export policy: adding an API field must not silently export it.
        fields = (
            "student_id", "identifier_type", "identifier_value", "full_name",
            "phone_number", "admission_year", "mode_of_admission", "current_level",
            "is_active", "academic_status",
        )
        writer = csv.writer(Echo())

        # Yield the header and each sanitized record as the client consumes it.
        def rows():
            yield writer.writerow(fields)
            for student in students.iterator(chunk_size=500):
                yield writer.writerow([spreadsheet_cell(getattr(student, field)) for field in fields])

        response = StreamingHttpResponse(rows(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="student-profiles.csv"'
        response["Cache-Control"] = "no-store"
        return response
