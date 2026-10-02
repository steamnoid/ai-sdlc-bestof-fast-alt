"""Starting a run again from what the last one left behind.

**The read side of the register, and without it the register is a filing cabinet.** A run that was
interrupted after four gates left four artifacts and a work item at a real stage, and until now the
only way back into it was to rebuild the state by hand.

**What is on disk is carried; what is not stays absent.** A run resumed at the start is the same
state a fresh run begins in, and one resumed after four gates carries four artifacts. Inventing an
empty artifact to fill a channel would have the run re-ask a person about a document that already
exists.

**The stage comes from the work item and the artifact presented comes from what exists.** A gate
presents `presented_artifact_id` and its version, and a resumed run that kept the starting value
would put `DiscoveryReport` in front of a person a second time with a version number meaning the
wrong thing. So the artifact presented is the first one this run does not already have.

**Nothing is inferred and nothing is invented.** An empty register is not a run at the start; it is
a run nobody asked for, and that stops.
"""

from __future__ import annotations

from pathlib import Path

from aisdlc.agents.architecture_report import ArchitectureReport
from aisdlc.agents.discovery_report import DiscoveryReport
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.pull_request_request import PullRequestRequest
from aisdlc.agents.qa_plan import QaPlan
from aisdlc.agents.requirements import Requirements
from aisdlc.agents.security_report import SecurityReport
from aisdlc.agents.verification_report import VerificationReport
from aisdlc.domain.repository import Repository
from aisdlc.domain.state_machine import validate_state
from aisdlc.domain.work_item import WorkItem
from aisdlc.graph.agent_state import AgentState
from aisdlc.persistence.the_register_of_work_items import the_work_item_registered_as
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.the_project_directory import the_clone_directory_of, the_project_directory_of

A_FILE_EXTENSION_A_PERSON_CAN_READ = ".json"
ITS_FIRST_VERSION = 1
THE_ARTIFACT_A_RUN_BEGINS_WITH = "DiscoveryReport"

# What exists on disk, in the order a run produces it. **Read in order and not by name**, because
# the order is what decides which artifact a resumed run presents, and a lookup by name would have
# that decided by whichever key a dict happened to keep.
_THE_ARTIFACTS_IN_THE_ORDER_A_RUN_PRODUCES_THEM = (
    ("discovery_report", DiscoveryReport),
    ("requirements", Requirements),
    ("qa_plan", QaPlan),
    ("architecture_report", ArchitectureReport),
    ("security_report", SecurityReport),
    ("implementation_plan", ImplementationPlan),
    ("verification_report", VerificationReport),
    ("pull_request_request", PullRequestRequest),
)


def a_resumed_run_of(
    repository: Repository, work_item_id: str, projects_root: Path
) -> AgentState:
    """The state a run starts from when it is picked up again, from the register and the artifacts.

    **A work item and a projects root in, a whole state out**, because a caller that wanted a
    state has one thing to say and a caller that wanted the work item already has it. The
    alternative is a function per channel and a caller assembling twenty fields by hand — which
    is `a_starting_state_of` all over again, and that factory exists in the test tier precisely
    because production had nothing.

    **The clone is pointed at, not created.** Cloning is the one step that must not happen twice
    for a run that already has a checkout, and reading a directory's path is all resuming needs.
    Whether the clone is there is the node's question, not this one's.
    """
    work_item = the_work_item_registered_as(repository, work_item_id, projects_root)
    what_exists = _the_artifacts_this_run_already_produced(work_item, projects_root)

    return _the_state_of(work_item, what_exists, projects_root)


