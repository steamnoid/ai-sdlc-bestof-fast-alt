"""The repair supervisor, against a real model, a real card and a real refusal.

**This is the only stage of a run whose answer is a destination rather than a document, and it
is the only one whose model has never been watched deciding.** Every other agent this tier
proves alone is handed a repository or an approved document and produces an artifact somebody
can read. This one is handed a card and a refusal and produces a `Command`, so the thing that
can be wrong is not the words — it is where the run goes next. **A `Command` naming a node the
graph does not contain stops a run twenty minutes in with a message about a graph**, and this
repository's own account is that every repair here died of the wiring while every routing test
passed, because a routing test calls the function and reads what it returns.

**So the assertion is about the outcome and not the verdict.** A real model is free to send the
run back to the planner, to send it back to the implementer, or to stand every agent down and
stop it — and all three are answers this system has somewhere to put, which is the whole claim
this file exists to make. What must not happen is the run dying of anything that is not one of
them, and the way that is asserted is by asking the built graph which nodes it registers rather
than by trusting the two literals the node happens to name today.

**A real refusal rather than a made-up one, and this is the most repairable there is.** The
implementer wrote a file back byte-for-byte is a refusal a planner's own `files_to_change`
produced and an implementer ignored, so *which agent was wrong* is not in doubt — which makes
it the right question to hand a model. What is asserted about the answer is that a verdict was
reached for every agent the run reasons with, because an answer about two of the seven is
indistinguishable from an answer about all of them and the run would read the five it was not
told about as standing down.

**The ceiling is stated rather than left to the default, and the arithmetic is the point.**
`AISDLC_REPEAT_BUDGET` is a deployment's ceiling on the supervisor's judgement, and the
supervisor stops a run when an agent it named has already had that many turns. The work item
below has had one implementer turn, so a ceiling of two leaves that agent one more and a
ceiling of one would stop this run before the model had been asked anything — **and a run
stopped by a number is a test that proved the number was read, which the default suite already
proves, and said nothing about whether a model can name a stage this graph has.**

**The card and the register live under a temporary directory, because both stages write.**
Leaving a decision is the supervisor's whole reason for existing — a run that repeats an agent's
work and leaves no record of why is a run whose second attempt is unexplainable to whoever reads
it third — and a test that let that write land in the repository would be leaving the very
artefact it is asserting about on the machine being tested.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

import pytest
from langgraph.types import Command

from aisdlc.domain.commissioned_request import a_request_about
from aisdlc.domain.repository import Repository
from aisdlc.domain.role import Role
from aisdlc.domain.the_work_each_agent_has_done import (
    TheWorkEachAgentHasDone,
    TheWorkOneAgentHasDone,
)
from aisdlc.domain.work_item import WorkItem, a_work_item_commissioned_for_an_agent
from aisdlc.graph.lifecycle import the_lifecycle
from aisdlc.graph.repeat_budget import THE_SETTING_NAMING_THE_REPEAT_BUDGET
from aisdlc.graph.supervise_a_repair import (
    TheRepeatBudgetRanOutError,
    TheSupervisorJudgedThisIsNotRepairingError,
    supervise_a_repair,
)
from aisdlc.graph.the_agents_a_run_reasons_with import THE_AGENTS_A_RUN_REASONS_WITH
from aisdlc.graph.the_agents_this_run import TheAgentsThisRun
from aisdlc.graph.the_prompt_to_supervise_a_repair import THE_AGENT_THAT_SUPERVISES_A_REPAIR
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.store.the_register_of_work_items import the_work_item_a_commission_registers
from aisdlc.store.where_the_register_lives import holding_the_register
from aisdlc.tools.what_people_said_about_a_work_item import (
    AComment,
    a_comment_was_left,
    what_people_said_about,
)

pytestmark = pytest.mark.e2e

THE_DEVELOPER_IMPLEMENTATION_AGENT = "aisdlc-dev-impl"
"""The agent whose turn this work item has already had, named rather than repeated as a literal."""

THE_WORK_ITEM_THIS_RUN_IS_REPAIRING = "issue-201"
"""One name for the work item, because the card is read by name and so is the register."""

HOW_MANY_REPEATS_THIS_TEST_STATES = 2
"""The ceiling this run is judged under — the arithmetic is in the module docstring."""

WHAT_STOPPED_THE_RUN = (
    "The implementer wrote tests/test_the_api.py back byte-for-byte, and the suite passes "
    "identically with the file present and deleted. The plan named that file and said what to "
    "change in it, and the diff is empty."
)
"""The refusal in the words a real implementer's own refusal carries, and not a summary of it."""


