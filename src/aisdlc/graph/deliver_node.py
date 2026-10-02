"""The delivery: what a run will ask for, refused until every gate has been answered.

Identical in shape to the plan node and for the same reason — the artifact is written, the
channel is checked before the node reads anything, and the artifact the gate will name is
returned alongside it.

**No model, and that is the design rather than a shortcut.** §10 gives the PR agent four
responsibilities and none of them is reasoning: prepare the change summary, prepare the title
and body, verify that the required gates passed, and create the pull request only after
explicit human approval. Every one of those is a fact the run already holds. A pull request
body is read further upstream than the run's own summary — by a maintainer deciding whether
to merge machine-written code — and a model in between would put prose where the two numbers
are the whole of what the run claims.
"""

from __future__ import annotations

from collections.abc import Callable

from langgraph.types import Command

from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.pull_request_request import PullRequestRequest
from aisdlc.agents.verification_report import VerificationReport
from aisdlc.domain.repository import Repository
from aisdlc.domain.work_item import WorkItem
from aisdlc.graph.agent_state import WHAT_STOPPED_THIS_RUN, AgentState
from aisdlc.graph.clone_node import TheRepositoryHasNotBeenClonedYetError
from aisdlc.graph.supervise_a_repair import WHERE_THE_SUPERVISOR_DECIDES_WHETHER_TO_REPAIR
from aisdlc.store.what_a_run_records import a_run_was_delivered
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.github_create_branch import PushedBranch
from aisdlc.tools.github_create_pull_request import (
    AnOpenedPullRequest,
    BranchOnRemote,
    PullRequestToOpen,
    a_pull_request_to_open,
)
from aisdlc.tools.our_own_runs import (
    a_delivery_branch_for_a_filing,
    a_delivery_branch_named,
)
from aisdlc.tools.run_tests import SuiteOutcome

WHERE_THE_RUN_IS_MARKED_DELIVERED = "mark_the_work_item_delivered"
WHERE_GITHUB_IS_ASKED_ABOUT_THE_COMMIT = "ask_github_whether_the_suite_went_green"
"""The node this one hands to on success, named here because it is part of what this node does.

**There is no edge out of this node, for the same reason there is none out of the node that
implements a plan.** This node returns a `Command` on both outcomes — a red suite goes to the
supervisor, a delivery goes to `mark_the_work_item_delivered` — and an edge out of a node whose
other outcome is a `Command(goto=...)` fires *alongside* whichever `goto` it chose. That is not a
hypothetical: it is how every repair in this system used to die, with LangGraph refusing the run
for writing `requested_stage` twice in one step. The implementer had the same shape; this node was
found by reading for it once the first one was fixed, because the defect has one shape and one
shape has more than one place it can sit.
"""

THE_ARTIFACT_DELIVERY_PRODUCES = "PullRequestRequest"
ITS_FIRST_VERSION = 1

# Every gate a run walks through, in order. A delivery needs all of them, which is the whole
# of what "verify that required gates passed" means in §10 — and it means *answered yes*, not
# merely answered, because a refusal ends the run and this stage is downstream of the end.
EVERY_ARTIFACT_A_PERSON_RULES_ON_BEFORE_A_DELIVERY = (
    "DiscoveryReport",
    "Requirements",
    "QaPlan",
    "ArchitectureReport",
    "SecurityReport",
    "ImplementationPlan",
    "VerificationReport",
)


class TheDeliveryHasNoVerifiedChangeToDeliverError(Exception):
    """The rule is in `a_request_for_the_delivery`, and only it may say the rule broke.

    A delivery is a change and a verification of it, and this run has neither to hand. The
    node is reached only through the router with an approved `VerificationReport`, so this
    cannot happen in the wired graph — and the check is here for the reason the clone channel
    is checked in the plan node: a graph wired in the wrong order passes a `None` along until
    something reads an attribute off it, and the thing it reads here is what a maintainer
    would be asked to merge.
    """


class TheDeliveryHasNoRequestToDeliverError(Exception):
    """The rule is in `a_request_for_the_delivery`, and only it may say the rule broke."""


class TheDeliveryHasNotBeenApprovedError(Exception):
    """The rule is in `a_request_for_the_delivery`, and only it may say the rule broke.

    A run that verified a change and was not approved for it has a change on disk and nothing
    else. Opening a pull request for it would be a delivery nobody was asked for, on a
    repository that did not invite one, which is the failure §10 names when it says a pull
    request may be created "only after explicit human approval".
    """


