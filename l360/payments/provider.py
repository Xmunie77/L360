"""Payment-provider interface. Revolut Business is the only implementation
today (see revolut.py); swapping in another provider later means
implementing this same interface — the reconciliation and billing code
never depends on Revolut specifics directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawTxn:
    external_id: str
    txn_date: datetime
    amount_cents: int
    currency: str
    reference: str | None
    counterparty: str | None


class PaymentProvider:
    def fetch_transactions(self, since: datetime) -> list[RawTxn]:
        raise NotImplementedError


class ProviderNotConfigured(Exception):
    """Raised when a provider is asked to sync without its API credentials
    set — the caller should surface this as a clear admin-facing message,
    not a stack trace."""
