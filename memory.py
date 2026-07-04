"""
memory.py
---------
Cognee CLOUD integration using cognee.serve() -- the managed CloudClient.
import os

# Must be set BEFORE importing cognee
os.environ.setdefault("COGNEE_SERVICE_URL", "https://tenant-81f70461-f8df-4863-9627-6edd07e08aca.aws.cognee.ai")

import asyncio
from typing import Any, Optional
import cogneeThis is the actual Cognee Cloud API surface (remember/recall/improve/forget),
not the self-hosted add()/cognify()/search() calls. Routes through Cognee
Cloud's managed infra, so it does NOT need a separate OpenAI/Groq key.


Required env vars (set as Codespaces secrets, never hardcoded):
    COGNEE_SERVICE_URL = https://api.cognee.ai
    COGNEE_API_KEY     = your key from platform.cognee.ai

Run this file directly to sanity-check your Cognee Cloud connection:
    python memory.py
"""

import os
import asyncio
from typing import Any, Optional

import os
os.environ.setdefault("COGNEE_API_KEY", os.environ.get("COGNEE_API_KEY", ""))
os.environ.setdefault("COGNEE_SERVICE_URL", "https://tenant-81f70461-f8df-4863-9627-6edd07e08aca.aws.cognee.ai")
import cognee

POLICY_DATASET = "procurement_policies"
HISTORY_DATASET = "procurement_history"

_client: Optional[Any] = None


async def _get_client():
    """Lazily connect to Cognee Cloud once and reuse the client."""
    global _client
    if _client is None:
        os.environ.setdefault("COGNEE_SERVICE_URL", "https://tenant-81f70461-f8df-4863-9627-6edd07e08aca.aws.cognee.ai")
        assert os.environ.get("COGNEE_API_KEY"), (
            "COGNEE_API_KEY not set. Add it as a Codespaces secret from "
            "https://platform.cognee.ai/sign-in"
        )
        _client = await cognee.serve()
    return _client


async def remember_policy(text: str) -> None:
    """Ingest a policy statement / document into long-term Cloud memory."""
    client = await _get_client()
    await client.remember(text, dataset_name=POLICY_DATASET)


async def remember_decision(
    department: str,
    vendor_status: str,
    item_type: str,
    request_id: str,
    decision_summary: str,
) -> None:
    """
    Called after every /step. Stores what was decided so future requests
    from the same department/vendor context can be recalled as precedent.
    """
    client = await _get_client()
    entry = (
        f"Request {request_id} | Department: {department} | "
        f"Vendor status: {vendor_status} | Item type: {item_type} | "
        f"Outcome: {decision_summary}"
    )
    await client.remember(entry, dataset_name=HISTORY_DATASET)


async def recall_policy(query: str) -> str:
    """Ask memory what policy applies to a given request description."""
    client = await _get_client()
    result = await client.recall(query, dataset_name=POLICY_DATASET)
    return _flatten(result)


async def recall_history(department: str, vendor_status: str) -> str:
    """Pull prior decisions relevant to this department/vendor."""
    client = await _get_client()
    query = f"Past procurement decisions for department {department} with vendor status {vendor_status}"
    result = await client.recall(query, dataset_name=HISTORY_DATASET)
    return _flatten(result)


async def improve() -> None:
    """Post-ingestion enrichment (memify)."""
    client = await _get_client()
    try:
        await client.improve(dataset=HISTORY_DATASET)
    except RuntimeError as e:
        if "404" in str(e):
            print("Note: improve() endpoint not yet available on this Cognee Cloud tenant, skipping.")
        else:
            raise


async def forget_stale_history() -> dict:
    """Surgically prune the history dataset when it's no longer needed."""
    client = await _get_client()
    try:
        await client.forget(dataset=HISTORY_DATASET)
        return {"status": "history pruned"}
    except RuntimeError as e:
        if "404" in str(e):
            return {"status": "forget endpoint not yet available on this tenant"}
        raise


def _flatten(result: Any) -> str:
    if not result:
        return ""
    if isinstance(result, str):
        return result
    try:
        return "\n".join(str(r) for r in result)
    except Exception:
        return str(result)


if __name__ == "__main__":

    async def _smoke_test():
        print("Remembering a policy...")
        await remember_policy(
            "Software purchases over 5000 USD require finance approval. "
            "All software purchases require a security review regardless of amount."
        )

        print("Remembering a past decision...")
        await remember_decision(
            department="Engineering",
            vendor_status="unapproved",
            item_type="software",
            request_id="REQ-TEST-001",
            decision_summary="Denied -- unapproved vendor, routed to security for vendor onboarding review.",
        )

        print("Recalling policy for a new software request...")
        policy = await recall_policy("software purchase over budget")
        print("POLICY RECALL:\n", policy)

        print("Recalling history for Engineering + unapproved vendor...")
        history = await recall_history("Engineering", "unapproved")
        print("HISTORY RECALL:\n", history)

        print("Running improve()...")
        await improve()

        print("Done.")

    asyncio.run(_smoke_test())