def a_request_for_the_delivery(state: AgentState) -> dict:
    """The request a person rules on, and the artifact identity the gate will record.

    **Gates first, and every one of them answered yes.** §10 makes this the PR agent's
    responsibility — "verify that required gates passed" — and passed means an approval, not
    an answer. The artifacts in the state are identical whether a person said yes or no, so a
    check that counted decisions would let a run a person stopped at the fourth gate deliver a
    change anyway, which is the one thing a human approval boundary exists to prevent.

    The title is the commissioned request, because that is what a reviewer reads in a list of
    forty. The work item's id would be true and would say nothing about whether they want the
    change in their repository.
    """
    _refuse_a_run_with_an_unanswered_gate(state)

    work_item = state["work_item"]
    plan = state["implementation_plan"]
    report = state["verification_report"]

    if plan is None or report is None:
        raise TheDeliveryHasNoVerifiedChangeToDeliverError(
            f"{THE_ARTIFACT_DELIVERY_PRODUCES} states a change and what was verified about it, "
            f"and this run has {'a plan but no verification' if plan is not None else 'no plan'}"
            f"{'' if report is not None else ' and no verification'}. A pull request that "
            "omitted either would present a change nobody verified, which is the one thing a "
            "maintainer reading it is entitled to rely on."
        )

    request = work_item.requested

    if request is None:
        raise TheDeliveryHasNoRequestToDeliverError(
            "a pull request is titled after the work somebody asked for, and this work item "
            "records no request. A title built from the work item's id would be true and "
            "would say nothing about the change to a reviewer."
        )

    return {
        "pull_request_request": PullRequestRequest(
            repository=work_item.repository,
            work_item_id=work_item.work_item_id,
            branch=(
                a_delivery_branch_for_a_filing(work_item)
                if work_item.requested is not None
                and work_item.requested.filed_as is not None
                else a_delivery_branch_named(work_item.work_item_id)
            ),
            base=state["clone"].ref if state["clone"] is not None else "",
            title=request.title,
            body="\n".join(
                (
                    *_the_lines_of_a_pull_request_body(work_item),
                    "",
                    _the_body_saying_what_changed_and_what_was_verified(plan, report),
                )
            ),
        ),
        "presented_artifact_id": THE_ARTIFACT_DELIVERY_PRODUCES,
        "presented_artifact_version": ITS_FIRST_VERSION,
    }


PushTheBranch = Callable[[ClonedRepository, str], PushedBranch]
OpenThePullRequest = Callable[[PullRequestToOpen], AnOpenedPullRequest]


class ASuiteThatWentRedIsNotADeliveryError(Exception):
    """A change that leaves the suite red is not delivered, and this says what the suite said.

    **A fact and not a judgement, and that is the whole reason this is a rule.** Asserting that a
    change *keeps* the suite green would be a claim about the model's judgement, and
    `test_the_run_reports_the_suite_before_and_after_the_change_truthfully` says so and asserts
    green nowhere. **Refusing what the suite already said is claims nothing about the model**: the
    suite was run in a container, on both sides of the change, and its own output is in the
    message -- so a person reads the same two numbers this system refused on.

    **Carries the suite's own words rather than a summary of them.** This system cannot parse
    another project's test output to name the test that broke, and a name a scraper invented is a
    name nobody verified, so the report and this refusal quote the same text.
    """

    def __init__(
        self, what_the_suite_said: str, exit_code: int, who_approved_the_red_change: str = ""
    ) -> None:
        """Say the suite's own words, its exit code, and **who approved this and was refused**.

        **The third fact is the one that was missing, and it was missing by accident.** The gate
        is upstream of this node: a person was asked about this verification, with the failing
        assertions quoted in the artifact, and answered yes. A refusal that does not say so makes
        the run's own directory read as though nobody ruled on it — and this system's principle is
        that a person rules and the run continues.

        **The refusal still stands.** A person who approves a known red change is doing exactly
        what the gate is for, and the next thing they need is to be told it was not delivered and
        why, in the same record they approved.
        """
        super().__init__(
            "This run will not open a pull request, because the repository's own suite went red"
            f" after the change -- exit code {exit_code}. The suite said:\n{what_the_suite_said}"
            "\n\nA pull request that reports breaking the build is a report, not a delivery, and"
            " the report is already on disk beside the clone with the artifacts. What the change"
            " needs is the product change the plan did not name; the failure above is the suite"
            " saying so."
            + (
                f"\n\nThis was approved by {who_approved_the_red_change}, and the delivery is"
                " refused anyway. The approval is recorded here so the directory beside the clone"
                " tells the whole story."
                if who_approved_the_red_change
                else ""
            )
        )


