"Custom exception hierarchy for SudoLink."

from __future__ import annotations


class SudoLinkError(Exception):
    """Base class for user-facing errors."""


class LinkExtractionError(SudoLinkError):
    """Raised when a message does not contain a usable URL."""


class MetadataFetchError(SudoLinkError):
    """Raised when the original link cannot be fetched."""


class SearchProviderError(SudoLinkError):
    """Raised when the external search provider fails or is not configured."""


class ResultFormattingError(SudoLinkError):
    """Raised when the final response could not be created."""
