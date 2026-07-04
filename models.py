from typing import List, Optional
from pydantic import BaseModel


class ProcurementAction(BaseModel):
    policy_compliance: str
    approval_decision: str
    risk_level: str
    route_to: str | list[str]
    missing_requirements: List[str]


class ProcurementObservation(BaseModel):
    done: bool
    reward: Optional[float] = None
    request_id: str
    department: str
    requestor_role: str
    item_type: str
    item_description: str
    amount_usd: float
    budget_remaining_usd: float
    vendor_status: str
    manager_approval: bool
    finance_approval: bool
    security_review: bool
    urgency: str
    policy_notes: str
    difficulty: str
    allowed_actions: List[str]
    message: str
    memory_context: Optional[str] = None


class ProcurementState(BaseModel):
    episode_id: str = ""
    step_count: int = 0
    current_task_id: str = ""
    difficulty: str = ""
    expected_policy_compliance: str = ""
    expected_approval_decision: str = ""
    expected_risk_level: str = ""
    expected_route_to: list[str] | str = []
    expected_missing_requirements: List[str] = []
    score_so_far: float = 0.0
    completed: bool = False