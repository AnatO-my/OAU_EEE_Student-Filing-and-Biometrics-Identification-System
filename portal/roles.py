from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import Student

def is_hod(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name="HOD").exists())

def is_lecturer(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name__in=["Lecturers", "HOD"]).exists())

def is_part_adviser(user):
    """Checks if the user belongs to any Part Adviser group."""
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name__startswith="PartAdviser_").exists())

def get_adviser_level(user):
    """Extracts the specific level integer the user is advising (e.g., 100 from 'PartAdviser_100')."""
    if user.is_superuser or user.groups.filter(name="HOD").exists():
        return None  # HOD sees all levels
    group = user.groups.filter(name__startswith="PartAdviser_").first()
    if group:
        try:
            return int(group.name.split("_")[1])
        except (IndexError, ValueError):
            return None
    return None

def is_student(user):
    return user.is_authenticated and Student.objects.filter(user=user).exists()


def role_required(check):
    """Decorator: log in first, then give a 403 'not allowed' page if the role check fails."""
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator