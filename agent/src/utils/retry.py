from typing import Callable

import requests
import structlog
import tenacity

from agent.src.exceptions import GeminiError

log = structlog.get_logger(__name__)


def _log_before_sleep(retry_state: tenacity.RetryCallState) -> None:
    exc = retry_state.outcome.exception()
    log.warning(
        "retrying",
        attempt=retry_state.attempt_number,
        exception=str(exc),
        exception_type=type(exc).__name__,
    )


def retry_network(extra_exceptions: tuple = ()) -> Callable:
    """Returns a tenacity retry decorator with exponential backoff.

    Retries on requests.RequestException, GeminiError, and any extra
    exception types passed in.
    """
    exceptions = (requests.RequestException, GeminiError, *extra_exceptions)
    return tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
        retry=tenacity.retry_if_exception_type(exceptions),
        before_sleep=_log_before_sleep,
        reraise=True,
    )
