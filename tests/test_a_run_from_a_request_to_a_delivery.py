"""One run from an empty register to a delivered pull request, and a board that shows it.

**This is the whole product in one test, and it is the only test in the repository.** It exists
because the two projects this was assembled from each had half of it and neither had the whole:
one had a board over a store that nothing ever wrote, and the other had a pipeline that only
`pytest -m e2e` could start. So the question this file answers is the only one worth asking at
first — *does starting a run work, and does what comes out look right?*

**A real clone, a real state machine, real gates, a real register, a real HTTP request.** Four
things are replaced and each is named below. Everything else is production code on its real path,
because the parts being replaced are the parts that need a network and a model, and the parts
that are *not* replaced are exactly the ones this product is a claim about: that a work item
cannot be moved illegally, that a gate suspends, that a decision reaches the board only through
the gate, and that a run which delivered says so in a column.

**A local bare repository rather than a fixture for the clone.** `git clone /some/path` needs no
network and is the same code that clones from GitHub, so the clone, the branch and the checkout
are genuinely exercised. A doubled clone would have left the most expensive step in the pipeline
unproven and made this file much shorter, which is not the same as better.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langgraph.types import Command

from aisdlc.agents.apply_the_plan import ADeliveredChange
from aisdlc.agents.architecture_report import ArchitectureReport
from aisdlc.agents.architecture_report_answer import ArchitectureReportAnswer
from aisdlc.agents.discovery_answer import DiscoveryAnswer
from aisdlc.agents.discovery_report import DiscoveryReport, EvidenceFile
from aisdlc.agents.implement_the_plan import AWriteThatChangesNothingError, FileToWrite
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.qa_plan import QaPlan
from aisdlc.agents.qa_plan_answer import QaPlanAnswer
from aisdlc.agents.requirements import Requirements
from aisdlc.agents.requirements_answer import RequirementsAnswer
from aisdlc.agents.security_report import SecurityReport
from aisdlc.agents.verification_report import VerificationReport
from aisdlc.agents.what_an_agent_judged import WhatAnAgentJudged
from aisdlc.agents.what_the_planner_concluded import ImplementationPlanAnswer
from aisdlc.application.a_run_being_assembled import a_run_beginning_at
from aisdlc.application.the_runs_this_process_is_holding import TheRunsThisProcessIsHolding
from aisdlc.approval.approval_decision import ApprovalDecision
from aisdlc.domain.commissioned_request import a_request_about
from aisdlc.domain.repository import Repository
from aisdlc.domain.role import Role
from aisdlc.domain.stage import Stage
from aisdlc.domain.work_item import a_work_item_commissioned_for_an_agent
from aisdlc.graph.lifecycle import a_config, the_lifecycle
from aisdlc.graph.router import WHERE_AN_APPROVED_ARTIFACT_LEADS
from aisdlc.graph.supervise_a_repair import WHERE_THE_IMPLEMENTATION_IS_REWRITTEN
from aisdlc.graph.the_agents_this_run import TheAgentsThisRun
from aisdlc.graph.the_delivery_of_this_run import TheDeliveryOfThisRun
from aisdlc.store.the_board_reads import AColumnOfTheBoard
from aisdlc.store.the_register_of_work_items import (
    the_work_item_a_commission_registers,
    the_work_item_registered_at,
)
from aisdlc.store.where_the_register_lives import holding_the_register, the_register_lives_at
from aisdlc.tools.github_client import Addresses
from aisdlc.tools.github_clone_repository import RepositoryToClone
from aisdlc.tools.github_create_branch import PushedBranch
from aisdlc.tools.github_create_pull_request import AnOpenedPullRequest
from aisdlc.tools.run_tests import SuiteOutcome
from aisdlc.web.the_api import the_api_over

A_REPOSITORY = Repository(owner="pikuniu", name="a-project")
A_MOMENT = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
HOW_LONG_A_SMOKE_MAY_WAIT_IN_SECONDS = 30.0
HOW_MANY_TIMES_A_BOARD_MAY_BE_BUSY = 20
"""How many times this test asks again while the board is still walking from the previous gate.

