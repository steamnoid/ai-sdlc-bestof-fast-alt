"""A supervisor that cannot reach a verdict ends the run with a reason, not a traceback.

**A real run reached the repair loop for the first time in this copy's history and died there.**
Six gates approved, the plan approved, the implementation written, the repository's own suite run
three times in a container — and then the repair supervisor asked a model what to repeat, the
answer did not validate, and the run ended with:

    ValidationError: 1 validation error for WhatToRepeat
    raise ARefusalWithNoReasonToRepairError

**`WhatToRepeat` is strict on purpose, and the strictness is correct.** Every agent in the run
must be given a verdict, because an agent the model left out is indistinguishable from an agent
that had nothing to do; a decision to stop must name what has not changed, because *"this is not
working"* is a mood the run acted on. Those validators are the rules that make a supervisor's
answer mean anything.

**The gap is that nothing handles them.** `supervise_a_repair` calls `model_validate` and lets
the `ValidationError` out — so a model that forgot one agent out of seven kills a run that had
already done everything else correctly. **And this is the one node in the pipeline with no
correction loop**: discovery, the product analyst, the QA analyst, the architect, the security
analyst, the planner and the implementer each spend from the shared budget to ask again, and the
supervisor asks once and propagates. The run ends on a Python exception rather than on a
decision, which is the outcome this repository's own rule exists to prevent — *a refusal is a
decision and is recorded as one*.

**So the answer cannot validate, and the run stops with the validation's own words on the card.**
`TheSupervisorJudgedThisIsNotRepairingError` is exactly that outcome and was previously reachable
only when a model said so in words. A model whose answer cannot be expressed has said nothing, and
a run that received nothing should stop for the same reason and say why.

**The double answers with real shapes and the register is opened for real**, because the first
version of this file did neither: it passed `repeat=` and `verdict=` where `WhatOneAgentMustDoAgain`
declares `must_repeat_its_work` and `why`, and it never opened the register, so the suite failed
at fixture setup with `NoRegisterHasBeenOpenedError` and proved nothing at all. A RED that dies in
its own scaffolding is not a RED — it is a test that cannot run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aisdlc.domain.commissioned_request import a_request_about
from aisdlc.domain.repository import Repository
from aisdlc.domain.role import Role
from aisdlc.domain.work_item import WorkItem, a_work_item_commissioned_for_an_agent
from aisdlc.graph.supervise_a_repair import (
    THE_AGENT_THAT_SUPERVISES_A_REPAIR,
    WHERE_THE_PLAN_IS_REWRITTEN,
    TheSupervisorJudgedThisIsNotRepairingError,
    supervise_a_repair,
)
from aisdlc.store.the_register_of_work_items import the_work_item_a_commission_registers
from aisdlc.store.where_the_register_lives import the_register, the_register_lives_at
from aisdlc.tools.what_people_said_about_a_work_item import what_people_said_about

A_REPOSITORY = Repository(owner="steamnoid", name="a-project")
A_WORK_ITEM_ID = "a-work-item-that-reached-the-supervisor"
WHAT_STOPPED_THE_RUN = (
    "The suite passed identically with package.json changed and with it deleted, so nothing "
    "observed the change."
)

EVERY_AGENT_A_RUN_REASONS_WITH = (
    "aisdlc-discover",
    "aisdlc-po-analyze",
    "aisdlc-qa-analyze",
    "aisdlc-arch-analyze",
    "aisdlc-sec-analyze",
    "aisdlc-dev-plan",
    "aisdlc-dev-impl",
)


class AModelAnsweringWith:
    """A model that answers with whatever it was given, in the shape production asks for.

    **Answers data and never raises, because a double that raised would be testing the
    framework.** The defect under test is a node letting a `ValidationError` out; the double's job
    is to hand over an answer the type refuses and let the node decide what that means.
    """

    def __init__(self, the_answer: dict[str, object]) -> None:
        self.the_answer = the_answer
        self.what_it_was_asked = 0

    def with_structured_output(self, _the_artifact: object, **_keywords: object) -> object:
        the_model = self

        class ABound:
            def invoke(self, _the_question: str) -> dict[str, object]:
                the_model.what_it_was_asked += 1
                return the_model.the_answer

        return ABound()


def a_verdict(an_agent: str, must_repeat_its_work: bool = True) -> dict[str, object]:
    """One verdict in the shape `WhatOneAgentMustDoAgain` declares, named as it declares them.

    **Written out rather than built from the model, because the whole point of this file is the
    disagreement between what a model is asked for and what the artefact has.** A double built
    from the model would agree with it by construction and would have caught nothing.
    """
    return {
        "agent": an_agent,
        "must_repeat_its_work": must_repeat_its_work,
        "why": "the change was not written anywhere this run could see",
    }


@pytest.fixture
def a_projects_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Where every run's directory goes, told to the process and opened once, as production does."""
    monkeypatch.setenv("AISDLC_PROJECTS_DIR", str(tmp_path / "projects"))
    the_register_lives_at(tmp_path / "the-register.sqlite3")
    return tmp_path / "projects"


@pytest.fixture
def a_work_item_at_a_gate(a_projects_root: Path) -> WorkItem:
    """A commissioned work item, in the register the run's own nodes read the card from."""
    a_work_item = a_work_item_commissioned_for_an_agent(
        work_item_id=A_WORK_ITEM_ID,
        repository=A_REPOSITORY,
        accountable_role=Role.DEV,
        commissioned_by="a person in a terminal",
        requested=a_request_about("declare the Node version this project needs"),
    )
    return the_work_item_a_commission_registers(the_register(), a_work_item)


