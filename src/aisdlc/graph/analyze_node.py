"""The product analyst's node: the run's second piece of reasoning, after discovery."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aisdlc.agents.artifact import Artifact
from aisdlc.agents.requirements import Requirements
from aisdlc.agents.requirements_answer import RequirementsAnswer
from aisdlc.domain.commissioned_request import CommissionedRequest
from aisdlc.domain.repository import Repository
from aisdlc.graph.agent_state import AgentState
from aisdlc.graph.clone_node import TheRepositoryHasNotBeenClonedYetError
from aisdlc.graph.pickup_node import THE_PRODUCT_ANALYST_AGENT
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.what_people_said_about_a_work_item import a_comment_was_left

Analyze = Callable[
    [ClonedRepository, Repository, CommissionedRequest | None],
    tuple[Requirements, RequirementsAnswer],
]

ITS_FIRST_VERSION = 1


def analyze_the_repository_in_this_run(state: AgentState, analyze: Analyze) -> dict:
    """What the run proposes, and the artifact the gate will present.

    Both halves, for discovery's reason and because they are different facts. A proposal in
    the state is not an artifact anybody was asked to rule on: the gate presents
    `presented_artifact_id` and its version, and a run that kept its proposal and offered
    nothing would put an empty artifact in front of a person and record their approval
    against it.

    The version is fixed at one for discovery's reason. Nothing has ever written a second
    version of a `Requirements`, and a counter that incremented per run would be a version
    meaning "how many times this run happened", which is not what an approval needs to be
    invalidated by.

    **An ambiguity the analyst found travels to the plan, and this node stops nobody.** For three
    changes the analyst used to refuse here, on a model's judgement about whether a question
    blocks the work -- and it refused a request naming its own test file because *the inspection
    does not show what `.gitignore` covers*, and a request to change one word because nobody said
    whether to keep the emoji after it. **Both were questions the implementer answers by opening a
    file.** The question itself is rendered into the planner's own prompt, marked where only a
    person can settle it, and the person who rules on the plan reads it there.

    **The analyst is handed the clone and the repository, not the discovery report.** The
    report says what the repository *is*; what should be built is a question about what it
    *lacks*, and handing over a report invites an agent to restate it — which is exactly
    what the first real run did. The clone is the substrate, and the inspection is read from
    it rather than from another agent's conclusion.
    """
    clone = state["clone"]

    if clone is None:
        raise TheRepositoryHasNotBeenClonedYetError(
            f"{Artifact.REQUIREMENTS} is reasoned about from the clone, "
            "and this run has none yet. The clone node is wired before the analyst node."
        )

    requirements, what_the_analyst_concluded = analyze(
        clone,
        state["work_item"].repository,
        state["work_item"].requested,
    )

    a_comment_was_left(
        state["work_item"],
        what_was_said=what_the_analyst_concluded.judged.the_text_of_the_note_this_is(),
        by=THE_PRODUCT_ANALYST_AGENT,
        at=datetime.now(UTC),
        projects_root=state["projects_root"],
    )

    return {
        "requirements": requirements,
        "presented_artifact_id": Artifact.REQUIREMENTS,
        "presented_artifact_version": ITS_FIRST_VERSION,
    }
