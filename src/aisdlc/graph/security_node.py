"""The security analyst's node: the last of the four, and the one whose silence reads as safety.

Identical in shape to the other three for the same reasons: the clone channel is checked
before the node reads anything, the model answers first, and the artifact the gate will name is
written beside it — because findings sitting in the state are not something anybody was asked
to rule on.

**It reads the clone, because §10's security responsibilities are all questions about code** —
authentication, configuration, secrets handling. The QA analyst is the one analysis agent whose
question is about a document, and saying so here is what separates this file from `qa_node.py`
rather than leaving a reader to infer it from two files that look alike.

The node is the fourth analysis stage and the run is routed here by the third gate. Where it
leads is the router's business, and until the planner can be reached from this artifact the run
ends here — a deliberate ending rather than a missing stage, which is the distinction
`NoRouteIsDeclaredForThisArtifactError` is named for.
"""

from __future__ import annotations

from collections.abc import Callable

from aisdlc.agents.artifact import Artifact
from aisdlc.agents.security_report import SecurityReport
from aisdlc.domain.repository import Repository
from aisdlc.graph.agent_state import AgentState
from aisdlc.graph.clone_node import TheRepositoryHasNotBeenClonedYetError
from aisdlc.tools.github_clone_repository import ClonedRepository

InspectForSecurityRisk = Callable[[ClonedRepository, Repository], SecurityReport]

ITS_FIRST_VERSION = 1


def inspect_for_security_risk_in_this_run(
    state: AgentState, inspect: InspectForSecurityRisk
) -> dict:
    """The risk found in the repository this run cloned, and the artifact to present.

    Both halves, because they are different facts. Findings in the state are not an artifact
    anybody was asked to rule on: the gate presents `presented_artifact_id` and its version,
    and a run that kept its findings and offered nothing would put an empty artifact in front
    of a person — **and an empty security artifact is the one a reader mistakes for a clean
    bill of health.**

    The version is fixed at one for the reason every stage's is: nothing has written a second
    version of a `SecurityReport`, and a counter that counted runs would not be a version an
    approval could be invalidated by.
    """
    clone = state["clone"]

    if clone is None:
        raise TheRepositoryHasNotBeenClonedYetError(
            f"{Artifact.SECURITY_REPORT} is inspected for in the clone, "
            "and this run has none yet. The clone node is wired before the analyst node."
        )

    return {
        "security_report": inspect(clone, state["work_item"].repository),
        "presented_artifact_id": Artifact.SECURITY_REPORT,
        "presented_artifact_version": ITS_FIRST_VERSION,
    }
