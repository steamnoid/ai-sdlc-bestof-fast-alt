"""The graph's state: the channels a work item's journey is carried in."""

from __future__ import annotations

import operator
from pathlib import Path
from typing import Annotated, TypedDict

from aisdlc.agents.architecture_report import ArchitectureReport
from aisdlc.agents.discovery_report import DiscoveryReport
from aisdlc.agents.implement_the_plan import FileToWrite
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.pull_request_request import PullRequestRequest
from aisdlc.agents.qa_plan import QaPlan
from aisdlc.agents.requirements import Requirements
from aisdlc.agents.security_report import SecurityReport
from aisdlc.agents.verification_report import VerificationReport
from aisdlc.approval.approval_decision import ApprovalDecision
from aisdlc.domain.approval import Approval
from aisdlc.domain.role import Role
from aisdlc.domain.stage import Stage
from aisdlc.domain.work_item import WorkItem
from aisdlc.graph.what_to_repeat import WhatToRepeat
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.github_create_pull_request import AnOpenedPullRequest

# **Named because a node that carries a refusal across the graph has to name the key twice**,
# and a string typed at a call site is a string nothing checks. This is the channel a refusal
# bound for the supervisor travels in, and it holds the refusal's own words rather than a
# summary of them.
WHAT_STOPPED_THIS_RUN = "what_stopped_this_run"


class AgentState(TypedDict):
    """Everything the lifecycle carries between nodes.

    A channel is a container and its payload is a domain type, never a dict, so a
    node cannot smuggle a shape past the state machine by writing a loose value into
    it.

    **`decisions` and `approvals` are lists because a run is walked through more than one
    gate, and a single channel keeps only the last answer.** That is not a tidiness point: the
    summary is a person's record of who ruled on what, and with one channel it named one gate
    of three and paired that gate's verdict with another gate's name. `operator.add` is what
    makes a channel accumulate rather than be overwritten, so a node writes its own answer and
    nobody has to read the previous ones first.

    **Both lists, and not one.** A refusal is a decision with `approved` false and it leaves no
    `Approval` at all — so a record built from approvals alone could not show a gate somebody
    answered "no" to, and one built from decisions alone would be ignoring which answers earned
    a record. `presented_artifact_id` and `presented_artifact_version` stay single, and
    correctly so: the gate presents the artifact of *this* gate, and the history of what was
    presented is in the decisions, each of which names its own.
    """

    work_item: WorkItem
    projects_root: Path
    clone: ClonedRepository | None
    requested_stage: Stage
    requested_agent: str | None
    requested_role: Role
    discovery_report: DiscoveryReport | None
    requirements: Requirements | None
    qa_plan: QaPlan | None
    architecture_report: ArchitectureReport | None
    security_report: SecurityReport | None
    implementation_plan: ImplementationPlan | None
    written_files: list[FileToWrite] | None
    verification_report: VerificationReport | None
    pull_request_request: PullRequestRequest | None
    opened_pull_request: AnOpenedPullRequest | None
    the_commit_anything_proved: str | None
    which_checks_went_green: list[str] | None
    the_commit_that_landed: str | None
    the_conflict_that_stopped_this_merge: str | None
    presented_artifact_id: str
    presented_artifact_version: int
    repair: WhatToRepeat | None
    what_stopped_this_run: str | None
    decisions: Annotated[list[ApprovalDecision], operator.add]
    approvals: Annotated[list[Approval], operator.add]
