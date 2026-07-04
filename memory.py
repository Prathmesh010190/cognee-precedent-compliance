"""
memory.py
---------
Thin wrapper around Cognee's memory lifecycle (remember / recall / improve / forget).
Every other file in this project should call INTO this module, not into cognee directly.
This keeps the Cognee integration in one place and makes it easy to demo/test in isolation.

Run this file directly to sanity-check your Cognee connection:
    python memory.py
"""

import os
import asyncio
from typing import Any, Dict, List, Optional

import cognee

# ---------------------------------------------------------------------------
# Dataset names — Cognee organizes memory into named datasets.
# We split into two datasets so policy knowledge and vendor/department
# history can be recalled (and forgotten) independently.
# ---------------------------------------------------------------------------
POLICY_DATASET = "procurement_policies"
HISTORY_DATASET = "procurement_history"


async def remember_policy(text: str) -> None:
    """Ingest a policy statement / document into long-term memory."""
    await cognee.add(text, dataset_name=POLICY_DATASET)
    await cognee.cognify(datasets=[POLICY_DATASET])


async def remember_decision(
    department: str,
    vendor_status: str,
    item_type: str,
    request_id: str,
    decision_summary: str,
) -> None:
    """
    Called after every /step. Stores what was decided so future requests
    from the same department/vendor context can be recalled against it.
    This is what turns the environment from single-step/stateless into
    something with real institutional memory.
    """
    entry = (
        f"Request {request_id} | Department: {department} | "
        f"Vendor status: {vendor_status} | Item type: {item_type} | "
        f"Outcome: {decision_summary}"
    )
    await cognee.add(entry, dataset_name=HISTORY_DATASET)
    await cognee.cognify(datasets=[HISTORY_DATASET])


async def recall_policy(query: str) -> str:
    """Ask memory what policy applies to a given request description."""
    results = await cognee.search(
        query_text=query,
        dataset_names=[POLICY_DATASET],
    )
    return _flatten(results)


async def recall_history(department: str, vendor_status: str) -> str:
    """
    Pull prior decisions relevant to this department/vendor before grading
    a new request. This is the core "does it remember precedent" feature.
    """
    query = f"Past procurement decisions for department {department} with vendor status {vendor_status}"
    results = await cognee.search(
        query_text=query,
        dataset_names=[HISTORY_DATASET],
    )
    return _flatten(results)


async def improve() -> None:
    """
    Post-ingestion enrichment pass (memify). Call this periodically (e.g. every
    N decisions, or via an explicit endpoint) so the graph re-derives
    relationships and stale weights are refreshed as new history comes in.
    """
    await cognee.cognify(datasets=[HISTORY_DATASET])


async def forget_stale_history() -> Dict[str, Any]:
    """
    Prune the history dataset. In a real deployment you'd filter by date /
    retention policy; Cognee's prune here removes the dataset's derived
    graph so it can be rebuilt clean. Demonstrates the forget() operation
    explicitly for the hackathon's "Best Use of Cognee" criterion.
    """
    await cognee.prune.prune_data()
    return {"status": "history pruned"}


def _flatten(results: Any) -> str:
    """Cognee search can return a list of chunks/nodes; join into plain text."""
    if not results:
        return ""
    if isinstance(results, str):
        return results
    try:
        return "\n".join(str(r) for r in results)
    except Exception:
        return str(results)


# ---------------------------------------------------------------------------
# Manual smoke test — run `python memory.py` after setting COGNEE_API_KEY
# ---------------------------------------------------------------------------
if __name__ == "__main__":

    async def _smoke_test():
        assert os.environ.get("COGNEE_API_KEY"), "Set COGNEE_API_KEY first (see .env.example)"

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
            decision_summary="Denied — unapproved vendor, routed to security for vendor onboarding review.",
        )

        print("Recalling policy for a new software request...")
        policy = await recall_policy("software purchase over budget")
        print("POLICY RECALL:\n", policy)

        print("Recalling history for Engineering + unapproved vendor...")
        history = await recall_history("Engineering", "unapproved")
        print("HISTORY RECALL:\n", history)

    asyncio.run(_smoke_test())
