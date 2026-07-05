import os

# Must be set BEFORE importing cognee
os.environ.setdefault("COGNEE_SERVICE_URL", "https://tenant-81f70461-f8df-4863-9627-6edd07e08aca.aws.cognee.ai")

import asyncio
from typing import Any, Optional

import cognee

POLICY_DATASET = "procurement_policies"
HISTORY_DATASET = "procurement_history"

RECALL_TIMEOUT_SECONDS = 90.0

CLIENT_INIT_TIMEOUT_SECONDS = 90.0

_client = None


async def _get_client():
    global _client
    if _client is None:
        assert os.environ.get("COGNEE_API_KEY"), (
            "COGNEE_API_KEY not set. Add it as a Codespaces secret from "
            "https://platform.cognee.ai/sign-in"
        )
        try:
            _client = await asyncio.wait_for(cognee.serve(), timeout=CLIENT_INIT_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"cognee.serve() did not respond within {CLIENT_INIT_TIMEOUT_SECONDS}s -- "
                "check COGNEE_API_KEY / COGNEE_SERVICE_URL and Cognee Cloud status."
            )
    return _client


async def remember_policy(text: str) -> None:
    client = await _get_client()
    await client.remember(text, dataset_name=POLICY_DATASET)


async def remember_decision(department, vendor_status, item_type, request_id, decision_summary):
    client = await _get_client()
    entry = (
        f"Request {request_id} | Department: {department} | "
        f"Vendor status: {vendor_status} | Item type: {item_type} | "
        f"Outcome: {decision_summary}"
    )
    await client.remember(entry, dataset_name=HISTORY_DATASET)


async def recall_policy(query: str) -> str:
    client = await _get_client()
    try:
        result = await asyncio.wait_for(
            client.recall(query, dataset_name=POLICY_DATASET),
            timeout=RECALL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return "(policy recall timed out after 20s -- Cognee may be slow to respond right now)"
    return _flatten(result)


async def recall_history(department: str, vendor_status: str) -> str:
    client = await _get_client()
    query = f"Past procurement decisions for department {department} with vendor status {vendor_status}"
    try:
        result = await asyncio.wait_for(
            client.recall(query, dataset_name=HISTORY_DATASET),
            timeout=RECALL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return "(history recall timed out after 20s -- Cognee may be slow to respond right now)"
    return _flatten(result)


async def improve() -> None:
    client = await _get_client()
    try:
        await client.improve(dataset=HISTORY_DATASET)
    except RuntimeError as e:
        if "404" in str(e):
            print("Note: improve() not yet available on this tenant, skipping.")
        else:
            raise


async def forget_stale_history() -> dict:
    client = await _get_client()
    try:
        await client.forget(dataset=HISTORY_DATASET)
        return {"status": "history pruned"}
    except RuntimeError as e:
        if "404" in str(e):
            return {"status": "forget endpoint not yet available on this tenant"}
        raise


def _flatten(result) -> str:
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
        print("Recalling policy...")
        policy = await recall_policy("software purchase over budget")
        print("POLICY RECALL:\n", policy)
        print("Recalling history...")
        history = await recall_history("Engineering", "unapproved")
        print("HISTORY RECALL:\n", history)
        print("Done.")

    asyncio.run(_smoke_test())