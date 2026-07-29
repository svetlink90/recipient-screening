"""Risk provider interface."""

from __future__ import annotations

from typing import Protocol

from ..models import CheckResult, ScreeningRequest


class RiskProvider(Protocol):
    check_id: str

    def assess(self, request: ScreeningRequest,
               sanctioned_addresses: set[str]) -> CheckResult:
        """Return a CheckResult. sanctioned_addresses carries every crypto
        address extracted from the sanctions lists, so proximity providers
        can flag flows from listed addresses without a second source."""
        ...
