"""Isolated PDF conversion process; reads bytes from stdin and emits only JSON."""
import json
import sys

from .format import MAX_BYTES
from .preparation import PreparationError, prepare_pdf_in_process


def main():
    try:
        # On Linux, cap decompression/process allocation too. Windows receives
        # input/page/character/table bounds and the supervising process timeout.
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
        except (ImportError, OSError, ValueError):
            pass
        metadata = sys.stdin.buffer.readline(65537)
        if len(metadata) > 65536:
            raise PreparationError("PDF preparation metadata exceeds its bound.")
        request = json.loads(metadata)
        data = sys.stdin.buffer.read(MAX_BYTES + 1)
        if not data or len(data) > MAX_BYTES:
            raise PreparationError("The PDF exceeds the 2 MiB upload bound.")
        result = prepare_pdf_in_process(data, request["filename"], **request["options"])
    except PreparationError as error:
        result = {"error": str(error)}
    except Exception:
        result = {"error": "The PDF is corrupted, encrypted or unsupported. Use a reviewed CSV export."}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=True).encode("utf-8"))


if __name__ == "__main__":
    main()
