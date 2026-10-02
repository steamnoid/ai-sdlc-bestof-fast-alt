"""The discovery node: the run's one piece of reasoning before the gate."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aisdlc.agents.artifact import Artifact
from aisdlc.agents.discovery_answer import DiscoveryAnswer
from aisdlc.agents.discovery_report import DiscoveryReport
from aisdlc.domain.repository import Repository
from aisdlc.graph.agent_state import AgentState
from aisdlc.graph.clone_node import TheRepositoryHasNotBeenClonedYetError
from aisdlc.graph.pickup_node import THE_DISCOVER_AGENT
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.what_people_said_about_a_work_item import a_comment_was_left

Discover = Callable[
    [ClonedRepository, Repository], tuple[DiscoveryReport, DiscoveryAnswer]
]

ITS_FIRST_VERSION = 1


def discover_the_repository_in_this_run(state: AgentState, discover: Discover) -> dict:
    """What the run learned about the repository, and the artifact the gate will present.

    Both halves, because they are different facts. A report sitting in the state is not
    an artifact anybody has been asked to rule on: the gate presents
    `presented_artifact_id` and its version, and a run that kept its report and offered
    nothing would put an empty artifact in front of a person and record their approval
    against it.

    The version is fixed at one because the report is written afresh by every run and
    nothing has ever written a second version of it. Inventing an incrementing counter
    would be a version that means "how many times this run happened", which is not what
    an approval needs to be invalidated.
    """
    clone = state["clone"]

    if clone is None:
        raise TheRepositoryHasNotBeenClonedYetError(
            f"{Artifact.DISCOVERY_REPORT} reads the repository from the clone, and "
            "this run has none yet. The clone node is wired after the discovery node."
        )

    report, what_the_discovery_agent_concluded = discover(
        clone, state["work_item"].repository
    )

    a_comment_was_left(
        state["work_item"],
        what_was_said=what_the_discovery_agent_concluded.judged.the_text_of_the_note_this_is(),
        by=THE_DISCOVER_AGENT,
        at=datetime.now(UTC),
        projects_root=state["projects_root"],
    )

    return {
        "discovery_report": report,
        "presented_artifact_id": Artifact.DISCOVERY_REPORT,
        "presented_artifact_version": ITS_FIRST_VERSION,
    }
