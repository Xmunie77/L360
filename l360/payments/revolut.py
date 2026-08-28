"""Revolut Business API client.

⚠️ The exact response shape here is best-effort against Revolut's publicly
documented Business API transactions endpoint, written without a live
token to verify against. Treat the JSON field names below (`legs`,
`completed_at`, `state`, `counterparty.name`) as a starting point that
MUST be checked against a real account + REVOLUT_API_TOKEN before this
goes live — see l360/DEPLOY.md. The reconciliation logic downstream
(l360/reconciliation.py) is provider-agnostic and fully tested against
synthetic data, so a shape mismatch here is a contained, obvious fix
(transactions come back empty or malformed) rather than a silent
correctness bug in matching or invoicing.
"""
from __future__ import annotations

from datetime import datetime

import httpx

from l360.config import REVOLUT_API_BASE, REVOLUT_API_TOKEN
from l360.payments.provider import PaymentProvider, ProviderNotConfigured, RawTxn


class RevolutProvider(PaymentProvider):
    def fetch_transactions(self, since: datetime) -> list[RawTxn]:
        if not REVOLUT_API_TOKEN:
            raise ProviderNotConfigured("REVOLUT_API_TOKEN is not set")

        headers = {"Authorization": f"Bearer {REVOLUT_API_TOKEN}"}
        params = {"from": since.isoformat()}
        resp = httpx.get(f"{REVOLUT_API_BASE}/transactions", headers=headers, params=params, timeout=30)
        resp.raise_for_status()

        out: list[RawTxn] = []
        for row in resp.json():
            if row.get("state") != "completed":
                continue
            legs = row.get("legs") or []
            if not legs:
                continue
            leg = legs[0]
            amount = leg.get("amount")
            # Only incoming money is a payment; Revolut represents outgoing
            # legs as negative amounts.
            if amount is None or amount <= 0:
                continue
            completed_at = row.get("completed_at")
            if not completed_at:
                continue
            out.append(RawTxn(
                external_id=row["id"],
                txn_date=datetime.fromisoformat(completed_at),
                amount_cents=round(amount * 100),
                currency=leg.get("currency", "EUR"),
                reference=row.get("reference"),
                counterparty=(row.get("counterparty") or {}).get("name"),
            ))
        return out
