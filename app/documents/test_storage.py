"""Keep synthetic document uploads out of every configured application folder."""
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.storage import FileSystemStorage

from .models import StudentDocument


def isolate_document_storage(test_case):
    """Swap the already-instantiated FileField storage until test cleanup."""
    directory = TemporaryDirectory(prefix="eee_test_documents_")
    field = StudentDocument._meta.get_field("file")
    previous_storage = field.storage
    # Cleanups run in reverse order: restore the shared field before deleting
    # the temporary files. Also works if the test fails during its setup.
    test_case.addCleanup(directory.cleanup)
    test_case.addCleanup(setattr, field, "storage", previous_storage)
    field.storage = FileSystemStorage(location=directory.name)
    return Path(directory.name)
