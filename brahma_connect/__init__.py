"""Brahma Connect subsystem.

This package adds the local gateway, device registry, pairing flow, and
protocol definitions used by Brahma AI to reach companion devices.
"""

from .service import BrahmaConnectService, get_service

__all__ = ["BrahmaConnectService", "get_service"]
