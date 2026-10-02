"""Where a gate's answer sends the run next.

**This is the routing decision the lifecycle's own docstring said nobody had made.** It is
small because the transition table left nothing to choose: an approved artifact is followed by
the next piece of work the pipeline does, and `AWAITING_HUMAN_APPROVAL -> AWAITING_AGENT_PICKUP`
is the table's own edge. So no new stage and no new transition were added for any stage after
the first, which is the same argument the `READY` entry made for a work item's birth.

**The pipeline is declared here, in one place, in the order it happens.** A run reaches
`record_what_was_decided` once per gate, so one router answers for all of them and the
artifact is the only thing in the state that says which gate this was.
`the_lifecycle` hands this mapping's values to its conditional edge, so a route cannot be
returned without a destination to return *to* — the two cannot drift apart, and a later phase
that adds a stage adds a row here and inherits that guarantee.

**A refusal ends the run, and a refusal is not a fault.** The router reads the *answer* rather
than the record it left, because an answer says "no" and a record's absence says the same thing
less directly. Carrying on past a refusal would mean a work item a person rejected went on to be
planned, implemented and put in front of somebody as a pull request — with a record saying a
human had ruled on it.

The answer is read from the end of `decisions`, which is the answer to the gate that just ran:
a run is walked through several and the list is in the order they happened.

**A terminal artifact is not an error, and that distinction is why the error is named as it
is.** `VerificationReport` is routed to the end of the run because the `aisdlc-pr` agent is a
later phase and a stage invented to have somewhere to send it would be a future concept
implemented because the present graph wanted one. An artifact with no stage after it is
therefore exactly what a terminal artifact looks like, and an error named after a *missing
stage* would report a deliberate ending as a fault. The error is for an artifact nobody wrote
a rule for at all.
"""

from __future__ import annotations

from aisdlc.agents.artifact import Artifact
from aisdlc.graph.agent_state import AgentState
from aisdlc.graph.the_agents_a_run_reasons_with import (
    THE_DEVELOPER_IMPLEMENTATION_AGENT,
)

THE_RUN_IS_OVER = "write_how_this_run_ended"
THE_NEXT_ARTIFACT_IS_THE_PROPOSAL = "offer_the_work_item_to_the_product_analyst"
THE_NEXT_ARTIFACT_IS_THE_QA_PLAN = "offer_the_work_item_to_the_qa_analyst"
THE_NEXT_ARTIFACT_IS_THE_ARCHITECTURE = "offer_the_work_item_to_the_architecture_analyst"
THE_NEXT_ARTIFACT_IS_THE_SECURITY_REPORT = "offer_the_work_item_to_the_security_analyst"
THE_NEXT_ARTIFACT_IS_A_PLAN = "offer_the_work_item_to_the_planner"
THE_NEXT_ARTIFACT_IS_THE_CHANGE = "offer_the_work_item_to_the_implementer"
THE_NEXT_ARTIFACT_IS_THE_DELIVERY = "offer_the_work_item_to_the_pull_request_agent"
THE_APPROVED_DELIVERY_IS_PUSHED_AND_OPENED = "deliver_this_run"


class NoRouteIsDeclaredForThisArtifactError(Exception):
    """The rule is in `where_a_gate_outcome_leads`, and this may say it broke.

    Named after a missing *declaration*, not after a missing stage, and the difference is the
    whole point. A terminal artifact has no stage after it either, and that is not a fault:
    `VerificationReport` is routed to the end of the run on purpose. This error is for an
    artifact nobody wrote a rule for at all, which is a gap in the pipeline rather than a
    decision in it.
    """


# What each approved artifact leads to. This is the pipeline, and the router does nothing but
# look a run's artifact up in it — which is why there is no fall-through and why an artifact
# that is not here cannot be routed at all.
WHERE_AN_APPROVED_ARTIFACT_LEADS = {
    Artifact.DISCOVERY_REPORT: THE_NEXT_ARTIFACT_IS_THE_PROPOSAL,
    Artifact.REQUIREMENTS: THE_NEXT_ARTIFACT_IS_THE_QA_PLAN,
    Artifact.QA_PLAN: THE_NEXT_ARTIFACT_IS_THE_ARCHITECTURE,
    Artifact.ARCHITECTURE_REPORT: THE_NEXT_ARTIFACT_IS_THE_SECURITY_REPORT,
    Artifact.SECURITY_REPORT: THE_NEXT_ARTIFACT_IS_A_PLAN,
    Artifact.IMPLEMENTATION_PLAN: THE_NEXT_ARTIFACT_IS_THE_CHANGE,
    Artifact.VERIFICATION_REPORT: THE_NEXT_ARTIFACT_IS_THE_DELIVERY,
    Artifact.PULL_REQUEST_REQUEST: THE_APPROVED_DELIVERY_IS_PUSHED_AND_OPENED,
}


def a_repair_cleared_the_implementer(state: AgentState) -> bool:
    """Whether a supervisor answered this run and said the implementation needs no work.

    **`None` and an empty answer are not the same thing, and the difference is every run this
    pipeline has ever run.** A run that never asked a supervisor has no `repair` in its state, and
    treating that as a clearance would deliver an unimplemented change on the next run with nothing
    anywhere saying so. A supervisor that named nobody — which is a decision, and one `WhatToRepeat`
    allows — is also not a clearance: the verdict is about which stage was wrong, not about which
    stage is unnecessary.
    """
    the_repair = state.get("repair")
    if the_repair is None:
        return False

    return not any(
        verdict.agent == THE_DEVELOPER_IMPLEMENTATION_AGENT
        and verdict.must_repeat_its_work
        for verdict in the_repair.what_each_agent_must_do
    )


def where_a_gate_outcome_leads(state: AgentState) -> str:
    """The next node, from two facts: whether a person said yes, and what they said it about.

    A run reaches this only from `record_what_was_decided`, which raises when nobody
    answered and which has just appended the answer being read, so the list has one and it is
    the right one. That is the same division of labour as before: a missing answer is the
    recording node's refusal to raise, not this function's to invent.
    """
    if not state["decisions"][-1].approved:
        return THE_RUN_IS_OVER

    approved_artifact = state["presented_artifact_id"]

    # **A verdict that cleared the implementation sends the run to the delivery instead.**
    # `WhatToRepeat` asks the supervisor about every agent and the router is where an answer
    # becomes a destination, so this is the one place the verdict is honoured. Skipping the
    # implementation is a whole container suite run on each side of the change, plus a commit
    # attempt, for a stage nobody objected to.
    if approved_artifact == Artifact.IMPLEMENTATION_PLAN and a_repair_cleared_the_implementer(
        state
    ):
        return THE_APPROVED_DELIVERY_IS_PUSHED_AND_OPENED

    if approved_artifact not in WHERE_AN_APPROVED_ARTIFACT_LEADS:
        raise NoRouteIsDeclaredForThisArtifactError(
            f"{approved_artifact!r} was approved, and no route is declared for it. The "
            f"declared artifacts are {sorted(WHERE_AN_APPROVED_ARTIFACT_LEADS)}, and an "
            "artifact outside them is a gap in the pipeline rather than a decision in it. It "
            "is not read as a request to implement something."
        )

    return WHERE_AN_APPROVED_ARTIFACT_LEADS[approved_artifact]
