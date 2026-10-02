"""The QA analyst's node: the run's first stage that reasons about a *decision*.

Every other node in this graph reads the clone, because every other one is asked a question
about code. This one is not: §10 gives the QA analyst `analyze requirements` and the glossary
has it converting `Requirements` into a `QaPlan`, so what it is handed is an artifact a person
already approved.

**That is a different kind of work item, and the node is shaped by it rather than by
similarity.** A QA plan is made from a decision, so this node has everything it needs the
moment the requirements gate is behind it — no clone is read and none is required, and
`test_the_qa_analyst_needs_no_clone_because_it_reads_the_requirements_not_the_code` holds that
so a later change cannot quietly copy the other three's checkout check in here.

The consequence for a reader is worth stating plainly: **a QA plan is a judgement about whether
the work is specified well, not about whether the code works.** A missing requirement produces
an ambiguity in the plan rather than a failing test, and the verification that follows cannot
check what nobody wrote down. That is the pipeline's shape, not this node's choice.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aisdlc.agents.artifact import Artifact
from aisdlc.agents.qa_plan import QaPlan
from aisdlc.agents.qa_plan_answer import QaPlanAnswer
from aisdlc.agents.requirements import Requirements
from aisdlc.graph.agent_state import AgentState
from aisdlc.graph.pickup_node import THE_QA_ANALYST_AGENT
from aisdlc.tools.what_people_said_about_a_work_item import a_comment_was_left

AnalyzeTheRequirements = Callable[[Requirements], tuple[QaPlan, QaPlanAnswer]]

ITS_FIRST_VERSION = 1


class RequirementsHaveNotBeenApprovedYetError(Exception):
    """The rule is in this module, and it may say the rule broke.

    Raised rather than a `None` carried onward, because a QA plan planned from nothing is a
    plan that looks finished: the person at the gate would approve a document about testing
    that was written about no requirements at all, and the record would say a human had ruled
    on it.
    """

    def __init__(self, why: str) -> None:
        """Say which artifact wanted the requirements, and what this run has instead."""
        super().__init__(
            f"{Artifact.QA_PLAN} is planned from the approved "
            f"requirements, and this run has none. {why} A plan planned from nothing looks "
            "the same as a plan planned from something, and a person cannot tell them apart."
        )


def analyze_the_requirements_in_this_run(
    state: AgentState, analyze: AnalyzeTheRequirements
) -> dict:
    """The QA plan for the requirements a person approved, and the artifact to present.

    Both halves, because they are different facts. A plan in the state is not an artifact
    anybody was asked to rule on: the gate presents `presented_artifact_id` and its version,
    and a run that kept its plan and offered nothing would put an empty artifact in front of a
    person and record their approval against it.

    The version is fixed at one for the same reason every stage's is: nothing has written a
    second version of a `QaPlan`, and a counter that said "how many times this run happened"
    would not be a version an approval could be invalidated by.
    """
    requirements = state["requirements"]

    if requirements is None:
        raise RequirementsHaveNotBeenApprovedYetError(
            f"The {Artifact.QA_PLAN} stage is reached only through the "
            "router, and the router sends it an approved artifact."
        )

    plan, what_the_analyst_concluded = analyze(requirements)

    a_comment_was_left(
        state["work_item"],
        what_was_said=what_the_analyst_concluded.judged.the_text_of_the_note_this_is(),
        by=THE_QA_ANALYST_AGENT,
        at=datetime.now(UTC),
        projects_root=state["projects_root"],
    )

    return {
        "qa_plan": plan,
        "presented_artifact_id": Artifact.QA_PLAN,
        "presented_artifact_version": ITS_FIRST_VERSION,
    }