class WhatTheSupervisorSaid(NamedTuple):
    """One real call's whole outcome, because a supervisor has two ways to end and both count.

    **Both halves, and not an exception that was caught and thrown away.** A fixture that let
    either error escape would fail the run for an answer the system gave on purpose, and a
    fixture that swallowed everything would pass a run that died of something else. Anything
    outside these two travels out of here untouched, so a wiring failure still arrives with its
    own traceback rather than as this file's verdict.
    """

    where_it_says_to_start_again: Command | None
    the_refusal_it_raised: Exception | None


@pytest.fixture(scope="module")
def a_register_and_a_projects_root_under_a_temporary_directory(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """A register and a projects root, both in a directory pytest will delete.

    **The register is opened as well as the root, because leaving a note writes to both.** A
    comment beside the clone and a row a board reads are the same note written once, so a
    supervisor that cannot reach the register stops at the moment it decides anything — and a
    test that let that write land anywhere else would be writing a SQLite file into whatever
    directory the process happened to start in.
    """
    a_temporary_directory = tmp_path_factory.mktemp("this-run-repaired")
    return a_temporary_directory / "projects"


def _with_one_implementer_turn_spent(work_item: WorkItem) -> WorkItem:
    """This work item with the implementer having already had one turn on it.

    **Set by hand rather than by walking the table, and that is what this file is not about.**
    A run earns that count by being run, and it is here because the ceiling is checked against
    it: an agent with no turns can never be out of turns, so a work item without one would make
    the ceiling unreachable and leave this file measuring the prompt rather than the decision.
    """
    return work_item.model_copy(
        update={
            "work_done": TheWorkEachAgentHasDone(
                worked=(
                    TheWorkOneAgentHasDone(
                        agent=THE_DEVELOPER_IMPLEMENTATION_AGENT, how_many_times=1
                    ),
                )
            )
        }
    )


@pytest.fixture(scope="module")
def the_work_item_through_one_attempt(
    the_repository: Repository,
    a_register_and_a_projects_root_under_a_temporary_directory: Path,
) -> WorkItem:
    """A work item an implementer has already worked on, registered and carrying its own note.

    **The register is written because a resumed run reads its card from there, and a work item
    nobody commissioned is not the one a supervisor is about.** The note is the implementer's,
    because a card with nothing on it is the first thing this stage would never see in a real
    run: the supervisor's question is built from what every earlier agent said, and a card with
    no notes on it is a card where the only judgement is about to be the model in this file.
    """
    the_work_item = _with_one_implementer_turn_spent(
        a_work_item_commissioned_for_an_agent(
            work_item_id=THE_WORK_ITEM_THIS_RUN_IS_REPAIRING,
            repository=the_repository,
            accountable_role=Role.DEV,
            commissioned_by="a person reading a test",
            requested=a_request_about("name the Node version the project is developed against"),
        )
    )

    with holding_the_register() as the_register:
        the_work_item_a_commission_registers(the_register, the_work_item)

    a_comment_was_left(
        the_work_item,
        what_was_said=(
            "wrote the file the plan named and the diff came back empty; I cannot tell whether "
            "the plan meant to replace the handler or to add one beside it"
        ),
        by=THE_DEVELOPER_IMPLEMENTATION_AGENT,
        at=datetime.now(UTC),
        projects_root=a_register_and_a_projects_root_under_a_temporary_directory,
    )
    return the_work_item


@pytest.fixture(scope="module")
def a_repeat_budget_this_run_may_spend() -> Iterator[None]:
    """The deployment's ceiling on repeats, stated for the length of this module.

    **`pytest.MonkeyPatch` of this fixture's own, because a module-scoped fixture cannot take
    the function-scoped one pytest hands out.** The budget is read at the moment the supervisor
    asks for it, so it has to be in the environment for the whole call and not restored before
    it. The number is the one the module docstring argues for: the implementer has had a turn
    and the ceiling is two, so nothing here can stop the run except the model's own judgement.
    """
    the_deployments_own_ceiling = pytest.MonkeyPatch()
    the_deployments_own_ceiling.setenv(
        THE_SETTING_NAMING_THE_REPEAT_BUDGET, str(HOW_MANY_REPEATS_THIS_TEST_STATES)
    )
    yield
    the_deployments_own_ceiling.undo()


@pytest.fixture(scope="module")
def a_real_supervision(
    the_work_item_through_one_attempt: WorkItem,
    a_register_and_a_projects_root_under_a_temporary_directory: Path,
    a_repeat_budget_this_run_may_spend: None,
    the_model_for,
    request,
) -> WhatTheSupervisorSaid:
    """One real decision about a real refusal, shared by every assertion about it.

    **One call for the whole module, because a second one would be a different run.** A model
    asked the same question twice can answer two different ways, so asserting the six sentences
    of a decision against six decisions would be asserting that the model varies — which is
    true and is not what this file is for. The provider is `request.param` and the tests
    parametrise it indirectly, so a deployment configured for one provider *skips* the others
    with the reason printed.

    **And which of the three answers this run got is printed, because the assertions accept all
    of them.** A test that passes on either verdict is right to, and a reader of a passing run
    is left knowing that rather than knowing *which* happened — which is the fact worth having
    when somebody asks whether the supervisor is doing anything. Pytest captures this and shows
    it only on failure, so `-s` is how a run says it out loud.
    """
    try:
        the_outcome = WhatTheSupervisorSaid(
            where_it_says_to_start_again=supervise_a_repair(
                the_work_item_through_one_attempt,
                a_register_and_a_projects_root_under_a_temporary_directory,
                WHAT_STOPPED_THE_RUN,
                the_model_for(request.param),
            ),
            the_refusal_it_raised=None,
        )
    except (
        TheSupervisorJudgedThisIsNotRepairingError,
        TheRepeatBudgetRanOutError,
    ) as refused:
        the_outcome = WhatTheSupervisorSaid(
            where_it_says_to_start_again=None, the_refusal_it_raised=refused
        )

    print(
        "\nA REAL MODEL SUPERVISING A REPAIR:",
        f"sent the run back to {the_outcome.where_it_says_to_start_again.goto}"
        if the_outcome.the_refusal_it_raised is None
        else f"stopped the run — {the_outcome.the_refusal_it_raised}",
        flush=True,
    )
    return the_outcome


def the_nodes_this_graph_registers() -> frozenset[str]:
    """Every node name the built lifecycle holds, asked of the graph rather than of the source.

    **The graph is compiled here and its node list read, because a list of literals typed into
    this file is a second copy of the graph.** A `goto` is a node name, and the only thing that
    settles whether one exists is the graph itself — a check that compared a destination against
    a hand-written pair of names would pass for ever if either name were renamed on one side
    only. Every collaborator raises, because nothing here runs a run: the cast is only what the
    compiler needs to have a name to attach.
    """

    def a_collaborator_nobody_asked_for(*_arguments: object, **_keywords: object) -> object:
        """A collaborator that refuses, so a test cannot reach one by accident."""
        raise AssertionError("this file builds the graph to read its nodes and runs nothing in it")

    from aisdlc.domain.repository import Repository
    from aisdlc.graph.the_delivery_of_this_run import TheDeliveryOfThisRun

    the_graph = the_lifecycle(
        agents=TheAgentsThisRun(
            discover=a_collaborator_nobody_asked_for,
            propose_requirements=a_collaborator_nobody_asked_for,
            plan_the_tests=a_collaborator_nobody_asked_for,
            describe_the_architecture=a_collaborator_nobody_asked_for,
            inspect_for_security=a_collaborator_nobody_asked_for,
            plan=a_collaborator_nobody_asked_for,
            apply_and_verify=a_collaborator_nobody_asked_for,
        ),
        delivery=TheDeliveryOfThisRun(
            our_copy=Repository(owner="nobody", name="asked-for-nothing"),
            push_the_branch=a_collaborator_nobody_asked_for,
            open_the_pull_request=a_collaborator_nobody_asked_for,
            ask_whether_the_suite_went_green=a_collaborator_nobody_asked_for,
            merge_the_pull_request=a_collaborator_nobody_asked_for,
            rebase_the_branch_a_run_pushed=a_collaborator_nobody_asked_for,
        ),
    )

    return frozenset(the_graph.get_graph().nodes)


def _the_one_note_the_supervisor_left(
    the_repository: Repository, a_projects_root: Path
) -> AComment:
    """The single note the supervisor put on this card, or a refusal naming how many there are."""
    the_notes_it_left = [
        a_note
        for a_note in what_people_said_about(
            the_repository, THE_WORK_ITEM_THIS_RUN_IS_REPAIRING, a_projects_root
        ).comments
        if a_note.said_by == THE_AGENT_THAT_SUPERVISES_A_REPAIR
    ]

    if len(the_notes_it_left) != 1:
        raise AssertionError(
            f"the card carries {len(the_notes_it_left)} notes from "
            f"{THE_AGENT_THAT_SUPERVISES_A_REPAIR} and this file reads one. A supervisor that "
            "leaves no note before it acts is the defect this whole file exists to catch, and one "
            "that leaves two is two records of one decision able to disagree"
        )
    return the_notes_it_left[0]


def _what_has_not_changed_as_the_card_reads(what_the_supervisor_said: str) -> str:
    """The sentence the supervisor named, read off the card rather than off the model.

    **The first line, and the reason is that this is what the refusal quotes.** The refusal
    carries `what_has_not_changed` verbatim, so any part of it shows the sentence travelling
    from the model into the record a reader finds — and reading the first line means a model
    that wrote a paragraph, or a bullet list, cannot make this file fail over its own parsing.
    """
    the_line_naming_it = what_the_supervisor_said.split("what has not changed: ", 1)[1]
    return the_line_naming_it.splitlines()[0].strip()


@pytest.mark.parametrize("a_real_supervision", list(LlmProvider), indirect=True)
def test_the_run_ends_somewhere_this_graph_has_a_node_for(
    a_real_supervision: WhatTheSupervisorSaid,
) -> None:
    """A destination the graph holds, or one of the two refusals that end a run on purpose.

    **Both are answers, and neither is asserted for.** A model that sent the run back to the
    planner and a model that stood every agent down have both been right, and a test that wanted
    one of them would be testing the model rather than the system — and would fail on a good
    answer. What is refused is everything else: a destination this graph does not contain, a
    refusal that is neither of the two named errors, and the two happening at once.

    **The node list is read off the compiled graph, so this cannot pass by agreeing with
    itself.** Every repair that broke in this repository broke between two stages that each
    looked right — a node that returned a `Command` and also carried an edge — and the only
    thing that catches a shape like that is building the thing and asking what it holds.
    """
    the_nodes = the_nodes_this_graph_registers()

    assert the_nodes, (
        "the graph this file asked for its node names holds none, so every destination would be "
        "contained in it and this assertion could not fail"
    )
    both_places_a_run_may_start_again = {
        "offer_the_work_item_to_the_planner",
        "offer_the_work_item_to_the_implementer",
    }
    assert both_places_a_run_may_start_again <= the_nodes, (
        f"{sorted(both_places_a_run_may_start_again - the_nodes)} are not in the graph, so a run "
        "put back to one of them stops for a reason that is a rename rather than a judgement"
    )

    if a_real_supervision.the_refusal_it_raised is not None:
        assert isinstance(
            a_real_supervision.the_refusal_it_raised,
            TheSupervisorJudgedThisIsNotRepairingError | TheRepeatBudgetRanOutError,
        ), (
            f"the supervisor ended this run with "
            f"{type(a_real_supervision.the_refusal_it_raised).__name__}, which is not one of the "
            "two ways a repair loop is allowed to end. A run that stops for a third reason stops "
            "with nothing on the card to say why, and the run never got to show whether the "
            "wiring is sound"
        )
        assert a_real_supervision.where_it_says_to_start_again is None, (
            "the supervisor both refused and named a destination, so a reader of this run cannot "
            "tell whether it stopped or continued — and the two must not look alike in a record"
        )
        return

    the_destination = a_real_supervision.where_it_says_to_start_again
    assert isinstance(the_destination, Command), (
        f"the supervisor answered with {type(the_destination).__name__} rather than a Command "
        "naming where the run starts again, so nothing downstream can rely on where it went"
    )
    assert the_destination.goto in the_nodes, (
        f"a real model was asked where this run should start again and it was sent to "
        f"{the_destination.goto!r}, which is not a node this graph holds. A destination with no "
        "node behind it is a run that stops for ever with no refusal to show, and the set of "
        "places a run may be put back to is two literals in one function — so a model reaching a "
        "third is the whole wiring being wrong, which is what this file was written to catch"
    )


@pytest.mark.parametrize("a_real_supervision", list(LlmProvider), indirect=True)
def test_a_decision_was_left_on_the_card_with_a_verdict_for_every_agent(
    a_real_supervision: WhatTheSupervisorSaid,
    the_repository: Repository,
    a_register_and_a_projects_root_under_a_temporary_directory: Path,
    the_placeholders: frozenset[str],
) -> None:
    """The card says where the run starts again, and what each of the run's agents must do.

    **Every agent, and that is the claim.** `WhatToRepeat` refuses an answer that is silent
    about one of the seven, because a run cannot tell an agent that had nothing to do from an
    agent nobody spoke about — and a model is the only thing here that can be silent. Asserting
    it on the card rather than on a returned decision is deliberate: the card is what a person
    reads when deciding whether the repair was justified, and a card carrying a decision this
    file cannot find is a card that says nothing.

    **Non-empty and not placeholder, on the whole note and not only on its headings.** A real
    model filled this system's shape with five blank sentences once, and a record of a judgement
    with nothing in it is a record of a decision nobody made.
    """
    what_the_supervisor_said = _the_one_note_the_supervisor_left(
        the_repository, a_register_and_a_projects_root_under_a_temporary_directory
    ).what_was_said

    assert what_the_supervisor_said.strip(), (
        f"{THE_AGENT_THAT_SUPERVISES_A_REPAIR} left an empty note. A run that repeats an agent's "
        "work and leaves no record of why is a run whose second attempt is unexplainable to "
        "whoever reads it third"
    )
    assert what_the_supervisor_said.strip().lower() not in the_placeholders, (
        "the note is placeholder text, which means the model returned a shape rather than a "
        "judgement and the card now reads as though somebody had decided something"
    )
    assert "where this run starts again: " in what_the_supervisor_said, (
        "the note does not say where the run starts again, so a reader has to read the run's own "
        "state to learn which stage was sent back"
    )

    never_judged = [
        an_agent
        for an_agent in THE_AGENTS_A_RUN_REASONS_WITH
        if f"- {an_agent}:" not in what_the_supervisor_said
    ]
    assert not never_judged, (
        f"{never_judged} have no verdict on a card a real model filled, and that card is what a "
        "person reads to judge the repair. The set of agents a run reasons with is read out of "
        "production rather than written here, and an agent missing from the card is one the run "
        "will read as standing down whether or not anybody said so"
    )


@pytest.mark.parametrize("a_real_supervision", list(LlmProvider), indirect=True)
def test_a_run_that_stopped_says_which_sentence_had_not_changed(
    a_real_supervision: WhatTheSupervisorSaid,
    the_repository: Repository,
    a_register_and_a_projects_root_under_a_temporary_directory: Path,
    the_placeholders: frozenset[str],
) -> None:
    """When the model stood every agent down, the refusal carries the sentence it gave.

    **A stop has to name the thing that has not moved, or it is a mood the run acted on.** A
    model asked whether another attempt is worth it has very little reason to say no, so the
    only thing that makes a stop a decision is that its reason can be read and argued with. The
    sentence is read off the card — the record a person finds — and then looked for in the
    refusal, so what is asserted is that the two agree and not that either one exists.

    **The card is checked first and unconditionally, and the refusal only when there is one.** A
    model that sent the run back to the implementer wrote the same sentence onto the same card,
    which is the claim of the test above; a sentence nothing checks is the part of this stage
    that would rot.
    """
    what_the_supervisor_said = _the_one_note_the_supervisor_left(
        the_repository, a_register_and_a_projects_root_under_a_temporary_directory
    ).what_was_said
    what_has_not_changed = _what_has_not_changed_as_the_card_reads(what_the_supervisor_said)

    assert what_has_not_changed.strip(), (
        "the card names no sentence under `what has not changed`, so a reader of this run finds a "
        "decision and not a reason for it"
    )
    assert what_has_not_changed.strip().lower() not in the_placeholders, (
        f"{what_has_not_changed!r} is placeholder text standing in for the model's judgement, "
        "which means the card reads as a decision while naming nothing anybody can argue with"
    )

    if a_real_supervision.the_refusal_it_raised is None:
        return

    assert what_has_not_changed in str(a_real_supervision.the_refusal_it_raised), (
        f"this run stopped, and the refusal does not carry the sentence the supervisor wrote on "
        f"the card ({what_has_not_changed!r}). The two are the same decision, and a reader who "
        "finds one in a trace and the other on the card is reading two records that can disagree"
    )
