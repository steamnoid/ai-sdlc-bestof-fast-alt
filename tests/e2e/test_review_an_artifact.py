"""A policy standing in for a person at the gate, against a real model and a real artifact.

**The gate is a hard architectural boundary and a policy is the one thing standing on the wrong
side of it deliberately, so it is the one thing that has to be proven rather than assumed.** A
person ruling on an artifact and a model ruling on one are recorded in the same table, and the
only thing that tells a reader which happened is the name on the decision. If a decision naming
a model is signed with somebody's name, the audit trail is forged and it is forged *exactly*
looking like the real thing at the moment somebody needs to tell them apart. **So this file
asserts the signing on every decision a real model produced here, and it would fail on a
decision signed as a person however well the model had reasoned.**

**The artifact is a real one, read off disk by production code, because the alternative is
approving a paragraph.** The policy opens the file beside the clone rather than reading the
question, and the question deliberately carries identity and not contents — so a policy
answering from the question would be reviewing nothing and approving on a filename. The
artifact here is a discovery report citing a path the clone really holds, and the test says so,
because a hand-built artifact citing a file the repository does not have would be testing the
signing of a decision made about nothing.

**Asserting the grounds, and not the verdict.** A policy is free to approve or refuse this
report — both are decisions, both are recorded, and a test that wanted one of them would be
testing the model rather than the boundary. What cannot be either is a decision with no reason:
a verdict with nothing behind it is a coin flip written down, and it is refused in two places
(the model's own shape and the decision's), so reaching this assertion is the first half of the
claim and the second is that what arrived is a sentence rather than a shape.

**And the one rule that needs no model is here too, because it is the one that protects the
signing.** An `aisdlc-` identifier posted as a decider is refused by the gate, and the default
suite holds that through a board. What it cannot hold is the setting that decides *which* name
gets to sign: a value that already carries the policy namespace, or one that is blank, is
refused rather than unwrapped or ignored — **because this is the one setting where a fallback is
the worst answer available**, since falling back would hand a run the right to approve its own
work and leave no name in the record to quote in the argument about whose run it was.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

import pytest

from aisdlc.agents.discovery_report import DiscoveryReport, evidence_for
from aisdlc.agents.review_an_artifact import (
    THE_SETTING_NAMING_THE_APPROVAL_POLICY,
    APolicySettingThatNamesNoPolicyError,
    review_an_artifact,
    the_policy_a_deployment_stated,
)
from aisdlc.approval.approval_decision import ApprovalDecision
from aisdlc.approval.approval_gate import THE_POLICY_NAMESPACE
from aisdlc.approval.approval_question import ApprovalQuestion
from aisdlc.domain.commissioned_request import a_request_about
from aisdlc.domain.repository import Repository
from aisdlc.domain.role import Role
from aisdlc.domain.work_item import WorkItem, a_work_item_commissioned_for_an_agent
from aisdlc.graph.the_agents_a_run_reasons_with import THE_AGENTS_A_RUN_REASONS_WITH
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.store.the_register_of_work_items import the_work_item_a_commission_registers
from aisdlc.store.where_the_register_lives import holding_the_register
from aisdlc.tools.what_a_run_leaves_behind import write_the_report

pytestmark = pytest.mark.e2e

THE_POLICY_THIS_FILE_NAMES = "read-the-discovery-report"
"""A bare name, which is what a deployment states and all this file signs with.

