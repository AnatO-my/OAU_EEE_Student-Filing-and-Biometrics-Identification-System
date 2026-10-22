"""Private test uploads use a directory removed when the test process exits."""

from tempfile import TemporaryDirectory

_private_media = TemporaryDirectory(prefix="test_private_media_")
PRIVATE_MEDIA_ROOT = _private_media.name
