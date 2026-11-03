"""Domain exception hierarchy for arc-life-diary."""


class DiaryError(Exception):
    """Base exception for all domain and operational errors in arc-life-diary."""

    pass


class UnknownProviderError(DiaryError, ValueError):
    """Raised when an unrecognized provider name is specified."""

    pass
