"""Errors for desktop perception."""


class PerceptionError(Exception):
    """Base error for desktop perception."""


class PerceptionUnavailableError(PerceptionError):
    """A perception capability is unavailable in this environment."""
