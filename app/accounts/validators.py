"""Allow departmental matriculation identifiers as exact login usernames."""
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _


@deconstructible
class DepartmentUsernameValidator(UnicodeUsernameValidator):
    regex = r"^[\w.@+/\-]+\Z"
    message = _("Enter a valid username. Use letters, numbers and @/./+/-/_ characters only.")
