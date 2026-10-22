# Keep the legacy session-context import path while delegating to the canonical resolver.
def current_session_name():
    from .current_session import current_session_name as resolve
    return resolve()
