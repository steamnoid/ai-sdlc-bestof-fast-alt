"""The implementation node: the run's change, and the suite run around it.

**Writing and verifying are one node, and the reason is the window.** §10 gives the
implementation agent three responsibilities — implement the approved plan, modify the
repository, run the tests — and if the writing and the running were two nodes then a person
or a process could edit the checkout between them, and the verification would be of a
repository this system did not produce. The suite has to be run *around* the change, so the
two halves belong to the same node.

**The clone is checked first, as in the other two reading nodes.** A graph wired with
implementation before the clone would otherwise hand a `None` to a collaborator that is about
to write files into it, which is a different failure from the one the refusal names.

**Both results go into the state, and both are written out.** What was written is the record
of the change, and the verification is the record of what the suite said about it; a run that
kept the first and dropped the second would have a change nobody checked.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from langgraph.types import Command

from aisdlc.agents.apply_the_plan import ADeliveredChange
from aisdlc.agents.artifact import Artifact
from aisdlc.agents.implement_the_plan import AWriteThatChangesNothingError
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.domain.repository import Repository
from aisdlc.graph.agent_state import WHAT_STOPPED_THIS_RUN, AgentState
from aisdlc.graph.clone_node import TheRepositoryHasNotBeenClonedYetError
from aisdlc.graph.pickup_node import THE_DEVELOPER_IMPLEMENTATION_AGENT
from aisdlc.graph.supervise_a_repair import (
    WHERE_THE_SUPERVISOR_DECIDES_WHETHER_TO_REPAIR,
)
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.what_people_said_about_a_work_item import a_comment_was_left
from aisdlc.verify_the_change import (
    AnUnrunTestError,
    ATestThatPassesWithoutTheChangeError,
)

ApplyAndVerify = Callable[
    [ClonedRepository, Repository, ImplementationPlan], ADeliveredChange
]

ITS_FIRST_VERSION = 1

WHERE_THE_VERIFICATION_IS_WRITTEN = "write_what_the_change_says"
"""The node this one hands to on success, named here because it is part of what this node does.

**Both outcomes of this node name their own destination, and there is no edge out of it.** That
is not a style preference; it is the fix for a defect a whole run found. This node returned a
plain state update on success and a `Command(goto=...)` on a repairable refusal, while the graph
also carried a static edge from it to the next node. A `Command`'s `goto` and a static edge out of
the same node both fire, so a refusal did not divert the run — the run went to the supervisor
*and* carried on down the ordinary path, and the two arrived at the same node in the same step
and both wrote `requested_stage`. LangGraph refused it:

    At key 'requested_stage': Can receive only one value per step.

So **every repair in this system crashed the run**, at the moment the repair was being performed,
with a message about concurrent writes rather than about the repair. Every refusal-routing test
here passed, because they call the function and read the `Command` it returns; none of them
builds the graph, and the defect was entirely in the wiring.
"""


def apply_and_verify_in_this_run(
    state: AgentState, apply_and_verify: ApplyAndVerify
) -> Command:
    """The change the approved plan asked for, the suite's answer to it, and what to present.

    The presented artifact is the **verification**, not the change. A person is being asked
    whether the change is fit, and what they can read is what the suite said about it plus the
    files it touched — so the artifact they rule on is the evidence rather than the edit.
    """
    clone = state["clone"]
    plan = state["implementation_plan"]

    if clone is None or plan is None:
        raise TheRepositoryHasNotBeenClonedYetError(
            f"{Artifact.VERIFICATION_REPORT} writes into the clone and implements "
            f"{Artifact.IMPLEMENTATION_PLAN}, and this run has not reached either yet. The "
            "implementation node is wired before the clone or the plan."
        )

    try:
        delivered = apply_and_verify(clone, state["work_item"].repository, plan)
    except (
        ATestThatPassesWithoutTheChangeError,
        AWriteThatChangesNothingError,
        AnUnrunTestError,
    ) as repairable:
        # **Named, not `except Exception`, and the naming is the declaration.** This node says a
        # refusal of this kind is one it can hand on. A node catching everything would make the
        # supervisor the place a run goes when anything goes wrong, and a repair that repairs a
        # work item nobody commissioned is a circle.
        #
        # **The second name was added by a real run, and it is the most repairable of the three.**
        # Asked to change the Dockerfile's healthcheck interval, the planner named the Dockerfile
        # and the implementer wrote it back byte-for-byte, keeping `--interval=30s` — a refusal of
        # exactly the kind this mechanism exists for, and the one where the answer is most clearly
        # "the implementer was wrong, because the plan named the file and said what to change in
        # it". It killed the run instead, because this `except` named only the other one. So the
        # gap was not that the refusal was unhandled; it was that the run stopped on a question it
        # had built a reader for.
        return Command(
            goto=WHERE_THE_SUPERVISOR_DECIDES_WHETHER_TO_REPAIR,
            update={WHAT_STOPPED_THIS_RUN: str(repairable)},
        )

    a_comment_was_left(
        state["work_item"],
        what_was_said=delivered.what_the_implementer_said,
        by=THE_DEVELOPER_IMPLEMENTATION_AGENT,
        at=datetime.now(UTC),
        projects_root=state["projects_root"],
    )

    return Command(
        goto=WHERE_THE_VERIFICATION_IS_WRITTEN,
        update={
            "written_files": delivered.written,
            "verification_report": delivered.verification,
            "presented_artifact_id": Artifact.VERIFICATION_REPORT,
            "presented_artifact_version": ITS_FIRST_VERSION,
        },
    )
