"""The architecture analyst's node: what the code is shaped like, and the artifact to present.

Identical in shape to the product analyst's and for the same reasons: the clone channel is
checked before the node reads anything, the model answers first, and the artifact the gate will
name is written beside it — because a report sitting in the state is not something anybody was
asked to rule on.

**It reads the clone rather than the requirements, and that is §10's choice.** The
architecture agent's responsibilities are `analyze architecture`, `identify relevant modules`
and `identify dependencies`, which are questions about code; the QA analyst is the one agent
whose question is about a document. The distinction is the only thing separating this node
from `qa_node.py`, so it is stated here rather than left to a reader's inference from two
similar files.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aisdlc.agents.architecture_report import ArchitectureReport
from aisdlc.agents.architecture_report_answer import ArchitectureReportAnswer
from aisdlc.agents.artifact import Artifact
from aisdlc.domain.repository import Repository
from aisdlc.graph.agent_state import AgentState
from aisdlc.graph.clone_node import TheRepositoryHasNotBeenClonedYetError
from aisdlc.graph.pickup_node import THE_ARCHITECTURE_ANALYST_AGENT
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.what_people_said_about_a_work_item import a_comment_was_left

AnalyzeTheArchitecture = Callable[
    [ClonedRepository, Repository],
    tuple[ArchitectureReport, ArchitectureReportAnswer],
]

ITS_FIRST_VERSION = 1


def analyze_the_architecture_in_this_run(
    state: AgentState, analyze: AnalyzeTheArchitecture
) -> dict:
    """The architecture of the repository this run cloned, and the artifact to present.

    Both halves, because they are different facts. A report in the state is not an artifact
    anybody was asked to rule on: the gate presents `presented_artifact_id` and its version,
    and a run that kept its report and offered nothing would put an empty artifact in front of
    a person and record their approval against it.

    The version is fixed at one for the reason every stage's is: nothing has written a second
    version of an `ArchitectureReport`, and a counter that counted runs would not be a version
    an approval could be invalidated by.
    """
    clone = state["clone"]

    if clone is None:
        raise TheRepositoryHasNotBeenClonedYetError(
            f"{Artifact.ARCHITECTURE_REPORT} is reasoned about from the "
            "clone, and this run has none yet. The clone node is wired before the analyst "
            "node."
        )

    report, what_the_analyst_concluded = analyze(clone, state["work_item"].repository)

    a_comment_was_left(
        state["work_item"],
        what_was_said=what_the_analyst_concluded.judged.the_text_of_the_note_this_is(),
        by=THE_ARCHITECTURE_ANALYST_AGENT,
        at=datetime.now(UTC),
        projects_root=state["projects_root"],
    )

    return {
        "architecture_report": report,
        "presented_artifact_id": Artifact.ARCHITECTURE_REPORT,
        "presented_artifact_version": ITS_FIRST_VERSION,
    }
