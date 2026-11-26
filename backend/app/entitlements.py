"""Server-side feature entitlements derived from the verified subscription."""
from __future__ import annotations

from dataclasses import dataclass

SYNDICATE_PLAN_CODES = frozenset({
    "SYNDICAT_5_ACCES",
    "SYNDICAT_10_ACCES",
    "SYNDICAT_15_ACCES",
})
ACTIVE_SUBSCRIPTION_STATUSES = frozenset({"ACTIVE", "TRIAL"})
AGENT_DAILY_QUESTION_LIMIT = 5


@dataclass(frozen=True)
class Entitlements:
    chatbot: bool
    syndicate_tools: bool
    daily_question_limit: int | None
    max_users: int


def resolve_entitlements(
    plan_code: str | None,
    subscription_status: str | None,
    *,
    founder: bool = False,
) -> Entitlements:
    """Fail closed: only active current union plans unlock syndicate features."""
    if founder:
        return Entitlements(True, True, None, 15)

    if (
        plan_code in SYNDICATE_PLAN_CODES
        and subscription_status in ACTIVE_SUBSCRIPTION_STATUSES
    ):
        seats = {
            "SYNDICAT_5_ACCES": 5,
            "SYNDICAT_10_ACCES": 10,
            "SYNDICAT_15_ACCES": 15,
        }[plan_code]
        return Entitlements(True, True, None, seats)

    # No subscription, expired subscription and all retired plans fall back
    # to the individual-agent product: chatbot only, five questions per day.
    return Entitlements(True, False, AGENT_DAILY_QUESTION_LIMIT, 1)
