class ConfigError(Exception):
    pass


class GeminiError(Exception):
    pass


class ScrapeError(Exception):
    pass


class PlacesError(Exception):
    pass


class AgentMailError(Exception):
    pass


class SendError(Exception):
    pass


class AuthError(Exception):
    pass


class ReplyDraftError(Exception):
    pass


class BriefError(Exception):
    pass


class FirecrawlError(Exception):
    pass


class UnipileError(Exception):
    pass


class LinkedInDraftError(Exception):
    pass


class ApolloError(Exception):
    """Raised when an Apollo API call fails.

    Carries the upstream HTTP status so callers can surface it (e.g. a 403
    on the free plan) instead of swallowing it. `status_code` is 0 for
    transport-level failures (timeout, connection refused).
    """

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code
