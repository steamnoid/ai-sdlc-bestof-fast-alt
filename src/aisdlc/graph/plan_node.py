"""The planning node: the run's second piece of reasoning, after a person approved the first.

Identical in shape to the discovery node and for the same reasons: the model answers first, the
artifact is built from what it said, and the clone channel is checked before the node reads
anything — because a graph wired with planning before the clone would otherwise pass a `None`
along until something read an attribute off it.

**The plan is presented, not produced and forgotten.** As well as the channel this node writes
the artifact the gate will name, because a report sitting in the state is not something anybody
was asked to rule on. A run that planned and offered nothing would put an empty artifact in
front of a person and record their approval against it.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from langgraph.types import Command

from aisdlc.agents.artifact import Artifact
from aisdlc.agents.plan_the_change import PlannedTestDirectoryNotCollectedError
from aisdlc.agents.requirements import Requirements
from aisdlc.agents.what_the_planner_concluded import ImplementationPlanAnswer
from aisdlc.domain.repository import Repository
from aisdlc.graph.agent_state import WHAT_STOPPED_THIS_RUN, AgentState
from aisdlc.graph.clone_node import TheRepositoryHasNotBeenClonedYetError
from aisdlc.graph.pickup_node import THE_DEVELOPER_PLANNING_AGENT
from aisdlc.graph.supervise_a_repair import (
    WHERE_THE_SUPERVISOR_DECIDES_WHETHER_TO_REPAIR,
)
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.what_people_said_about_a_work_item import a_comment_was_left

# **What the repository's runner says it collects, and not a model.** The fourth argument is the
# runner's own announcement, because a test's directory has to be one the suite will look in, and
# that is a fact about the runner rather than something this system or the model may decide. The
# seam has no `model` for the same reason it has this: neither value belongs to the stage's input
# state, and `test_the_planner_seam_and_the_planner_name_the_same_arguments` compares the two lists
# so a parameter cannot be added to one and forgotten in the other.
PlanTheChange = Callable[
    [Requirements, ClonedRepository, Repository, str], ImplementationPlanAnswer
]

# What the suite is known to collect when nobody has asked it. Empty rather than a default glob,
# because a default would be this system deciding what a repository's runner looks at, and
# `plan_the_change` reads emptiness as "ask nothing" for the reason the column rule does: a
# fallback is a lie with a position.
THE_RUNNER_ANNOUNCED_NOTHING_YET = ""



class ThePlanHasNoApprovedRequirementsError(Exception):
    """The rule is in this module, and it may say the rule broke.

    The glossary says `aisdlc-dev-plan` *converts approved requirements* into a plan, so a
    requirements set is this stage's input and not the discovery report it started from before
    the analysis stages sat between them. Refused rather than planning from whatever is
    available, because a plan built from the discovery report is a reasonable-looking plan
    about the wrong document and nothing downstream of it can tell.
    """

    def __init__(self, why: str) -> None:
        """Say which artifact wanted the requirements, and what this run has instead."""
        super().__init__(
            f"{Artifact.IMPLEMENTATION_PLAN} is planned from the approved requirements, and "
            f"this run has none. {why}"
        )


def plan_the_change_in_this_run(state: AgentState, plan: PlanTheChange) -> Command | dict:
    """The plan for the change this run was commissioned to make, and the artifact to present.

    **The version is the number of times the planning agent has worked on this work item**, and
    the counting is done by the pickup and carried by `transition()` rather than kept here, so a
    node cannot claim a version. It used to be fixed at one, on the reasoning that a counter saying
    "how many times this run happened" would not be a version an approval could be invalidated
    against -- and the run that put an agent back on a work item was the reason that was wrong: the
    plan written on the agent's second turn is a different artifact, presented at the version a
    person had already approved, and `Approval.applies_to` could not tell the two apart.
    """
    clone = state["clone"]

    if clone is None:
        raise TheRepositoryHasNotBeenClonedYetError(
            f"{Artifact.IMPLEMENTATION_PLAN} reads the repository from the clone, and this "
            "run has none yet. The clone node is wired after the planning node."
        )

    requirements = state["requirements"]

    if requirements is None:
        raise ThePlanHasNoApprovedRequirementsError(
            "The planning stage is reached only through the router, and the router sends it "
            "an approved artifact."
        )

    how_many_versions_the_planning_agent_has_written = state[
        "work_item"
    ].work_done.how_many_times_this_agent_has_worked(THE_DEVELOPER_PLANNING_AGENT)

    try:
        what_the_planning_agent_concluded = plan(
            requirements,
            clone,
            state["work_item"].repository,
            THE_RUNNER_ANNOUNCED_NOTHING_YET,
        )
    except PlannedTestDirectoryNotCollectedError as repairable:
        # **Named, not `except Exception`, and the naming is the declaration.** This node says a
        # refusal of this kind is one it can hand on: a plan whose test is in a directory the
        # repository does not collect is a plan that was wrong about the repository, and a
        # planner that reads the runner's `include` is the one that can fix it.
        return Command(
            goto=WHERE_THE_SUPERVISOR_DECIDES_WHETHER_TO_REPAIR,
            update={WHAT_STOPPED_THIS_RUN: str(repairable)},
        )

    a_comment_was_left(
        state["work_item"],
        what_was_said=what_the_planning_agent_concluded.judged.the_text_of_the_note_this_is(),
        by=THE_DEVELOPER_PLANNING_AGENT,
        at=datetime.now(UTC),
        projects_root=state["projects_root"],
    )

    return {
        "implementation_plan": what_the_planning_agent_concluded.plan,
        "presented_artifact_id": Artifact.IMPLEMENTATION_PLAN,
        "presented_artifact_version": how_many_versions_the_planning_agent_has_written,
    }
