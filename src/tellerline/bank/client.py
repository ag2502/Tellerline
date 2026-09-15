"""Async client the agent uses to run actions against the bank."""

from typing import Any

import httpx

from tellerline.actions import Action

BANK_URL = "http://127.0.0.1:8090"


class BankClient:
    """Runs a validated action for the call's verified customer and returns the bank's answer.

    Errors the caller should hear about (an unknown card, an account they don't have) come back
    as ``{"error": ...}`` for the response templates; anything else raises.
    """

    def __init__(self, base_url: str = BANK_URL, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=5.0)
        self.customer_id: str | None = None

    async def close(self) -> None:
        await self._client.aclose()

    async def run(self, action: Action) -> dict[str, Any]:
        args = action.arguments
        if action.tool == "verify_identity":
            result = await self._call("POST", "/v1/identity/verify", json=args)
            if result.get("verified"):
                self.customer_id = result["customer_id"]
            return result
        if action.tool == "transfer_to_human":
            body = {"customer_id": self.customer_id, "reason": args.get("reason")}
            return await self._call("POST", "/v1/handoffs", json=body)
        if action.tool == "end_call":
            return {"status": "ending"}

        if self.customer_id is None:
            raise PermissionError(f"{action.tool} needs a verified caller")
        base = f"/v1/customers/{self.customer_id}"
        if action.tool == "get_balance":
            return await self._call("GET", f"{base}/accounts/{args['account']}/balance")
        if action.tool == "get_recent_transactions":
            return await self._call(
                "GET",
                f"{base}/accounts/{args['account']}/transactions",
                params={"count": args.get("count", 3)},
            )
        if action.tool == "freeze_card":
            return await self._call(
                "POST",
                f"{base}/cards/{args['card_last_four']}/freeze",
                json={"reason": args["reason"]},
            )
        if action.tool == "order_replacement_card":
            return await self._call("POST", f"{base}/cards/{args['card_last_four']}/replacement")
        if action.tool == "dispute_transaction":
            return await self._call("POST", f"{base}/disputes", json=args)
        raise ValueError(f"Unknown action {action.tool}")

    async def _call(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        response = await self._client.request(method, path, **kwargs)
        if response.status_code in (404, 422):
            detail = response.json().get("detail")
            if isinstance(detail, dict) and "error" in detail:
                return detail
        response.raise_for_status()
        return response.json()
