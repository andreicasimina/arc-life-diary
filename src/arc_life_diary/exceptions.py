"""Domain exception hierarchy for arc-life-diary.

All custom exceptions derive from DiaryError, enabling clean caller-level handling.
"""


class DiaryError(Exception):
    """Base exception for all domain and operational errors in arc-life-diary."""

    pass


class ConfigurationError(DiaryError):
    """Base exception for configuration and authentication issues."""

    pass


class ProviderAuthError(ConfigurationError):
    """Raised when provider credentials cannot be loaded or authenticated."""

    pass


class GoogleDriveAuthError(ProviderAuthError):
    """Raised when Google Drive authentication fails or required credentials are missing."""

    pass


class UnknownProviderError(ConfigurationError, ValueError):
    """Raised when an unrecognized provider name is specified."""

    pass


class ValidationError(DiaryError, ValueError):
    """Raised when input validation fails (e.g. empty queries, invalid entry format)."""

    pass


class StorageError(DiaryError):
    """Base exception for local and remote storage failures."""

    pass


class DimensionMismatchError(StorageError, ValueError):
    """Raised when vector dimensions do not match database or model dimensions."""

    pass


class RemoteStorageError(StorageError):
    """Raised when remote cloud storage operations (e.g. Google Drive) fail."""

    pass


class BackupError(DiaryError):
    """Base exception for backup and restore operations."""

    pass


class EmptyArchiveError(BackupError):
    """Raised when an entries directory or archive contains no journal entries."""

    pass


class DecryptionError(BackupError):
    """Raised when archive decryption fails due to invalid password or corruption."""

    pass


class PasswordMismatchError(BackupError):
    """Raised when password confirmation does not match."""

    pass


class RestoreCancelledError(BackupError):
    """Raised when restore is cancelled by the user."""

    pass


class AIProviderError(DiaryError):
    """Raised when an AI provider fails during embedding generation or LLM synthesis."""

    pass