def _the_artifacts_this_run_already_produced(
    work_item: WorkItem, projects_root: Path
) -> dict[str, object]:
    """Every artifact on disk for this work item, and only those that are.

    **Validated on the way in, because a file is data until something has checked it.** A run
    resumed from a hand-edited register would otherwise reason on a work item in a stage it cannot
    be in, and the state machine is the only thing in this package that knows which stages are
    possible.
    """
    validate_state(work_item)

    project = the_project_directory_of(work_item, projects_root)
    found: dict[str, object] = {}

    for channel, the_artifact in _THE_ARTIFACTS_IN_THE_ORDER_A_RUN_PRODUCES_THEM:
        the_file = project / f"{the_artifact.__name__}{A_FILE_EXTENSION_A_PERSON_CAN_READ}"
        if the_file.is_file():
            found[channel] = the_artifact.model_validate_json(
                the_file.read_text(encoding="utf-8")
            )

    return found


def _the_state_of(
    work_item: WorkItem, what_exists: dict[str, object], projects_root: Path
) -> AgentState:
    """The state, with every channel this system has, and nothing invented to fill one.

    **The artifact presented is the first one this run has not already produced**, because that is
    the one a person has not ruled on yet. Presenting the first would put a document in front of
    somebody for a second time, with a version number meaning the second attempt.
    """
    state: AgentState = {
        "work_item": work_item,
        "projects_root": projects_root,
        "clone": _where_this_runs_clone_is(work_item, projects_root),
        "requested_stage": work_item.stage,
        "requested_agent": None,
        "requested_role": work_item.role,
        "the_commit_anything_proved": None,
        "which_checks_went_green": None,
        "written_files": None,
        "opened_pull_request": None,
        "repair": None,
        "what_stopped_this_run": None,
        "decisions": [],
        "approvals": [],
        "discovery_report": None,
        "requirements": None,
        "qa_plan": None,
        "architecture_report": None,
        "security_report": None,
        "implementation_plan": None,
        "verification_report": None,
        "pull_request_request": None,
        "presented_artifact_id": THE_ARTIFACT_A_RUN_BEGINS_WITH,
        "presented_artifact_version": ITS_FIRST_VERSION,
    }
    state.update(what_exists)  # type: ignore[typeddict-item]
    state["presented_artifact_id"] = _the_artifact_a_resumed_run_presents(what_exists)
    state["presented_artifact_version"] = ITS_FIRST_VERSION

    return state


def _the_artifact_a_resumed_run_presents(what_exists: dict[str, object]) -> str:
    """The first artifact this run has not produced, or the last one when it has produced them all.

    **The run's own list rather than the pipeline's order again**, because the two are the same
    list and a second one is a second thing to forget to extend.
    """
    for channel, the_artifact in _THE_ARTIFACTS_IN_THE_ORDER_A_RUN_PRODUCES_THEM:
        if channel not in what_exists:
            return the_artifact.__name__

    return _THE_ARTIFACTS_IN_THE_ORDER_A_RUN_PRODUCES_THEM[-1][1].__name__


def _where_this_runs_clone_is(work_item: WorkItem, projects_root: Path) -> ClonedRepository:
    """Where this run's checkout is, without cloning it again.

    **A placeholder commit, and said so.** A run that is being resumed has a checkout already, and
    a resumed state that pointed at nothing would be a state the clone node has to overwrite; a
    resumed state that pointed at a *wrong* commit would be worse. The commit is read from the
    clone's own `HEAD` when it is there, and this is the one value a resumed run cannot be honest
    about without asking git.
    """
    where = the_clone_directory_of(work_item, projects_root)
    the_head = where / ".git" / "HEAD"

    return ClonedRepository(
        path=where,
        ref="",
        commit=_the_commit_the_clone_is_on(the_head),
    )


def _the_commit_the_clone_is_on(the_head: Path) -> str:
    """The commit a checkout is on, read from git's own file rather than by running git.

    **Read rather than asked for, because this runs during a resume and a resume is not the place
    to shell out.** The file is git's own record and it is the same one `git rev-parse` reads.
    """
    if not the_head.is_file():
        return ""

    return the_head.read_text(encoding="utf-8").strip().removeprefix("ref: ")