def test_a_supervisor_whose_answer_cannot_validate_stops_the_run_with_a_reason(
    a_work_item_at_a_gate: WorkItem, a_projects_root: Path
) -> None:
    """An unvalidatable answer ends the run the way a considered refusal ends it.

    **The answer is a real one that this system's own rules refuse**, not a malformed thing: two
    agents given verdicts and five forgotten, which is exactly the case the validator names and
    refuses by name.

    **And the refusal has to carry the validator's own words**, because the person reading the
    card afterwards is the one who can tell whether the run gave up or was told. A refusal that
    says only "the supervisor could not answer" sends a reader to look for a defect in the graph
    rather than in the model that answered it.
    """
    an_answer_forgetting_five_agents = {
        "what_each_agent_must_do": [
            a_verdict("aisdlc-dev-plan"),
            a_verdict("aisdlc-dev-impl"),
        ],
        "where_to_start_again": "the change is planned again",
        "what_has_not_changed": "nothing observes the change either way",
    }

    with pytest.raises(TheSupervisorJudgedThisIsNotRepairingError) as what_stopped_the_run:
        supervise_a_repair(
            a_work_item_at_a_gate,
            a_projects_root,
            WHAT_STOPPED_THE_RUN,
            AModelAnsweringWith(an_answer_forgetting_five_agents),  # type: ignore[arg-type]
        )

    the_refusal = str(what_stopped_the_run.value)

    for an_agent_the_model_forgot in ("aisdlc-discover", "aisdlc-po-analyze"):
        assert an_agent_the_model_forgot in the_refusal, (
            f"{an_agent_the_model_forgot} was one of the five the answer left out and the refusal "
            f"does not name it, so a reader cannot tell what the model got wrong: {the_refusal}"
        )


def test_the_run_is_told_its_supervisor_reached_no_verdict(
    a_work_item_at_a_gate: WorkItem, a_projects_root: Path
) -> None:
    """The card says the supervisor stopped here, because a quiet stop reads as finished.

    **Asked of what is on the card and not of the exception**, because the exception is this
    process's problem and the card is the next person's. A supervisor that raises and writes
    nothing leaves a card saying the run was refused for the reason the *implementer* gave — which
    is now a lie, because it was refused for a different reason entirely.

    **And the note is about the answer, not about the run.** The run's own reason is already on
    the card from the node that raised it; what is missing is the supervisor's verdict about it,
    and those are two different sentences.
    """
    an_answer_naming_no_verdict = {
        "what_each_agent_must_do": [],
        "where_to_start_again": "the change is planned again",
        "what_has_not_changed": "   ",
    }

    with pytest.raises(TheSupervisorJudgedThisIsNotRepairingError):
        supervise_a_repair(
            a_work_item_at_a_gate,
            a_projects_root,
            WHAT_STOPPED_THE_RUN,
            AModelAnsweringWith(an_answer_naming_no_verdict),  # type: ignore[arg-type]
        )

    what_the_run_said = what_people_said_about(
        a_work_item_at_a_gate.repository, a_work_item_at_a_gate.work_item_id, a_projects_root
    )

    the_supervisor_said_something = [
        a_comment
        for a_comment in what_the_run_said.comments
        if a_comment.said_by == THE_AGENT_THAT_SUPERVISES_A_REPAIR
    ]

    what_is_on_the_card = [
        (a_comment.said_by, a_comment.what_was_said) for a_comment in what_the_run_said.comments
    ]

    assert the_supervisor_said_something, (
        f"the supervisor refused and left nothing on the card under its own name: "
        f"{what_is_on_the_card}. A run that stops quietly reads as a run that finished, and this "
        "one did not finish — it "
        "ran out of verdicts with everything before it done correctly, and a person reading the "
        "card is the only one who will ever be told"
    )


def test_an_answer_nobody_asked_for_is_still_a_verdict_the_run_can_act_on(
    a_work_item_at_a_gate: WorkItem, a_projects_root: Path
) -> None:
    """A complete, self-consistent answer still routes, so the refusal above is about the failure.

    **The other direction, and it is what makes the two refusals above mean something.** If this
    node refused every answer, the refusals would be indistinguishable from a stage that never
    worked — and this repository has spent a week on guards that pass because they refuse
    nothing. So an answer with a verdict for every agent goes back to the planner, which is what
    the run asked the supervisor for and the only thing it can do next.

    **`Command.goto` and not the class of the exception**, because the routing is the claim. A
    supervisor that decided "not repairing" and a supervisor that could not decide look identical
    to a caller reading an exception type, and only the destination tells them apart.
    """
    a_complete_answer = {
        "what_each_agent_must_do": [
            a_verdict(an_agent) for an_agent in EVERY_AGENT_A_RUN_REASONS_WITH
        ],
        "where_to_start_again": "the change is planned again",
        "what_has_not_changed": "nothing observes the change either way",
    }

    where_the_run_went = supervise_a_repair(
        a_work_item_at_a_gate,
        a_projects_root,
        WHAT_STOPPED_THE_RUN,
        AModelAnsweringWith(a_complete_answer),  # type: ignore[arg-type]
    )

    assert where_the_run_went.goto == WHERE_THE_PLAN_IS_REWRITTEN, (
        f"a complete answer was sent to {where_the_run_went.goto!r} rather than to the planner, so "
        "the refusals above would be indistinguishable from a stage that never routed at all"
    )