**Twenty, and the number is about the ceiling rather than the patience.** A run between two gates
with no model in it is fast, and this test uses faked agents — so a run that is still busy after
twenty re-reads is not busy, it is broken, and the test says so rather than waiting longer. The
alternative is a fixed sleep, which is either too short and fails for having been impatient or too
long and is paid on every run.
"""


# ---------------------------------------------------------------------------
# A real repository, made locally, because the clone is the step worth proving.
# ---------------------------------------------------------------------------


@pytest.fixture
def a_repository_to_clone_into(tmp_path: Path) -> Path:
    """A bare repository with one commit in it, on this machine, reachable by `git clone`.

    **A real `git init`, a real commit and a real bare remote.** The run under test then clones
    it with the same `git clone` it would use for a public repository, which means the expensive
    step is exercised rather than stubbed — and the test needs no network, no credential and no
    fixture that lies about what a clone is.
    """
    the_bare = tmp_path / "the-origin.git"
    the_bare.mkdir()
    _git(the_bare, "init", "--bare", "--initial-branch=main")

    a_working_copy = tmp_path / "a-working-copy"
    a_working_copy.mkdir()
    _git(a_working_copy, "init", "--initial-branch=main")
    _git(a_working_copy, "config", "user.email", "a-run@example.com")
    _git(a_working_copy, "config", "user.name", "a run")
    (a_working_copy / "README.md").write_text("# a project\n", encoding="utf-8")
    (a_working_copy / "test_thing.py").write_text(
        "def test_the_thing():\n    assert True\n", encoding="utf-8"
    )
    _git(a_working_copy, "add", ".")
    _git(a_working_copy, "commit", "-m", "the first commit")
    _git(a_working_copy, "remote", "add", "origin", str(the_bare))
    _git(a_working_copy, "push", "origin", "main")

    return the_bare


def _git(where: Path, *what: str) -> str:
    """One `git` call in one directory, and its output if it failed.

    **Loud rather than quiet**, because a clone that failed for a reason nobody read is the
    exact shape of a test that passes for the wrong reason — the assertion after it never runs.
    """
    what_happened = subprocess.run(
        ["git", *what], cwd=where, capture_output=True, text=True, check=False
    )
    if what_happened.returncode != 0:
        pytest.fail(f"git {' '.join(what)} in {where} failed: {what_happened.stderr}")
    return what_happened.stdout


# ---------------------------------------------------------------------------
# The four things this test replaces, and one line each saying which.
# ---------------------------------------------------------------------------


def _the_agents_no_model_would_produce() -> TheAgentsThisRun:
    """Every agent answered without a model, which is the first of the four replacements.

    **The seven seams are the production seams, in the production shapes.** Each is a plain
    callable taking the same arguments the real agent takes, and each returns the same
    `(artifact, answer)` pair — so the graph is handed exactly what a real run hands it, and the
    only thing missing is the reasoning. What the run *does* with the answer: the gate, the
    record, the board, the delivery, is entirely production code.

    **Every answer carries a `judged`**, because that is where the note a person reads on the
    card comes from. An agent that returned an artifact with no judgement would leave a card with
    no note on it, and the board would show a run that produced artifacts and never said what it
    concluded about them.
    """
    the_judged = WhatAnAgentJudged(
        what_it_found="one commit and one test",
        what_it_could_not_settle="whether the database is reachable in production",
        what_it_expects_next="the next agent reads what this one found",
    )

    def discover(clone, repository) -> tuple[DiscoveryReport, DiscoveryAnswer]:
        # **The answer holds paths and the report holds links, and that is the production split.**
        # A model is given the paths it concluded something from and the address is derived from
        # the repository, because a model asked for a link will name a host it likes. So the fake
        # answers in paths and builds the report the way the real node does.
        the_paths = ["README.md", "test_thing.py"]
        return (
            DiscoveryReport(
                languages=["Python"],
                architecture_summary="a single module and a test beside it",
                key_components=["test_thing.py"],
                evidence_files=[
                    EvidenceFile(path=a_path, link=f"local://{repository.address}/{a_path}")
                    for a_path in the_paths
                ],
            ),
            DiscoveryAnswer(
                languages=["Python"],
                architecture_summary="a single module and a test beside it",
                key_components=["test_thing.py"],
                evidence_files=the_paths,
                judged=the_judged,
            ),
        )

    def propose_requirements(
        clone, repository, requested
    ) -> tuple[Requirements, RequirementsAnswer]:
        the_found = {
            "requirements": ["an unauthenticated health endpoint"],
            "acceptance_criteria": ["the suite's file count goes up by one"],
        }
        return (
            Requirements(**the_found),
            RequirementsAnswer(judged=the_judged, **the_found),
        )

    def plan_the_tests(requirements) -> tuple[QaPlan, QaPlanAnswer]:
        the_found = {
            "test_strategy": "run the suite and count the files it collects",
            "scenarios": ["a call to the health endpoint answers"],
        }
        return QaPlan(**the_found), QaPlanAnswer(judged=the_judged, **the_found)

    def describe_the_architecture(
        clone, repository
    ) -> tuple[ArchitectureReport, ArchitectureReportAnswer]:
        the_found = {
            "findings": ["one module, no boundaries drawn yet"],
            "modules": ["test_thing.py"],
            "boundaries": ["the endpoint and the thing it reports on"],
        }
        return (
            ArchitectureReport(**the_found),
            ArchitectureReportAnswer(judged=the_judged, **the_found),
        )

    def inspect_for_security(clone, repository) -> SecurityReport:
        # **An account and no finding, never an empty report.** A report with neither is refused
        # by the artifact's own rule, because a reader cannot tell a repository that was
        # examined and found clean from one no analyst ever looked at.
        return SecurityReport(nothing_found_because="one commit of markdown and one trivial test")

    def plan(
        requirements, clone, repository, what_the_suite_announced=""
    ) -> ImplementationPlanAnswer:
        return ImplementationPlanAnswer(
            judged=the_judged,
            plan=ImplementationPlan(
                files_to_add=["health.py"],
                tests_to_add=["test_health.py"],
            ),
        )

    def apply_and_verify(clone, repository, implementation_plan) -> ADeliveredChange:
        a_suite_that_passed = SuiteOutcome(
            exit_code=0,
            passed=True,
            dependencies_installed=True,
            output="1 passed",
        )
        return ADeliveredChange(
            written=[
                FileToWrite(path="health.py", content="def health():\n    return {'ok': True}\n")
            ],
            verification=VerificationReport(
                suite_before_the_change=a_suite_that_passed,
                suite_after_the_change=a_suite_that_passed,
            ),
            what_the_implementer_said="added the endpoint the requirements asked for",
        )

    def supervise(work_item, projects_root, what_the_run_stopped_on) -> object:
        """The production arity, so a run that reaches this fails with the reason, not a TypeError.

        **This takes three arguments because the graph calls it with three, and that is not a
        detail.** A one-argument version raises `TypeError` on the way in, so the failure a
        reader sees is about plumbing — "supervisor() takes 1 positional argument but 3 were
        given" — and never about the thing the sentence below is for, which is that a repair on a
        run whose stages never refuse means something upstream is broken. The message is the
        point of the double and an arity error replaces it.
        """
        pytest.fail(
            f"the supervisor was asked about {what_the_run_stopped_on!r} on a run whose stages "
            "never refuse, so a repair here means something upstream is broken and the run "
            "should have carried on"
        )

    return TheAgentsThisRun(
        discover=discover,
        propose_requirements=propose_requirements,
        plan_the_tests=plan_the_tests,
        describe_the_architecture=describe_the_architecture,
        inspect_for_security=inspect_for_security,
        plan=plan,
        apply_and_verify=apply_and_verify,
        supervise=supervise,
    )


def _a_delivery_that_only_writes_down(clone_path: Path) -> TheDeliveryOfThisRun:
    """The second replacement: a delivery that reports what it would have done.

    **A `PushedBranch` and an `AnOpenedPullRequest` with real numbers.** The graph's delivery node
    decides *whether* to deliver and asks these two collaborators to do it; what they do is a
    network call. So they are the seam, and the decision — the last gate, the refusal check, the
    move to `DONE` — is production code being tested.
    """
    return TheDeliveryOfThisRun(
        our_copy=A_REPOSITORY,
        push_the_branch=lambda the_clone, name: PushedBranch(
            name=name, address=f"local://{clone_path}/branch/{name}"
        ),
        open_the_pull_request=lambda what_to_open: AnOpenedPullRequest(
            number=1, address="https://example.invalid/paligakrzychu/a-project/pull/1"
        ),
    )


def _cloning_from_a_local_repository(the_bare: Path):
    """The third replacement: clone from a path on this machine instead of from GitHub.

    **A real `git clone` of a real repository.** The only thing changed is the address, which is
    the one field `Addresses` exists to vary — fetched from somewhere writable, the code came
    from somewhere readable. Everything the clone node does around it is production code.
    """

    def planning(source: Repository, into: Path) -> RepositoryToClone:
        return RepositoryToClone(
            repository=source,
            addresses=Addresses(fetch_from=str(the_bare), origin_of_the_code=str(the_bare)),
            into=into,
        )

    return planning


# ---------------------------------------------------------------------------
# The run, and the board it has to end up on.
# ---------------------------------------------------------------------------


@pytest.fixture
def a_register_and_a_projects_root(tmp_path: Path, monkeypatch) -> tuple[sqlite3.Connection, Path]:
    """An empty register and a projects root, with the process told where both are.

    **`the_register_lives_at` rather than a connection threaded through everything.** The graph's
    nodes are handed the state and nothing else, so the connection cannot travel in the state
    without putting a database cursor in a `TypedDict` of domain values. The composition root
    opens it once and the recorders read it, which is the same door the board reads.
    """
    monkeypatch.setenv("AISDLC_PROJECTS_DIR", str(tmp_path / "projects"))
    the_register_lives_at(tmp_path / "the-register.sqlite3")
    return _the_open_register(), tmp_path / "projects"


def _the_open_register() -> sqlite3.Connection:
    from aisdlc.store.where_the_register_lives import the_register

    return the_register()


def test_a_run_started_from_the_board_reaches_delivered(
    a_repository_to_clone_into: Path, a_register_and_a_projects_root, tmp_path: Path
) -> None:
    """A person posts a repository and a sentence, answers eight gates, and gets a pull request.

    **The whole product, and the eight gates are answered one at a time on purpose.** A run
    answered by a policy never suspends, so a smoke test that approved everything at once would
    never reach a board showing a card waiting for somebody — and that card is the thing this
    repository is for. So each answer is posted, and between two of them the board is read to
    prove the run is standing at a gate rather than past it.
    """
    _, the_projects_root = a_register_and_a_projects_root
    os.environ["AISDLC_PROJECTS_DIR"] = str(the_projects_root)

    the_runs = _the_runs_holding_a_run_built_out_of_fakes(a_repository_to_clone_into)
    with TestClient(the_api_over(_the_open_register(), the_runs)) as the_board:
        started = the_board.post(
            "/api/runs",
            json={
                "repository_owner": A_REPOSITORY.owner,
                "repository_name": A_REPOSITORY.name,
                "asked_for": "add a health endpoint that answers",
            },
        )

        assert started.status_code == 200, started.text
        the_work_item_id = started.json()["work_item_id"]

        # **A card exists before the run has done anything.** A request that returned after four
        # minutes of cloning would be indistinguishable from a request the server dropped.
        the_first_reading = the_board.get("/api/board").json()
        assert [a_card["work_item_id"] for a_card in the_first_reading["cards"]] == [
            the_work_item_id
        ], (
            "a card has to be on the board the moment the request is accepted, not when the "
            "run reaches a gate"
        )

        already_answered: set[str] = set()
        for _gate in range(1, _how_many_gates_there_are() + 1):
            _answer_the_gate_now_showing(
                the_board,
                the_runs,
                the_work_item_id,
                already_answered,
                True,
                "it answers the request",
            )

        _wait_until_the_run_has_finished(the_board, the_work_item_id)

    # **The card is in the delivered column, and it is the only card.** Six stages, eight gates,
    # one pull request — and a board that showed anything else would be showing a second source
    # of truth.
    the_cards = the_board.get("/api/board").json()["cards"]
    assert len(the_cards) == 1, f"a run should have left one card and left {len(the_cards)}"
    the_card = the_cards[0]

    assert the_card["column"] == AColumnOfTheBoard.DELIVERED.value, (
        f"the card is in {the_card['column']!r} rather than delivered, at stage "
        f"{the_card['stage']!r}"
    )
    assert the_card["stage"] == Stage.DONE.name
    assert the_card["how_many_gates_it_has_been_through"] == 8, (
        "eight gates, and a run that recorded a different number answered a different number of "
        "them — the card is counting decisions, so this is a fact and not a display"
    )

    # **The work item really is at `DONE`, read back out of the register.** The card is a
    # projection; this is the fact it projects. A card saying "delivered" over a work item at
    # `AWAITING_HUMAN_APPROVAL` is the exact shape of bug this store was written to make
    # impossible, and reading it back is the cheapest way to be sure it is not happening.
    the_registered = the_work_item_registered_at(_the_open_register(), the_work_item_id)
    assert the_registered.stage is Stage.DONE, (
        f"the board says delivered and the register holds {the_registered.stage.name}. Two "
        "records of one run, telling two stories, is the failure this whole store exists to "
        "prevent — so this reads the register and not the card"
    )

    the_story = the_board.get(f"/api/runs/{the_work_item_id}").json()
    assert len(the_story["gates"]) == 8
    assert len(the_story["approvals"]) == 8, (
        "an approved gate leaves a record and a refused one does not, so eight approvals for "
        "eight answers is what an entirely approved run looks like"
    )
    assert all(a_gate["approved"] for a_gate in the_story["gates"])
    assert the_story["how_it_ended"] is None, (
        "this run delivered, so there is nothing to report about how it stopped"
    )
    assert any(
        "https://example.invalid" in a_line["what_happened"] for a_line in the_story["what_it_said"]
    ), "the address of the pull request has to reach the card — it is the run's whole output"


def test_a_refusal_ends_a_run_and_leaves_the_reason_on_the_card(
    a_repository_to_clone_into: Path, a_register_and_a_projects_root
) -> None:
    """Saying no at the second gate stops the run, and the card says who said it and why.

    **A refusal is a decision and not a gap**, so this asserts two things a run that merely
    stopped would fail: the decision is on the record, and no approval exists for it. A board
    built from approvals alone cannot show a gate somebody answered no to, which is the ordinary
    case rather than the rare one.
    """
    _, the_projects_root = a_register_and_a_projects_root
    os.environ["AISDLC_PROJECTS_DIR"] = str(the_projects_root)

    the_runs = _the_runs_holding_a_run_built_out_of_fakes(a_repository_to_clone_into)
    with TestClient(the_api_over(_the_open_register(), the_runs)) as the_board:
        started = the_board.post(
            "/api/runs",
            json={
                "repository_owner": A_REPOSITORY.owner,
                "repository_name": A_REPOSITORY.name,
                "asked_for": "add a health endpoint that answers",
            },
        )
        the_work_item_id = started.json()["work_item_id"]

        # **The set of gates this test has answered, and not the set the record holds.** The
        # record is written by the run's own thread, so a set read from it at the moment of the
        # wait can be a gate behind: the answer was posted and the run has not recorded it yet,
        # so the pending question is still gate one and the wait returns at once on a question the
        # run is about to clear. The test knows what it posted, and that is a fact about the test
        # rather than a fact about a race.
        already_answered: set[str] = set()

        _answer_the_gate_now_showing(
            the_board, the_runs, the_work_item_id, already_answered, True, "it is right"
        )
        _answer_the_gate_now_showing(
            the_board,
            the_runs,
            the_work_item_id,
            already_answered,
            False,
            "that is not the change I meant to ask for",
        )

        # **Wait for the refusal to reach the record, rather than reading on the strength of the
        # 200.** The answer is handed to a thread, and the thread is what writes it down; a test
        # that read immediately would be asserting about a run that had not finished reacting,
        # and it would pass or fail on how fast the machine is.
        _wait_until(
            lambda: len(the_board.get(f"/api/runs/{the_work_item_id}").json()["gates"]) == 2,
            f"the refusal at the second gate never reached the record on {the_work_item_id}",
        )

    the_story = the_board.get(f"/api/runs/{the_work_item_id}").json()

    assert len(the_story["gates"]) == 2
    assert len(the_story["approvals"]) == 1, (
        "a refusal leaves a decision and no approval, so one approval for two answers is what "
        "being refused looks like — a run that recorded two would be claiming a record exists "
        "for a decision that did not approve anything"
    )
    assert the_story["gates"][-1]["approved"] is False
    assert the_story["gates"][-1]["reason"] == "that is not the change I meant to ask for"

    the_card = the_story["card"]
    assert the_card["why_it_was_refused"] == "that is not the change I meant to ask for"
    assert the_card["who_refused_it"] == "pikuniu", (
        "the record names who decided, verbatim. A record naming anybody else is a forged audit "
        "trail and it looks exactly like the real thing at the moment somebody needs to tell "
        "them apart"
    )
    assert the_card["stage"] == Stage.AWAITING_HUMAN_APPROVAL.name, (
        "a refused run is left where it was refused, so a person can see it. A run that carried "
        "on would be doing the work anyway, and one that moved to DONE would be claiming a "
        "delivery nobody approved"
    )


def test_an_agent_may_not_answer_its_own_gate(
    a_repository_to_clone_into: Path, a_register_and_a_projects_root
) -> None:
    """An `aisdlc-` identifier posted as a decider is refused with the gate's own sentence.

    **The prohibition is an assertion and not a convention.** §11 forbids an agent approving an
    agent's output, and a boundary enforced only by a naming convention is a boundary the next
    agent written will cross. The `AgentDecidedError` exists to be raised, and this is where.
    """
    _, the_projects_root = a_register_and_a_projects_root
    os.environ["AISDLC_PROJECTS_DIR"] = str(the_projects_root)

    the_runs = _the_runs_holding_a_run_built_out_of_fakes(a_repository_to_clone_into)
    with TestClient(the_api_over(_the_open_register(), the_runs)) as the_board:
        started = the_board.post(
            "/api/runs",
            json={
                "repository_owner": A_REPOSITORY.owner,
                "repository_name": A_REPOSITORY.name,
                "asked_for": "add a health endpoint that answers",
            },
        )
        the_work_item_id = started.json()["work_item_id"]
        _wait_until_the_gate_is_asking(the_board, the_work_item_id, set())

        the_answer = the_board.post(
            f"/api/runs/{the_work_item_id}/decisions",
            json={
                "approved": True,
                "decided_by": "aisdlc-po-analyze",
                "reason": "I approved my own work",
            },
        )

    assert the_answer.status_code == 400
    assert "only a human" in the_answer.json()["detail"], (
        "the refusal has to reach a person as a sentence about the rule, not as a line number in "
        "a validation error — a browser shows this text and nobody is going to read a stack"
    )


# ---------------------------------------------------------------------------
# Waiting for a run, which is minutes of real work and must not be a fixed sleep.
# ---------------------------------------------------------------------------


def _the_runs_holding_a_run_built_out_of_fakes(
    the_bare: Path,
) -> TheRunsThisProcessIsHolding:
    """A holder whose runs are the real graph, the real clone and seven agents that did not ask.

    **The composition root is replaced and the graph is not.** `the_lifecycle` is the production
    wiring — every node, every edge, the router, the state machine, the gate, the delivery node —
    and this hands the holder a graph built by that function. What is replaced is the cast of
    agents and the two delivery collaborators, and the address the clone is fetched from.

    That split is the whole claim of this file: the pipeline is the product, and the pipeline is
    production code. A test that replaced the graph would be testing its own fakes, and a test
    that needed a credential would be testing that a deployment is configured.
    """
    from aisdlc.application.the_runs_this_process_is_holding import TheRunsThisProcessIsHolding

    def building_the_graph(source: Repository, the_model: object = None) -> object:
        return the_lifecycle(
            agents=_the_agents_no_model_would_produce(),
            delivery=_a_delivery_that_only_writes_down(the_bare),
            plan_the_clone=_cloning_from_a_local_repository(the_bare),
        )

    return TheRunsThisProcessIsHolding(build_the_graph=building_the_graph)


def _how_many_gates_there_are() -> int:
    """How many times a person is asked, read off the router rather than written down here.

    **Read from the code so the number cannot go stale.** A hard-coded eight would keep passing
    if a stage were added, and the test that is supposed to prove a run reached the end would
    instead be waiting at a gate for a ninth answer that never comes.
    """
    from aisdlc.graph.router import WHERE_AN_APPROVED_ARTIFACT_LEADS

    return len(WHERE_AN_APPROVED_ARTIFACT_LEADS)


def _answer_the_gate_now_showing(
    the_board: TestClient,
    the_runs: TheRunsThisProcessIsHolding,
    work_item_id: str,
    already_answered: set[str],
    approved: bool,
    why: str,
) -> None:
    """Wait for the next gate and answer it once, remembering which gate that was.

    **The wait and the POST are one function because the gap between them is the whole defect,
    and this file had it twice.** The board clears a question *after* this endpoint's response
    has gone back, so a caller that waits and then posts can read gate one, post for gate one, and
    — the next wait, holding a set that does not yet contain gate one — read gate one again and
    post for it a second time. That second post lands on gate two. The record then holds three
    decisions for a two-gate run, and an assertion about what a refusal leaves behind fails on a
    run that behaved perfectly. One of these tests did exactly that, and the other did the mirror
    of it.

    **A 409 is answered by asking again, and that is a person pressing the button twice.** The
    board refuses an answer to a run still walking from the previous gate, which is right: a
    second click that appeared to work and silently did nothing is worse than one that says why
    not. So the answer is to do what a reader does — wait for the run to come back to rest, and
    ask again — bounded, because a run between two gates with faked agents is fast and a busier
    one than this needs a different mechanism rather than a longer wait.

    **Only while the same question is still on the table.** A 409 with a different question
    pending means the run moved past the gate this test meant to answer, and asking again would
    answer the wrong gate.
    """
    a_question = _wait_until_the_gate_is_asking(the_board, work_item_id, already_answered)
    already_answered.add(a_question["artifact_id"])
    the_answer = {"approved": approved, "decided_by": "pikuniu", "reason": why}

    for _attempt in range(HOW_MANY_TIMES_A_BOARD_MAY_BE_BUSY + 1):
        answered = the_board.post(f"/api/runs/{work_item_id}/decisions", json=the_answer)
        if answered.status_code == 200:
            return
        if answered.status_code != 409:
            pytest.fail(
                f"answering {a_question['artifact_id']} was refused with "
                f"{answered.status_code}: {answered.text}. A refusal is a completed gate, not an "
                "error"
            )
        _wait_until_the_run_has_stopped_walking(the_runs, work_item_id)

    pytest.fail(
        f"the board was busy for {HOW_MANY_TIMES_A_BOARD_MAY_BE_BUSY} attempts and "
        f"{a_question['artifact_id']} was never answered. The board answers 409 while a run is "
        "still walking from the previous gate, and this test answers each gate exactly once, so a "
        "busier run than this needs a different mechanism rather than a longer wait"
    )


def _wait_until_the_gate_is_asking(
    the_board: TestClient, work_item_id: str, already_answered: set[str]
) -> dict[str, object]:
    """Wait for the board to ask about an artifact nobody has answered yet.

    **"Not answered yet" and not simply "asking", and the difference is a race this test lost
    once.** The graph clears a question when it records the answer, which happens *after* this
    endpoint's response has already gone back. So a poll for "is it asking" answers yes with
    the question it was just given permission to stop asking — and the assertion two lines later
    finds nothing. A gate list is what makes the wait a fact: the question has to be about
    something no decision names yet.
    """
    return _wait_until(
        lambda: _a_question_nobody_has_answered(the_board, work_item_id, already_answered),
        f"{work_item_id} never reached a gate that was still waiting",
    )


def _a_question_nobody_has_answered(
    the_board: TestClient, work_item_id: str, already_answered: set[str]
) -> dict[str, object] | None:
    """The pending question, or `None` while the one before it is still being cleared."""
    the_question = the_board.get(f"/api/runs/{work_item_id}").json()["the_question"]
    if the_question is None or the_question["artifact_id"] in already_answered:
        return None
    return the_question


def _wait_until_the_run_has_stopped_walking(
    the_runs: TheRunsThisProcessIsHolding, work_item_id: str
) -> None:
    """Wait until this run is parked at a gate rather than walking towards one.

    **Asked of the holder and not of the board**, because the board's question is cleared after
    the answer is posted and is therefore empty during exactly the window this waits for, while
    the holder still knows. `is_this_run_still_walking` is the same fact the board's 409 is raised
    from, so waiting on it cannot disagree with the thing being waited for.
    """
    _wait_until(
        lambda: not the_runs.is_this_run_still_walking(work_item_id),
        f"{work_item_id} never stopped walking, so the board kept refusing every answer",
    )


def _wait_until_the_run_has_finished(the_board: TestClient, work_item_id: str) -> None:
    """Wait for the run to stop asking, which is how both delivering and refusing end."""
    _wait_until(
        lambda: the_board.get(f"/api/runs/{work_item_id}").json()["the_question"] is None,
        f"{work_item_id} was still asking questions when the test gave up",
    )


def _wait_until(what_to_read, what_to_say_when_it_never_became_true: str):
    """One fact, polled, with a ceiling — the ceiling is a backstop and not the mechanism.

    **Polling a fact rather than sleeping a duration.** A fixed sleep is either too short, and
    the test fails for having been impatient, or too long, and it is paid on every run. This
    looks at the one thing it is waiting for, so it is as fast as the run and no slower — and it
    hands back what it read, so a caller that needed the value does not read it a second time
    and race itself.
    """
    how_long_it_has_waited = 0.0
    while how_long_it_has_waited < HOW_LONG_A_SMOKE_MAY_WAIT_IN_SECONDS:
        what_it_says = what_to_read()
        if what_it_says:
            return what_it_says
        time.sleep(0.1)
        how_long_it_has_waited += 0.1
    pytest.fail(
        f"{what_to_say_when_it_never_became_true}, after {HOW_LONG_A_SMOKE_MAY_WAIT_IN_SECONDS}s"
    )


def test_an_implementer_that_wrote_nothing_is_sent_back_and_the_run_delivers(
    a_repository_to_clone_into: Path, a_register_and_a_projects_root, tmp_path: Path
) -> None:
    """The claim twelve isolated tests could not make, made on a run that goes all the way.

    **Why this is here and not another isolated supervisor test.** Every refusal routing in this
    repository is covered by calling the node and reading the `Command` it returns. That proves the
    `except` names the refusal. It cannot prove the graph has a node on the other end of that
    `goto`, that the state the supervisor reads is populated, that the stage it names is reachable
    from where the run actually is, and that a run survives going there and coming back. Those are
    four claims and none is visible in a returned `Command`.

    **And the wiring was broken in a way none of them could see.** This node returned a `Command`
    on a refusal *and* the graph carried a static edge out of it, so both fired: the run went to
    the supervisor and carried on down the ordinary path, both arrived at the same node in the same
    step, and LangGraph refused the run for writing `requested_stage` twice. Every repair in this
    system died that way, and a test that reads a `Command` reads nothing about it.

    **The implementer refuses once and then works, and the run still delivers.** Refusing forever
    would prove the route exists and nothing else — the second attempt is where a half-fixed graph
    shows up.

    **Walked by driving the graph, not the board**, because the board's question lifecycle makes a
    repairing run indistinguishable from a polling race. See `_walk_the_run_to_the_end`.
    """
    what_the_supervisor_was_told: list[str] = []
    how_many_times_the_implementer_was_asked = {"count": 0}
    a_green_suite = SuiteOutcome(
        exit_code=0, passed=True, dependencies_installed=True, output="74 passed"
    )

    def an_implementer_that_refuses_once(clone, repository, implementation_plan):
        """The real refusal, once, on a plan it agrees with entirely.

        **It agrees with the plan, which is what makes this the right refusal to inject.** A
        refusal of "the plan named the file and the work did not match it" has one obvious answer,
        so a supervisor asked to judge it is being asked a question with only one sensible reply.
        """
        how_many_times_the_implementer_was_asked["count"] += 1
        if how_many_times_the_implementer_was_asked["count"] == 1:
            raise AWriteThatChangesNothingError(["health.py"])
        return ADeliveredChange(
            written=[FileToWrite(path="health.py", content="def health():\n    return 1\n")],
            verification=VerificationReport(
                suite_before_the_change=a_green_suite,
                suite_after_the_change=a_green_suite,
            ),
            what_the_implementer_said="added the endpoint the requirements asked for, on retry",
        )

    def a_supervisor_that_says_do_the_implementation_again(
        work_item, projects_root, what_the_run_stopped_on
    ) -> Command:
        what_the_supervisor_was_told.append(str(what_the_run_stopped_on))
        return Command(
            goto=WHERE_THE_IMPLEMENTATION_IS_REWRITTEN,
            update={"repair": "the implementer ignored an approved plan nobody disputes"},
        )

    working_agents = _the_agents_no_model_would_produce()
    the_graph = the_lifecycle(
        agents=TheAgentsThisRun(
            **{
                **working_agents.__dict__,
                "apply_and_verify": an_implementer_that_refuses_once,
                "supervise": a_supervisor_that_says_do_the_implementation_again,
            }
        ),
        delivery=_a_delivery_that_only_writes_down(a_repository_to_clone_into),
        plan_the_clone=_cloning_from_a_local_repository(a_repository_to_clone_into),
    )

    the_work_item = a_work_item_commissioned_for_an_agent(
        work_item_id="an-implementer-that-wrote-nothing",
        repository=Repository(owner="an", name="owner"),
        accountable_role=Role.DEV,
        commissioned_by="a person reading a test",
        requested=a_request_about("add a health endpoint", ""),
    )
    with holding_the_register() as register:
        the_work_item_a_commission_registers(register, the_work_item)

    _, the_projects_root = a_register_and_a_projects_root
    the_gates_it_asked_about: list[str] = []
    _walk_the_run_to_the_end(the_graph, the_work_item, the_projects_root, the_gates_it_asked_about)

    with holding_the_register() as register:
        the_stage_the_register_holds = the_work_item_registered_at(
            register, the_work_item.work_item_id
        ).stage

    assert how_many_times_the_implementer_was_asked["count"] == 2, (
        f"the implementer was asked {how_many_times_the_implementer_was_asked['count']} times, so "
        "the refusal did not send the run back to it — and a supervisor that names a stage is a "
        "claim that the graph can get there from where the run actually was"
    )
    assert len(what_the_supervisor_was_told) == 1, (
        f"the supervisor was asked {len(what_the_supervisor_was_told)} times for one refusal"
    )
    assert "health.py" in what_the_supervisor_was_told[0], (
        "the supervisor was told a run stopped but not which file was left alone, so it is asked "
        "to judge without the one fact the refusal exists to carry"
    )
    # **No gate is asked twice here, and that is the difference from the delivery's refusal.** This
    # one happens *before* a verification exists, so the repair re-does the implementation and the
    # verification gate is presented once like every other. A refusal from the delivery is after
    # that gate, so repairing it re-presents it. Two repairs, two shapes — and it is why both tests
    # exist rather than one parameterised over a refusal.
    assert sorted(set(the_gates_it_asked_about)) == sorted(WHERE_AN_APPROVED_ARTIFACT_LEADS), (
        f"this run was asked about {sorted(set(the_gates_it_asked_about))} and the router has "
        f"{sorted(WHERE_AN_APPROVED_ARTIFACT_LEADS)}"
    )
    assert len(the_gates_it_asked_about) == len(WHERE_AN_APPROVED_ARTIFACT_LEADS), (
        f"this run was asked {len(the_gates_it_asked_about)} questions for "
        f"{len(set(the_gates_it_asked_about))} gates: {the_gates_it_asked_about}"
    )
    assert the_stage_the_register_holds is Stage.DONE, (
        "the repair worked and every gate was approved, and the register has this run at "
        f"{the_stage_the_register_holds.name} rather than DONE"
    )


def _walk_the_run_to_the_end(
    graph, work_item, projects_root: Path, the_gates_it_asked_about: list[str]
) -> None:
    """Answer every gate until the run stops asking, driving the graph itself rather than the board.

    **Four attempts at this went through the board first, and every one of them failed on the board
    rather than on the graph.** The board clears a question when it records the answer, which
    happens after the POST has returned, so a poll right after answering sees the same question
    again — and a run that *repairs* asks about a gate it has already asked about, which looks
    exactly like that race. Count the gates and you stop on a repeat; count twice the gates and you
    answer a delivery gate twice, which leaves a run that is approved-everything and delivered
    nothing; report "finished" by returning `None` and `_wait_until` reads falsy as "not yet"; and
    count quiet moments per artifact, which re-answers a gate whenever the run pauses. Four shapes,
    four failures, none of them about a repair.

    **So this does not use the board at all.** The gate asks with `interrupt`, the graph pauses,
    and the answer goes back with `Command(resume=...)` — which is exactly what the production
    holder does, and what the board does on its behalf. Nothing here polls, so there is no race to
    lose and no question lifecycle to reason about. The graph is the subject; the board is a
    browser.
    """
    where_from = a_run_beginning_at(work_item, projects_root)
    the_config = a_config(work_item.work_item_id)

    while True:
        what_the_run_asked: object = None
        for what_happened in graph.stream(where_from, the_config):
            if "__interrupt__" not in what_happened:
                continue
            what_the_run_asked = what_happened["__interrupt__"][0].value
            break
        if what_the_run_asked is None:
            return

        the_gates_it_asked_about.append(what_the_run_asked.artifact_id)
        where_from = Command(
            resume=ApprovalDecision(
                work_item_id=work_item.work_item_id,
                artifact_id=what_the_run_asked.artifact_id,
                artifact_version=what_the_run_asked.artifact_version,
                approved=True,
                decided_by="a person reading a test",
                reason="it is right",
                decided_at=datetime.now(UTC),
            )
        )
        how_many_gates_there_can_be = len(WHERE_AN_APPROVED_ARTIFACT_LEADS) * 2
        if len(the_gates_it_asked_about) > how_many_gates_there_can_be:
            pytest.fail(
                f"this run has been asked about {len(the_gates_it_asked_about)} gates and is still "
                f"asking: {the_gates_it_asked_about}. Eight gates plus one repair is twelve, so "
                "this run is going round something"
            )


def test_a_red_suite_reaches_the_supervisor_and_the_run_delivers_afterwards(
    a_repository_to_clone_into: Path, a_register_and_a_projects_root, tmp_path: Path
) -> None:
    """The second broken node, proved on a run that goes all the way — and the proof that was
    abandoned on Tuesday because the harness fought back.

    **The delivery node carried the same defect the implementer did and was found by reading for
    it.** It returns a `Command(goto=supervisor)` when a change leaves the suite red, and the graph
        "an edge out of itself as well as returning a Command, which is the run that"
        "died of two writes to one state key in a single step"
    to `mark_the_work_item_delivered` in the same step — and LangGraph refused the run for writing
    `requested_stage` twice. That is how every repair in this system died, and no unit test could
    see it because they read the `Command` rather than building the graph.

    **A red suite is the refusal a real run produces most often**, so this is the path most worth
    walking. The suite goes red, the delivery refuses, the supervisor sends it back, the change is
    made again, the suite is green, and the run delivers. Refusing forever would prove only that
    the route exists: the second attempt is where a half-fixed graph shows up.

    **Re-adding the edge this node used to carry makes this test fail, though not with the error
    the implementer's defect produced.** With the edge back, this run dies of
    `DONE cannot move to AWAITING_AGENT_PICKUP` rather than of `Can receive only one value per
    step`. Both are a dead run and both are invisible to a unit test, which is the point; but the
    symptom is not the one this test's own message predicts, and a guard that names the wrong
    failure is half a guard. It was checked by breaking the thing rather than by reading it, which
    is how the two text-searching guards in this repository were caught as well.
    """

    from aisdlc.graph.lifecycle import the_lifecycle
    from aisdlc.store.the_register_of_work_items import (
        the_work_item_registered_at,
    )

    _, the_projects_root = a_register_and_a_projects_root
    what_the_supervisor_was_told: list[str] = []
    how_many_times_the_change_was_attempted = {"count": 0}
    a_green_suite = SuiteOutcome(
        exit_code=0, passed=True, dependencies_installed=True, output="74 passed"
    )
    a_red_suite = SuiteOutcome(
        exit_code=1,
        passed=False,
        dependencies_installed=True,
        output="1 failed, 73 passed -- the health endpoint answered 404",
    )

    def a_delivery_whose_suite_goes_red_once(clone, repository, implementation_plan):
        """Green on the second attempt and red on the first, against a plan nobody touches.

        **The plan is the same both times, which is what makes this the delivery's refusal rather
        than a planner's.** The plan was approved by a person and the suite says the change it
        describes is wrong, so nothing about the plan can be the answer and the only honest answer
        is "do it again, properly" — which is what the supervisor returns.
        """
        how_many_times_the_change_was_attempted["count"] += 1
        the_suite_after = (
            a_red_suite if how_many_times_the_change_was_attempted["count"] == 1 else a_green_suite
        )
        return ADeliveredChange(
            written=[FileToWrite(path="health.py", content="def health():\n    return 1\n")],
            verification=VerificationReport(
                suite_before_the_change=a_green_suite, suite_after_the_change=the_suite_after
            ),
            what_the_implementer_said="added the endpoint the requirements asked for",
        )

    def a_supervisor_that_says_do_the_change_again(
        work_item, projects_root, what_the_run_stopped_on
    ) -> Command:
        what_the_supervisor_was_told.append(str(what_the_run_stopped_on))
        return Command(
            goto=WHERE_THE_IMPLEMENTATION_IS_REWRITTEN,
            update={"repair": "the suite went red, so the change was not what the plan described"},
        )

    working_agents = _the_agents_no_model_would_produce()
    the_graph = the_lifecycle(
        agents=TheAgentsThisRun(
            **{
                **working_agents.__dict__,
                "apply_and_verify": a_delivery_whose_suite_goes_red_once,
                "supervise": a_supervisor_that_says_do_the_change_again,
            }
        ),
        delivery=_a_delivery_that_only_writes_down(a_repository_to_clone_into),
        plan_the_clone=_cloning_from_a_local_repository(a_repository_to_clone_into),
    )

    the_work_item = a_work_item_commissioned_for_an_agent(
        work_item_id="a-red-suite-that-was-repaired",
        repository=Repository(owner="an", name="owner"),
        accountable_role=Role.DEV,
        commissioned_by="a person reading a test",
        requested=a_request_about("add a health endpoint", ""),
    )
    with holding_the_register() as register:
        the_work_item_a_commission_registers(register, the_work_item)

    the_gates_it_asked_about: list[str] = []
    _walk_the_run_to_the_end(the_graph, the_work_item, the_projects_root, the_gates_it_asked_about)

    with holding_the_register() as register:
        the_stage_the_register_holds = the_work_item_registered_at(
            register, the_work_item.work_item_id
        ).stage

    assert how_many_times_the_change_was_attempted["count"] == 2, (
        f"the change was attempted {how_many_times_the_change_was_attempted['count']} times, so a "
        "refused delivery did not send the run back to the implementation — and this node carried "
        "an edge out of itself as well as returning a Command, which is the run that died of two "
        "writes to one state key in a single step"
    )
    assert len(what_the_supervisor_was_told) == 1, (
        f"the supervisor was asked {len(what_the_supervisor_was_told)} times for one refusal"
    )
    assert "404" in what_the_supervisor_was_told[0], (
        "the supervisor was told a suite went red without being told what the suite said, and a "
        "refusal whose whole argument is the suite's own output has to carry it"
    )
    # **The verification gate is asked twice, and once is not enough.** This refusal happened
    # *after* that gate — the delivery is the last thing a run does — so repairing it re-walked the
    # implementation and produced a second verification for somebody to rule on. A refusal from the
    # implementer is the opposite: it happens before a verification exists, so no gate repeats.
    # Two repairs, two shapes, and a test written for either alone would be wrong about the other.
    assert the_gates_it_asked_about.count("VerificationReport") == 2, (
        f"the verification was asked about "
        f"{the_gates_it_asked_about.count('VerificationReport')} times in a run that repaired "
        f"after its delivery was refused: {the_gates_it_asked_about}"
    )
    assert the_stage_the_register_holds is Stage.DONE, (
        "the repair worked, every gate was approved, and the register has this run at "
        f"{the_stage_the_register_holds.name} rather than DONE"
    )