**Named here rather than read from the environment, because this file asks one policy a
question.** The point of the stage is that the decision carries the name the deployment chose,
and a test that read `AISDLC_APPROVAL_POLICY` would prove that whatever was configured works
rather than that a policy can sign at all. The name is spelled as a bare name on purpose: the
namespace belongs to the code that knows what a policy is, which is why the value below cannot
carry it.
"""

THE_ARTIFACT_VERSION_BEING_RULED_ON = 1
"""The version in the question, so that the decision is asked about one version of one document."""


class WhatThePolicyAnswered(NamedTuple):
    """One real decision and the moment the question was put, which is the other half of it.

    **Both, and the moment is not decoration.** A decision is ordered against the other
    decisions on the same artifact, and the validator in `ApprovalDecision` exists because a
    decision with no timezone cannot be ordered at all — so a test that only checked the shape
    would never notice a decision stamped before the thing it rules on. The moment is captured
    before the call rather than after it, which is what makes the ordering assertion mean
    something.
    """

    the_decision: ApprovalDecision
    the_moment_the_gate_was_asked: datetime


@pytest.fixture(scope="module")
def a_register_and_a_projects_root_under_a_temporary_directory(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """A register and a projects root, both in a directory pytest will delete.

    **A policy writes twice, and neither write belongs in the repository.** It files the
    artifact a decision is about, and the artifact is announced to the register the board reads;
    a test that let either land beside this repository's own source would be leaving the
    evidence of a decision on the machine that is being tested.
    """
    a_temporary_directory = tmp_path_factory.mktemp("this-gate-answered")
    return a_temporary_directory / "projects"


@pytest.fixture(scope="module")
def the_work_item_at_this_gate(
    the_repository: Repository,
    a_register_and_a_projects_root_under_a_temporary_directory: Path,
) -> WorkItem:
    """A work item somebody asked for work on, registered where the run's record is read.

    **The projects-root fixture is asked for even though this fixture never uses its value, and
    that is the whole of why it is here.** The register is a process-wide fact rather than a
    per-directory one, and opening it is somebody else's fixture's job — so a fixture that writes
    to the register must depend on the one that opens it, or it runs first and raises
    `NoRegisterHasBeenOpenedError`. **The first version of this file did not, and it passed for a
    whole afternoon**: run beside a file that happened to open a register earlier, the global was
    already open and the ordering never showed. Run on its own it failed in three tenths of a
    second, which is the shape of a test that only ever passed beside another one.
    """
    the_work_item = a_work_item_commissioned_for_an_agent(
        work_item_id="issue-202",
        repository=the_repository,
        accountable_role=Role.ARCH,
        commissioned_by="a person reading a test",
        requested=a_request_about("name the Node version the project is developed against"),
    )
    with holding_the_register() as the_register:
        the_work_item_a_commission_registers(the_register, the_work_item)
    return the_work_item


def _a_file_the_clone_really_holds(the_clone) -> str:
    """One path in this repository's own root, read off the clone rather than assumed.

    **The candidate list is what an onboarding repository has, and the fallback is the reason
    the list exists at all.** A discovery report's evidence is paths a reviewer opens, so an
    artifact citing a file this repository does not have would be testing the signing of a
    decision made about a link that resolves to nothing — and the file would be about nothing.
    The walk at the end is a root file in the repository, whatever it is called, so a
    deployment pointed at a repository with none of the names below is not left with a briefing
    about a file it does not have.
    """
    for a_candidate in ("package.json", "pyproject.toml", "Dockerfile", "README.md"):
        if (the_clone.path / a_candidate).is_file():
            return a_candidate

    every_file_at_the_root = sorted(
        a_path.relative_to(the_clone.path).as_posix()
        for a_path in the_clone.path.iterdir()
        if a_path.is_file()
    )
    if not every_file_at_the_root:
        raise AssertionError(
            f"the clone of {the_clone.path} holds no file at its root, so a discovery report "
            "cannot cite anything a reviewer could open and this file would be about a decision "
            "made about nothing"
        )
    return every_file_at_the_root[0]


@pytest.fixture(scope="module")
def the_question_this_gate_asks(
    the_work_item_at_this_gate: WorkItem,
    a_register_and_a_projects_root_under_a_temporary_directory: Path,
    the_cloned_repository,
) -> ApprovalQuestion:
    """The question, and the artifact on disk beside the clone that it names.

    **The artifact is written by the production writer, not by this file.** A hand-written
    `DiscoveryReport.json` would be a second thing that could disagree with the run's own
    writer about where an artifact lives and what it is called — and the policy is asked to open
    a file at a path this system derives, so the path is part of what is under test.

    **The evidence is a real path of the real clone, and the test says so.** A report whose
    `evidence_files` point at a file this repository does not have hands a reviewer a link
    shaped exactly like a link to a file, which is the failure a discovery report's own check
    exists to stop and the reason this file cannot quietly build one.
    """
    the_path_it_cites = _a_file_the_clone_really_holds(the_cloned_repository)
    write_the_report(
        DiscoveryReport(
            languages=["TypeScript", "JavaScript"],
            frameworks=["React", "Express"],
            # **The command and not the tool, and that is the artifact's own rule rather than
            # this file's taste.** `DiscoveryReport` refuses a `build_system` that names one tool
            # and nothing else, because a person at a gate cannot rule on a change about a
            # runtime while holding a report that says only which tool — and a real run proved it
            # by answering `npm` and being refused.
            #
            # **This value was `"npm"` until a real-tier run caught it.** The rule arrived in the
            # same branch as this suite and `pytest -q` stayed green: 106 tests, no model, and
            # nothing here constructed a `DiscoveryReport`. `npm ci` is also what this repository
            # actually runs, so the fix makes the fixture true rather than merely acceptable.
            build_system="npm ci",
            ci_system=None,
            architecture_summary=(
                f"A React front end under web-app/ served by a Node API, built with npm and "
                f"tested by vitest. The root of the repository is where a reviewer starts, and "
                f"{the_path_it_cites} is the first file this report rests on."
            ),
            key_components=[the_path_it_cites, "web-app"],
            evidence_files=evidence_for([the_path_it_cites], the_work_item_at_this_gate.repository),
            suggested_changes=[
                "Say in the README which Node version this is developed against, because a "
                "contributor reading it today cannot tell which version to install."
            ],
        ),
        the_work_item_at_this_gate,
        a_register_and_a_projects_root_under_a_temporary_directory,
    )

    return ApprovalQuestion(
        work_item_id=the_work_item_at_this_gate.work_item_id,
        artifact_id="DiscoveryReport",
        artifact_version=THE_ARTIFACT_VERSION_BEING_RULED_ON,
    )


@pytest.fixture(scope="module")
def a_real_decision(
    the_work_item_at_this_gate: WorkItem,
    a_register_and_a_projects_root_under_a_temporary_directory: Path,
    the_question_this_gate_asks: ApprovalQuestion,
    the_model_for,
    request,
) -> WhatThePolicyAnswered:
    """One real decision about one real artifact, shared by every assertion about it.

    **The moment is taken before the model is called and not inside it**, so the ordering the
    next test asserts is about a real call rather than about two reads of a clock. One call for
    the whole module, because a model asked the same question twice can answer two different
    ways and this file is about the boundary rather than about the answer. The provider is
    `request.param` and the tests parametrise it indirectly, so a deployment configured for one
    provider *skips* the others with the reason printed.
    """
    the_moment_the_gate_was_asked = datetime.now(UTC)
    return WhatThePolicyAnswered(
        the_decision=review_an_artifact(
            the_work_item_at_this_gate,
            a_register_and_a_projects_root_under_a_temporary_directory,
            the_question_this_gate_asks,
            THE_POLICY_THIS_FILE_NAMES,
            the_model_for(request.param),
        ),
        the_moment_the_gate_was_asked=the_moment_the_gate_was_asked,
    )


@pytest.fixture(scope="module")
def the_policy_a_configured_deployment_could_answer_with(the_model_for, request) -> str:
    """The name a policy would sign with here, from a deployment that has a model to ask.

    **The model is built and never called, and that is what makes this fixture worth having.**
    The rule in the last test is about a deployment's *configuration* — which name is allowed to
    answer a gate — so asking it of a deployment that has nothing configured would prove it
    about nobody. Asking the real factory for the model is how this fixture establishes that
    there is a deployment to ask, and it costs no call, no network and no money: the factory
    builds a client and the first token is what a call is for. It also skips loudly for a
    provider this deployment is not configured for, which is the same reason every other test
    here is parametrised over the provider.
    """
    the_model_for(request.param)
    return THE_POLICY_THIS_FILE_NAMES


@pytest.mark.parametrize("a_real_decision", list(LlmProvider), indirect=True)
def test_the_decision_is_signed_as_the_policy_that_made_it_and_as_nobody_else(
    a_real_decision: WhatThePolicyAnswered,
) -> None:
    """A real model's verdict carries the policy's own name, in the policy's own namespace.

    **And carries nothing else, which is the whole of the forgery risk.** `decided_by` is the
    one field in the record that says who or what ruled, and a decision naming a person for a
    judgement a model made is a forged audit trail that is forged *looking exactly like the real
    thing* at the moment somebody needs to tell them apart. The comparison is on the whole name
    and not on a prefix, so a name that merely mentions the policy somewhere is not a signature.

    **An agent identifier is refused here too, and the check is a naming one.** §11 forbids an
    agent approving an agent's output, and the gate can only enforce that by looking at this
    field — so a decision signed this way is a run that answered its own gate, and the assertion
    is that the value a real model produced here never carries one of the run's own agents.
    """
    the_decision = a_real_decision.the_decision

    assert isinstance(the_decision, ApprovalDecision), (
        f"the policy answered with {type(the_decision).__name__} rather than the type the gate "
        "validates, so nothing downstream can rely on which fields the record carries"
    )
    assert the_decision.decided_by == f"{THE_POLICY_NAMESPACE}{THE_POLICY_THIS_FILE_NAMES}", (
        f"this decision is signed {the_decision.decided_by!r} and the run was told to sign "
        f"{THE_POLICY_NAMESPACE + THE_POLICY_THIS_FILE_NAMES!r}. A name outside the policy's "
        "namespace is indistinguishable from a person's at the moment somebody has to tell them "
        "apart, and this is the one field in the record that says who or what ruled"
    )
    assert the_decision.decided_by not in THE_AGENTS_A_RUN_REASONS_WITH, (
        f"this decision is signed {the_decision.decided_by!r}, which is an agent of this run. An "
        "agent approving an agent's output is forbidden, and the gate's only defence is this "
        "field — so a value carrying an agent's identifier is a run that answered its own gate"
    )


@pytest.mark.parametrize("a_real_decision", list(LlmProvider), indirect=True)
def test_the_decision_is_about_this_artifact_at_this_version_with_its_grounds(
    a_real_decision: WhatThePolicyAnswered,
    the_question_this_gate_asks: ApprovalQuestion,
    the_placeholders: frozenset[str],
) -> None:
    """The exact document and version, and a reason nobody can read past as nothing.

    **Three claims in one, and each of them is a field the gate orders by.** A decision names
    the artifact and the version it ruled on, and a later change to that document invalidates
    it — so a decision carrying a different version approves something the approval does not
    cover, which is the failure the version was introduced for. And it carries grounds: a
    verdict with nothing behind it is a coin flip written down, and the reason is the only part
    of the record a person can disagree with.

    **Non-empty is not asserted on its own.** The reason is refused blank by the decision and by
    the shape the model was asked for, so a test that only checked `isinstance(str)` would pass
    on a run that stopped over a whitespace-only reason at the gate. Placeholder text is the
    shape of that failure that reads as an answer.
    """
    the_decision = a_real_decision.the_decision

    assert the_decision.work_item_id == the_question_this_gate_asks.work_item_id, (
        f"the decision names work item {the_decision.work_item_id!r} and the gate asked about "
        f"{the_question_this_gate_asks.work_item_id!r}. A decision that cannot be told apart from "
        "another one is a gate that will eventually treat silence as consent"
    )
    assert the_decision.artifact_id == the_question_this_gate_asks.artifact_id, (
        f"the decision names {the_decision.artifact_id!r} and the gate asked about "
        f"{the_question_this_gate_asks.artifact_id!r}, so the record is about a document nobody "
        "presented"
    )
    assert the_decision.artifact_version == the_question_this_gate_asks.artifact_version, (
        f"the decision covers version {the_decision.artifact_version} and the gate presented "
        f"version {the_question_this_gate_asks.artifact_version}. An approval covers one version "
        "and is invalidated by a change to it, so a decision about a version that was not shown "
        "covers something the decision was never about"
    )

    assert the_decision.reason.strip(), (
        "this decision approved or refused with no reason, so the record says what it decided "
        "and not why. It is refused in two places — the shape the model was asked for and the "
        "decision itself — and a run that reached here has both refusals to have passed"
    )
    assert the_decision.reason.strip().lower() not in the_placeholders, (
        f"{the_decision.reason!r} is placeholder text standing in for the grounds, which means "
        "the model returned a shape rather than a ruling and the record reads as a decision "
        "nobody can question"
    )


@pytest.mark.parametrize("a_real_decision", list(LlmProvider), indirect=True)
def test_the_decision_can_be_ordered_against_the_document_it_ruled_on(
    a_real_decision: WhatThePolicyAnswered,
) -> None:
    """The decision carries a timezone, and it did not exist before the artifact did.

    **The timezone is asserted on the value that came back rather than on the constructor.**
    `ApprovalDecision` refuses a naive datetime itself, so a test that only built one and looked
    at it would be reading the constructor back; reading the settled value is what a board
    ordering two decisions on one artifact does, and it is the reason the validator exists.

    **The ordering against the question is the half nothing checks for us.** A decision stamped
    before it was asked is a record of a judgement made about a document that did not exist yet,
    and no validator in this system would notice — the two are only comparable because the
    moment the gate was asked was captured before the model was called, which is the part of
    this fixture that is not the model's.
    """
    the_decision = a_real_decision.the_decision
    when_it_was_made = the_decision.when_it_was_decided()

    assert when_it_was_made.tzinfo is not None, (
        f"{the_decision.decided_at!r} carries no timezone, so a board ordering this decision "
        "against another one on the same artifact gets an error rather than an order, and a "
        "decision nobody can place in time is a decision nobody can sequence"
    )
    assert the_decision.decided_at == when_it_was_made, (
        f"{the_decision.decided_at!r} and the moment the same decision reports "
        f"({when_it_was_made!r}) differ, so the two ways of reading one field's timezone "
        "disagree — and a caller writing its own conversion is a caller that can write a record "
        "in local time"
    )
    assert the_decision.decided_at >= a_real_decision.the_moment_the_gate_was_asked, (
        f"this decision is stamped {the_decision.decided_at.isoformat()}, which is before the "
        f"gate was asked ({a_real_decision.the_moment_the_gate_was_asked.isoformat()}). A "
        "judgement made about a document that did not exist yet is a record of a decision "
        "nobody took, and nothing in this system would refuse it"
    )


@pytest.mark.parametrize(
    "the_policy_a_configured_deployment_could_answer_with", list(LlmProvider), indirect=True
)
def test_a_setting_that_names_no_policy_is_refused_rather_than_answered(
    the_policy_a_configured_deployment_could_answer_with: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two settings that would sign a decision under a name nobody chose, and both are refused.

    **The other half of the same rule is here too: a bare name is honoured as written, and not
    unwrapped.** A rule that only refuses would be satisfied by a function returning `None` for
    everything, and a deployment whose policy was silently dropped would then have its gates
    answered by a person with nothing on the record saying so.

    **No model is asked, and that is why this test asks the setting rather than the gate.** The
    rule is about which name is allowed to answer a gate in the first place, so it can be proven
    in seconds; putting it beside a real model call would make a rule about an environment
    variable cost a paid round trip to check. The provider is still a parameter, so a deployment
    that has no model configured says so here too rather than reporting a green run about a
    question nobody could ask.

    **Both shapes, because they are both what a deployment actually writes.** A value already
    carrying the namespace is a deployment spelling the same thing twice, and the second copy is
    the one that can disagree with the first — so it is refused rather than unwrapped, because
    unwrapping quietly teaches two ways to say the same thing. A blank value is a truncated
    environment variable, which is the shape this failure takes in practice.

    **The refusal names the setting and the namespace, because the fix is in a configuration
    file.** Whoever reads this is holding a deployment's environment and not a document about
    one, and the module's own argument is that a run which fell back to a person here would be
    indistinguishable from one that never opted in.
    """
    monkeypatch.setenv(
        THE_SETTING_NAMING_THE_APPROVAL_POLICY,
        the_policy_a_configured_deployment_could_answer_with,
    )
    assert the_policy_a_deployment_stated() == the_policy_a_configured_deployment_could_answer_with

    for a_value_that_names_no_policy in (THE_POLICY_NAMESPACE + "already-written", "   "):
        monkeypatch.setenv(THE_SETTING_NAMING_THE_APPROVAL_POLICY, a_value_that_names_no_policy)

        with pytest.raises(APolicySettingThatNamesNoPolicyError) as refused:
            the_policy_a_deployment_stated()

        the_message = str(refused.value)
        assert THE_SETTING_NAMING_THE_APPROVAL_POLICY in the_message, (
            f"the refusal does not name the setting, so a person holding the value has nothing "
            f"to change. It said: {the_message}"
        )
        assert THE_POLICY_NAMESPACE in the_message, (
            "the refusal does not name the namespace a deployment must not write, which is the "
            f"half of the mistake worth showing somebody. It said: {the_message}"
        )
