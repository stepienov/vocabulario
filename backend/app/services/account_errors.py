"""Errors shared by the account services (E-001/F-004)."""

from __future__ import annotations

from datetime import datetime


class CredentialError(Exception):
    """Maps to the API error `code` with `status_code`; nothing was changed."""

    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code


class MailRateLimited(Exception):
    """Authenticated mail request over the per-recipient limit; maps to 429."""

    def __init__(self, retry_at: datetime) -> None:
        super().__init__("mail_rate_limited")
        self.retry_at = retry_at
