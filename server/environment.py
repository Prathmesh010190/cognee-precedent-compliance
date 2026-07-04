import asyncio
import json
import random
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from models import ProcurementAction, ProcurementObservation, ProcurementState
import memory as cognee_memory


class ProcurementComplianceEnvironment:
    SUPPORTS_CONCURRENT_SESSIONS = True

    # Difficulty multipliers — makes scores DIFFERENT per task
    DIFFICULTY_WEIGHTS = {
        "easy": 0.90,
        "medium": 0.95,
        "hard": 1.00,
    }

    def __init__(self):
        self.tasks = self._load_tasks()
        self.current_task: Optional[Dict[str, Any]] = None
        self._state = ProcurementState()
        self._completed = False

    def _load_tasks(self) -> List[Dict[str, Any]]:
        data_path = Path(__file__).resolve().parent.parent / "data" / "tasks.json"
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_task_ids(self) -> List[str]:
        """Return all available task IDs."""
        return [task["id"] for task in self.tasks]

    def reset(self, seed=None, episode_id=None, task_id=None, **kwargs) -> ProcurementObservation:
        if seed is not None:
            random.seed(seed)

        if task_id is not None:
            matching_tasks = [task for task in self.tasks if task["id"] == task_id]
            if not matching_tasks:
                raise ValueError(f"Task ID not found: {task_id}")
            self.current_task = matching_tasks[0]
        else:
            self.current_task = random.choice(self.tasks)

        expected = self.current_task["expected_output"]

        self._state = ProcurementState(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            current_task_id=self.current_task["id"],
            difficulty=self.current_task["difficulty"],
            expected_policy_compliance=expected["policy_compliance"],
            expected_approval_decision=expected["approval_decision"],
            expected_risk_level=expected["risk_level"],
            expected_route_to=expected["route_to"],
            expected_missing_requirements=expected["missing_requirements"],
            score_so_far=0.0,
            completed=False,
        )
        self._completed = False

        request = self.current_task["request"]

        # --- Cognee: recall precedent before the agent sees the request ---
        # This is what makes decisions precedent-aware instead of single-shot.
        # Falls back silently to "" if Cognee isn't configured yet, so the
        # environment still works with zero API keys set (useful for local dev).
        memory_context = self._safe_run(
            self._gather_memory_context(request)
        )

        return ProcurementObservation(
            done=False,
            reward=None,
            request_id=request["request_id"],
            department=request["department"],
            requestor_role=request["requestor_role"],
            item_type=request["item_type"],
            item_description=request["item_description"],
            amount_usd=request["amount_usd"],
            budget_remaining_usd=request["budget_remaining_usd"],
            vendor_status=request["vendor_status"],
            manager_approval=request["manager_approval"],
            finance_approval=request["finance_approval"],
            security_review=request["security_review"],
            urgency=request["urgency"],
            policy_notes=request["policy_notes"],
            difficulty=self.current_task["difficulty"],
            allowed_actions=["submit_decision"],
            message="Review this procurement request and submit a compliance decision.",
            memory_context=memory_context,
        )

    async def _gather_memory_context(self, request: Dict[str, Any]) -> str:
        policy = await cognee_memory.recall_policy(request["item_description"])
        history = await cognee_memory.recall_history(
            request["department"], request["vendor_status"]
        )
        parts = []
        if policy:
            parts.append(f"[Recalled policy]\n{policy}")
        if history:
            parts.append(f"[Recalled history]\n{history}")
        return "\n\n".join(parts)

    @staticmethod
    def _safe_run(coro) -> str:
        """Run an async Cognee call from sync FastAPI code; never crash the request on memory errors."""
        try:
            return asyncio.run(coro)
        except Exception as e:
            return f"(memory unavailable: {e})"

    def step(self, action: ProcurementAction, timeout_s=None, **kwargs) -> ProcurementObservation:
        if self.current_task is None:
            raise ValueError("Environment has not been reset. Call reset() first.")

        if self._completed:
            raise ValueError("Episode already completed. Call reset() to start a new episode.")

        self._state.step_count += 1

        expected = self.current_task["expected_output"]

        try:
            reward = self._grade_action(action, expected)
        except Exception:
            reward = 0.01

        self._state.score_so_far = reward
        self._state.completed = True
        self._completed = True

        request = self.current_task["request"]

        # --- Cognee: remember this outcome so future requests from the same
        # department/vendor can recall it as precedent. ---
        decision_summary = (
            f"policy_compliance={action.policy_compliance}, "
            f"approval_decision={action.approval_decision}, "
            f"risk_level={action.risk_level}, score={reward:.2f}"
        )
        self._safe_run(
            cognee_memory.remember_decision(
                department=request["department"],
                vendor_status=request["vendor_status"],
                item_type=request["item_type"],
                request_id=request["request_id"],
                decision_summary=decision_summary,
            )
        )

        return ProcurementObservation(
            done=True,
            reward=reward,
            request_id=request["request_id"],
            department=request["department"],
            requestor_role=request["requestor_role"],
            item_type=request["item_type"],
            item_description=request["item_description"],
            amount_usd=request["amount_usd"],
            budget_remaining_usd=request["budget_remaining_usd"],
            vendor_status=request["vendor_status"],
            manager_approval=request["manager_approval"],
            finance_approval=request["finance_approval"],
            security_review=request["security_review"],
            urgency=request["urgency"],
            policy_notes=request["policy_notes"],
            difficulty=self.current_task["difficulty"],
            allowed_actions=["submit_decision"],
            message=f"Decision submitted. Final score: {reward:.4f}",
        )

    def state(self) -> ProcurementState:
        return self._state

    # ------------------------------------------------------------------
    # GRADER — deterministic, weighted partial credit, difficulty-aware
    # ------------------------------------------------------------------
    def _grade_action(self, action: ProcurementAction, expected: Dict[str, Any]) -> float:
        raw_score = 0.0
        max_possible = 0.0

        # --- 1. policy_compliance (weight 0.25) ---
        weight = 0.25
        max_possible += weight
        try:
            act_val = str(action.policy_compliance or "").strip().lower()
            exp_val = str(expected.get("policy_compliance", "")).strip().lower()
            if act_val and exp_val and act_val == exp_val:
                raw_score += weight
        except Exception:
            pass

        # --- 2. approval_decision (weight 0.25) ---
        weight = 0.25
        max_possible += weight
        try:
            act_val = str(action.approval_decision or "").strip().lower()
            exp_val = str(expected.get("approval_decision", "")).strip().lower()
            if act_val and exp_val and act_val == exp_val:
                raw_score += weight
        except Exception:
            pass

        # --- 3. risk_level (weight 0.15) ---
        weight = 0.15
        max_possible += weight
        try:
            act_val = str(action.risk_level or "").strip().lower()
            exp_val = str(expected.get("risk_level", "")).strip().lower()
            if act_val and exp_val and act_val == exp_val:
                raw_score += weight
        except Exception:
            pass

        # --- 4. route_to (weight 0.20) — set-based partial credit ---
        weight = 0.20
        max_possible += weight
        try:
            exp_route = set(expected.get("route_to") or [])
            act_route = set(action.route_to or [])
            if not exp_route and not act_route:
                raw_score += weight
            elif exp_route:
                overlap = len(exp_route.intersection(act_route))
                denominator = max(len(exp_route), len(act_route))
                if denominator > 0:
                    raw_score += weight * (overlap / denominator)
            # If expected is empty but agent submitted routes: 0 points (false positives)
        except Exception:
            pass

        # --- 5. missing_requirements (weight 0.15) — set-based partial credit ---
        weight = 0.15
        max_possible += weight
        try:
            exp_missing = set(expected.get("missing_requirements") or [])
            act_missing = set(action.missing_requirements or [])
            if not exp_missing and not act_missing:
                raw_score += weight
            elif exp_missing:
                overlap = len(exp_missing.intersection(act_missing))
                # Penalize for false positives too
                if len(act_missing) > 0:
                    precision = overlap / len(act_missing)
                else:
                    precision = 0.0
                recall = overlap / len(exp_missing)
                # F1-like score
                if precision + recall > 0:
                    f1 = 2 * (precision * recall) / (precision + recall)
                else:
                    f1 = 0.0
                raw_score += weight * f1
            # If expected is empty but agent submitted missing reqs: 0 points
        except Exception:
            pass

        # --- Apply difficulty multiplier for score variation ---
        difficulty = self.current_task.get("difficulty", "medium")
        diff_weight = self.DIFFICULTY_WEIGHTS.get(difficulty, 0.95)

        # Number of expected fields that are non-trivial (lists with items)
        complexity_bonus = 0.0
        exp_route_len = len(expected.get("route_to") or [])
        exp_missing_len = len(expected.get("missing_requirements") or [])
        total_expected_items = exp_route_len + exp_missing_len

        if total_expected_items > 0:
            # More complex tasks get a tiny bonus for getting them right
            complexity_bonus = min(0.03, total_expected_items * 0.005)

        # Final score with variation
        final_score = (raw_score * diff_weight) + (complexity_bonus if raw_score > 0.5 else 0.0)

        # Round and clamp strictly between 0 and 1
        final_score = round(final_score, 4)
        final_score = max(0.01, min(0.98, final_score))
        return final_score