def open_the_delivery(
    state: AgentState,
    our_copy: Repository,
    push: PushTheBranch,
    open_a_pull_request: OpenThePullRequest,
) -> Command | dict:
    """Push the approved branch and open the approved pull request, in that order.

    **A red suite stops this before anything is pushed, and the order matters for that.** The
    refusal is the first statement, so a refused delivery leaves no branch on a remote and no
    pull request anybody can find and read as a finished change.

    **Push first, because a pull request cannot be opened against a branch that is not on a
    remote.** GitHub answers 422 and quotes the cause, and the other order would produce a
    run that reported a delivery and delivered nothing.

    **Nothing before the approval.** §10 says the pull request is created "only after
    explicit human approval", and this artifact is the one that carries the branch, the base,
    the title and the body — so approving it approves the delivery rather than a description
    of one. The gate for the *verification* was checked when the request was written; this one
    is about the delivery itself.

    **`our_copy` is an argument rather than a setting read here.** Whose fork a delivery goes
    to is a fact about this deployment, and `the_account_we_fork_into` is where the
    environment is read — the fork tool's own rule is that every address-shaped decision
    lives in the tools rather than spread through the graph. A node reading an environment
    variable would also mean the unit tier, which reads none, could not run this at all.
    """
    report = state["verification_report"]

    if report is not None and not report.suite_after_the_change.passed:
        the_refusal = ASuiteThatWentRedIsNotADeliveryError(
            report.suite_after_the_change.output,
            report.suite_after_the_change.exit_code,
            _who_approved_the_verification(state),
        )
        return Command(
            goto=WHERE_THE_SUPERVISOR_DECIDES_WHETHER_TO_REPAIR,
            update={WHAT_STOPPED_THIS_RUN: str(the_refusal)},
        )

    the_request = state["pull_request_request"]

    if the_request is None:
        raise TheDeliveryHasNothingToDeliverError(
            f"{THE_ARTIFACT_DELIVERY_PRODUCES} is opened by the stage that wrote it, and this "
            "run has none. The delivery node is wired after the node that builds the request."
        )

    if not _this_request_was_approved(state, the_request):
        raise TheDeliveryWasNeverApprovedError(
            f"{THE_ARTIFACT_DELIVERY_PRODUCES} version {the_request} was never approved, so "
            "nothing was pushed and nothing was opened. A pull request is somebody's decision "
            "to review, and opening one nobody approved is a delivery nobody asked for."
        )

    clone = state["clone"]

    if clone is None:
        # Reused rather than renamed: the rule is the clone node's, it is already named, and
        # a second error saying "no clone" would be the same fact under two names.
        raise TheRepositoryHasNotBeenClonedYetError(
            "a delivery pushes the branch from the clone this run worked on, and this run has "
            "none yet. The clone node is wired before every other node that reads the "
            "repository."
        )

    pushed = push(clone, the_request.branch)
    the_pull_request = open_a_pull_request(
        a_pull_request_to_open(
            repository=the_request.repository,
            head=BranchOnRemote(owner=our_copy.owner, name=pushed.name),
            base=the_request.base,
            title=the_request.title,
            body=the_request.body,
        )
    )

    # **The address is announced before the node returns, so the card's last line is the
    # outcome.** Everything else this run did is on the board — the clone, the eight gates, the
    # notes — and the one thing a person came for is a link. A board that showed a run as
    # delivered without saying where would make the reader go and look for it, and the run's
    # whole output is that one string.
    a_run_was_delivered(state["work_item"].work_item_id, the_pull_request.address)

    return Command(
        goto=WHERE_GITHUB_IS_ASKED_ABOUT_THE_COMMIT,
        update={"opened_pull_request": the_pull_request},
    )


def _who_approved_the_verification(state: AgentState) -> str:
    """Whoever approved the verification that named a red suite, in their own words and theirs.

    **Read from the approvals and not from the decisions**, because an `Approval` is the record
    and a `ApprovalDecision` is one gate's answer, and what is needed here is *a person* rather
    than a count.

    **Empty rather than "nobody".** A run can reach this node with a red suite and no approval of
    a `VerificationReport` at all -- and then there is nobody to name, which is a different fact
    from a decision nobody made. The refusal says nothing extra in that case, rather than
    claiming a person approved something.
    """
    the_verification_approvals = [
        approval
        for approval in state["approvals"]
        if approval.artifact_id == "VerificationReport"
    ]
    if not the_verification_approvals:
        return ""
    return ", ".join(
        f"{one.approved_by} at {one.approved_at}" for one in the_verification_approvals
    )


def _this_request_was_approved(
    state: AgentState, the_request: PullRequestRequest
) -> bool:
    """Whether a person approved this exact artifact at this exact version.

    The work item's id is compared as well as the artifact's, because two runs of one
    repository both have an artifact called `PullRequestRequest` and only one of them is this.
    """
    return any(
        approval.artifact_id == THE_ARTIFACT_DELIVERY_PRODUCES
        and approval.work_item_id == state["work_item"].work_item_id
        for approval in state["approvals"]
    )


