"""Custom exceptions and error handling utilities."""
import logging
import uuid

logger = logging.getLogger("pathwise.errors")


class UserFacingError(Exception):
    """An exception whose message is safe to present directly to end users."""

    def __init__(self, message: str, status_code: int = 400, code: str = "bad_request"):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def log_internal_error(exc: Exception, context: str = "") -> str:
    """Log the real exception with a unique error tracking ID and stack trace."""
    err_id = str(uuid.uuid4())[:8]
    logger.error(f"[ERR-{err_id}] Internal error in {context}: {exc}", exc_info=True)
    return err_id