class TheDeliveryWasNeverApprovedError(Exception):
    """The rule is in `open_the_delivery`, and only it may say the rule broke.

    §10: the pull request is created "only after explicit human approval". A run that reached
    here without one is a run that wrote a request and is about to deliver it anyway, and the
    two statements — that a person was asked, and that they answered — are the whole of what
    makes a delivery legitimate.
    """


class TheDeliveryHasNothingToDeliverError(Exception):
    """The rule is in `open_the_delivery`, and only it may say the rule broke."""


def _refuse_a_run_with_an_unanswered_gate(state: AgentState) -> None:
    """Every artifact this run puts to a person has to have been approved, by name.

    Refused by naming what is missing, because "the delivery was refused" tells a person
    nothing about which of seven gates to go and look at.
    """
    approved = {
        approval.artifact_id
        for approval in state["approvals"]
        if approval.work_item_id == state["work_item"].work_item_id
    }
    missing = [
        artifact
        for artifact in EVERY_ARTIFACT_A_PERSON_RULES_ON_BEFORE_A_DELIVERY
        if artifact not in approved
    ]

    if missing:
        raise TheDeliveryHasNotBeenApprovedError(
            f"{THE_ARTIFACT_DELIVERY_PRODUCES} is opened only after every gate has been "
            f"approved, and this run has none of: {', '.join(missing)}. A run that verified a "
            "change and was not approved for it has a change on disk and nothing else, and "
            "opening a pull request for it is a delivery nobody asked for."
        )


def _the_body_saying_what_changed_and_what_was_verified(
    plan: ImplementationPlan, report: VerificationReport
) -> str:
    """§10's "prepare final change summary", in the order a reviewer reads it.

    **What changed, then what was verified, then the numbers.** The suite is stated on both
    sides because a reviewer cannot run this run's container, so this paragraph is the only
    evidence they will get — and a change that went red is reported as red rather than
    refused, because a failing verification is a result this system exists to produce. What
    the body must never do is say "passed" when the suite did not.
    """
    lines = ["## What changed", ""]
    lines += [f"- `{path}`" for path in plan.files_to_change]

    if plan.tests_to_add:
        lines += ["", "## Tests added", ""]
        lines += [f"- `{path}`" for path in plan.tests_to_add]

    lines += [
        "",
        "## What was verified",
        "",
        f"- The repository's own suite was run in a container, before the change: "
        f"{_how_a_suite_said(report.suite_before_the_change)}.",
        f"- and after it: {_how_a_suite_said(report.suite_after_the_change)}.",
    ]

    if report.regressions:
        lines += ["", "The change caused the following, which were not failing before:"]
        lines += [f"- {regression}" for regression in report.regressions]

    return "\n".join(lines)


def _how_a_suite_said(outcome: SuiteOutcome) -> str:
    """One clause, saying whether it passed, and never softening it.

    `passed` is the suite's own claim and the exit code is the fact, so both are stated: a
    report claiming to pass and an exit code saying otherwise is a report nobody can act on.
    """
    verdict = "passed" if outcome.passed else "failed"
    return f"{verdict}, exit code {outcome.exit_code}"


def _the_lines_of_a_pull_request_body(work_item: WorkItem) -> list[str]:
    """The lines naming the filing this delivery answers, and nothing when there is none.

    **The address GitHub returned, and no number composed here.** A number alone is a lookup and a
    lookup is work for a reviewer; the address is one click. Composing it from `owner/name` is the
    mistake that removed `CommissionedIssue` — a string shaped exactly like a link, resolving to
    nothing, in the one place a traceability chain exists to be true.

    **Nothing at all when the request was typed rather than filed.** A `Closes #` with no number,
    or a number nobody filed, is the same false reference the branch is refused for, and the two
    halves of a traceability record that disagree are worse than having neither.
    """
    if work_item.requested is None or work_item.requested.filed_as is None:
        return []

    return [
        "## What this answers",
        "",
        f"- The request this delivery answers: {work_item.requested.filed_as.address}",
        f"- filed as issue {work_item.requested.filed_as.number}.",
    ]
    # **Nothing here says whether the filing has been closed since**, and that is a gap rather
    # than a choice: `github.read_issue` reads `state`, and `TheIssueThisAnswers` deliberately
    # keeps only the number and the address, so a run commissioned while the filing was open
    # cannot afterwards say it was closed in between. Carrying the state would change what a
    # filing is, and that belongs in the glossary rather than in a line added here.
