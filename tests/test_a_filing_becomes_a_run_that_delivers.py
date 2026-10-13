"""A filing becomes a run that delivers, without its request being reworded.

**The clasp between the two halves of the product.** A briefing files an issue and
commissions a work item at `READY`; `POST /api/runs/from-work-item` (and
`aisdlc start`) looks that work item up and walks the same eight gates a
sentence-led run walks. The run inherits the opportunity's words and nothing else,
because a run inheriting its predecessor's analysis is a run whose analysis was
never checked by a gate.

**A real clone, a real state machine, real gates, a real register, real HTTP.**
Three things are replaced and each is named: the model, the issue API and the
delivery collaborators. Everything else — the filing, the lookup, the `READY`
guard, the PR body carrying `Closes #N` — is production code on its real path.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aisdlc.agents.apply_the_plan import ADeliveredChange
from aisdlc.agents.architecture_report import ArchitectureReport
from aisdlc.agents.architecture_report_answer import ArchitectureReportAnswer
from aisdlc.agents.discovery_answer import DiscoveryAnswer
from aisdlc.agents.discovery_report import DiscoveryReport, EvidenceFile
from aisdlc.agents.implement_the_plan import FileToWrite
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.qa_plan import QaPlan
from aisdlc.agents.qa_plan_answer import QaPlanAnswer
from aisdlc.agents.requirements import Requirements
from aisdlc.agents.requirements_answer import RequirementsAnswer
from aisdlc.agents.security_report import SecurityReport
from aisdlc.agents.verification_report import VerificationReport
from aisdlc.agents.what_an_agent_judged import WhatAnAgentJudged
from aisdlc.agents.what_the_planner_concluded import ImplementationPlanAnswer
from aisdlc.application.the_runs_this_process_is_holding import TheRunsThisProcessIsHolding
from aisdlc.creative.a_repository_briefing_itself import (
    WhatABriefingFound,
    filing_the_picks_a_person_made,
)
from aisdlc.creative.an_opportunity import AnOpportunity
from aisdlc.creative.filing_what_the_briefing_found import AnIssueThatWasOpened
from aisdlc.domain.commissioned_request import CommissionedRequest
from aisdlc.domain.repository import Repository
from aisdlc.domain.role import Role
from aisdlc.domain.stage import Stage
from aisdlc.domain.the_issue_this_answers import TheIssueThisAnswers
from aisdlc.domain.work_item import a_work_item_commissioned_for_an_agent
from aisdlc.graph.lifecycle import the_lifecycle
from aisdlc.graph.the_agents_this_run import TheAgentsThisRun
from aisdlc.graph.the_delivery_of_this_run import TheDeliveryOfThisRun
from aisdlc.store.the_board_reads import AColumnOfTheBoard
from aisdlc.store.the_register_of_work_items import the_work_item_registered_at
from aisdlc.store.where_the_register_lives import holding_the_register, the_register_lives_at
from aisdlc.tools.github_client import Addresses
from aisdlc.tools.github_clone_repository import RepositoryToClone
from aisdlc.tools.github_create_branch import PushedBranch
from aisdlc.tools.github_create_pull_request import AnOpenedPullRequest
from aisdlc.tools.merge_a_pull_request import WhatTheMergeLanded
from aisdlc.tools.run_tests import SuiteOutcome
from aisdlc.tools.the_suite_went_green import WhatTheSuiteSaid
from aisdlc.web.the_api import the_api_over

A_REPOSITORY = Repository(owner="pikuniu", name="a-project")
HOW_LONG_A_SMOKE_MAY_WAIT_IN_SECONDS = 30.0


@pytest.fixture
def creative_mode_on(monkeypatch) -> None:
    monkeypatch.setenv("AISDLC_CREATIVE_MODE", "on")


@pytest.fixture
def a_register_and_a_projects_root(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AISDLC_PROJECTS_DIR", str(tmp_path / "projects"))
    the_register_lives_at(tmp_path / "the-register.sqlite3")
    from aisdlc.store.where_the_register_lives import the_register

    return the_register(), tmp_path / "projects"


@pytest.fixture
def a_repository_to_clone_into(tmp_path: Path) -> Path:
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
    what_happened = subprocess.run(
        ["git", *what], cwd=where, capture_output=True, text=True, check=False
    )
    if what_happened.returncode != 0:
        pytest.fail(f"git {' '.join(what)} in {where} failed: {what_happened.stderr}")
    return what_happened.stdout


def _an_opportunity() -> AnOpportunity:
    return AnOpportunity(
        what_could_be_done="Remove the fallback secret from the authentication module",
        why_it_is_worth_doing="a literal fallback signs sessions with a value in the repository",
        the_files_that_show_this=["README.md"],
        how_it_would_be_known_to_have_worked="a test asserts refusal without SECRET",
        the_discipline_that_owns_it="SEC",
        the_risk_of_it="touches sessions",
    )


def _a_briefing_with(an_opportunity: AnOpportunity) -> WhatABriefingFound:
    return WhatABriefingFound(
        briefing_id="a-briefing",
        about=A_REPOSITORY,
        what_this_repository_is="a project",
        opportunities=[an_opportunity],
        what_the_briefing_could_not_settle=[],
        agent_judgement=None,
        what_was_already_tracked=[],
    )


def _an_issue_opener_that_records():
    what_was_opened: list[AnOpportunity] = []

    def opening(an_opportunity: AnOpportunity, _repository: Repository) -> AnIssueThatWasOpened:
        what_was_opened.append(an_opportunity)
        a_number = 41 + len(what_was_opened)
        return AnIssueThatWasOpened(
            number=a_number,
            address=f"https://example.invalid/{A_REPOSITORY.address}/issues/{a_number}",
        )

    return opening, what_was_opened


def test_filing_hands_back_the_work_item_ids_it_commissioned(
    a_register_and_a_projects_root, creative_mode_on: None
) -> None:
    """The picks call names the work items it made, because the board has to start one."""
    filing = filing_the_picks_a_person_made(
        _a_briefing_with(_an_opportunity()), [0], _an_issue_opener_that_records()[0]
    )

    assert filing.how_many_became_filings == 1
    assert len(filing.work_item_ids) == 1, (
        "one filing, so one id — a picks call that reports a count and no id "
        "leaves a person with a card they cannot start"
    )

    with holding_the_register() as a_register:
        the_filed = the_work_item_registered_at(a_register, filing.work_item_ids[0])

    assert the_filed.stage is Stage.READY
    assert the_filed.requested is not None and the_filed.requested.filed_as is not None


def test_starting_a_filing_twice_is_refused(
    a_register_and_a_projects_root, a_repository_to_clone_into: Path, creative_mode_on: None
) -> None:
    """A filed work item starts once; the second start, the unknown id and the
    past-`READY` item are all refused with a sentence."""
    _, the_projects_root = a_register_and_a_projects_root
    os.environ["AISDLC_PROJECTS_DIR"] = str(the_projects_root)

    the_runs = _the_runs_holding_fakes(a_repository_to_clone_into)
    with TestClient(the_api_over(_the_open_register(), the_runs)) as the_board:
        filing = filing_the_picks_a_person_made(
            _a_briefing_with(_an_opportunity()), [0], _an_issue_opener_that_records()[0]
        )
        the_id = filing.work_item_ids[0]

        started = the_board.post("/api/runs/from-work-item", json={"work_item_id": the_id})
        assert started.status_code == 200, started.text

        again = the_board.post("/api/runs/from-work-item", json={"work_item_id": the_id})
        assert again.status_code == 409, (
            "a run started twice would push one branch into one directory on one "
            f"checkpoint — it said: {again.text}"
        )

        nobody = the_board.post(
            "/api/runs/from-work-item", json={"work_item_id": "issue-1-no-such-work"}
        )
        assert nobody.status_code == 404


def test_a_filing_walks_eight_gates_and_its_pull_request_closes_the_issue(
    a_register_and_a_projects_root, a_repository_to_clone_into: Path, creative_mode_on: None
) -> None:
    """The loop: briefing pick → issue → run from the filing → `DONE`, and the PR
    body carries `Closes #N` so the merge closes what the briefing opened."""
    _, the_projects_root = a_register_and_a_projects_root
    os.environ["AISDLC_PROJECTS_DIR"] = str(the_projects_root)

    what_was_opened: list[object] = []
    the_runs = _the_runs_holding_fakes(a_repository_to_clone_into, what_was_opened)
    with TestClient(the_api_over(_the_open_register(), the_runs)) as the_board:
        filing = filing_the_picks_a_person_made(
            _a_briefing_with(_an_opportunity()), [0], _an_issue_opener_that_records()[0]
        )
        the_id = filing.work_item_ids[0]

        # **The picks call answers with the id, not only a count.** The board starts
        # what it can name; a count is a fact about the filing and an id is the handle.
        picks_answer = the_board.post("/api/briefings/no-briefing/picks", json={"which": []})
        assert picks_answer.status_code in (400, 410)

        started = the_board.post("/api/runs/from-work-item", json={"work_item_id": the_id})
        assert started.status_code == 200, started.text

        # **A card exists before the run has done anything**, as with a sentence-led run.
        assert the_id in [
            a_card["work_item_id"] for a_card in the_board.get("/api/board").json()["cards"]
        ]

        already_answered: set[str] = set()
        for _gate in range(1, _how_many_gates_there_are() + 1):
            _answer_the_gate_now_showing(the_board, the_runs, the_id, already_answered)

        _wait_until_the_run_has_finished(the_board, the_id)

    the_cards = the_board.get("/api/board").json()["cards"]
    assert len(the_cards) == 1
    assert the_cards[0]["column"] == AColumnOfTheBoard.DELIVERED.value
    assert the_cards[0]["stage"] == Stage.DONE.name

    with holding_the_register() as a_register:
        assert the_work_item_registered_at(a_register, the_id).stage is Stage.DONE

    assert what_was_opened, "the delivery never opened a pull request, so nothing can close it"
    the_body = what_was_opened[0]
    assert "Closes #42" in the_body, (
        f"the pull request body does not close the issue it answers: {the_body!r}. "
        "An address is a link for a reviewer; `Closes #N` is what makes the merge "
        "close the filing"
    )


def test_a_pull_request_body_for_a_filing_closes_its_issue() -> None:
    """The unit half: a filed request renders `Closes #N`, a typed one renders nothing."""
    from aisdlc.graph.deliver_node import _the_lines_of_a_pull_request_body

    filed = a_work_item_commissioned_for_an_agent(
        work_item_id="issue-42-x",
        repository=A_REPOSITORY,
        accountable_role=Role.DEV,
        commissioned_by="aisdlc-brief",
        requested=CommissionedRequest(
            title="Remove the fallback",
            body="words",
            filed_as=TheIssueThisAnswers(
                number=42, address="https://example.invalid/pikuniu/a-project/issues/42"
            ),
        ),
    )
    assert "Closes #42" in "\n".join(_the_lines_of_a_pull_request_body(filed))

    from aisdlc.domain.commissioned_request import a_request_about

    typed = a_work_item_commissioned_for_an_agent(
        work_item_id="a-run",
        repository=A_REPOSITORY,
        accountable_role=Role.DEV,
        commissioned_by="a person",
        requested=a_request_about("add a health endpoint", ""),
    )
    assert _the_lines_of_a_pull_request_body(typed) == []


def _the_open_register() -> sqlite3.Connection:
    from aisdlc.store.where_the_register_lives import the_register

    return the_register()


def _how_many_gates_there_are() -> int:
    from aisdlc.graph.router import WHERE_AN_APPROVED_ARTIFACT_LEADS

    return len(WHERE_AN_APPROVED_ARTIFACT_LEADS)


def _the_runs_holding_fakes(the_bare: Path, what_was_opened: list | None = None):
    def building_the_graph(source: Repository, the_model: object = None) -> object:
        return the_lifecycle(
            agents=_the_agents_no_model_would_produce(),
            delivery=_a_delivery_that_only_writes_down(the_bare, what_was_opened),
            plan_the_clone=_cloning_from_a_local_repository(the_bare),
        )

    return TheRunsThisProcessIsHolding(build_the_graph=building_the_graph)


def _the_agents_no_model_would_produce() -> TheAgentsThisRun:
    the_judged = WhatAnAgentJudged(
        what_it_found="one commit and one test",
        what_it_could_not_settle="nothing",
        what_it_expects_next="the next agent reads this",
    )

    def discover(clone, repository):
        the_paths = ["README.md", "test_thing.py"]
        return (
            DiscoveryReport(
                languages=["Python"],
                architecture_summary="a module and a test",
                key_components=["test_thing.py"],
                evidence_files=[
                    EvidenceFile(path=a_path, link=f"local://{repository.address}/{a_path}")
                    for a_path in the_paths
                ],
            ),
            DiscoveryAnswer(
                languages=["Python"],
                architecture_summary="a module and a test",
                key_components=["test_thing.py"],
                evidence_files=the_paths,
                judged=the_judged,
            ),
        )

    def propose_requirements(clone, repository, requested):
        # **The request the filing carried, not a rewording of it.** A run started
        # from a filing inherits the opportunity's words; an agent inventing its own
        # subject here would prove nothing about the clasp.
        assert requested.title.startswith("Remove the fallback"), requested.title
        the_found = {
            "requirements": ["remove the literal fallback"],
            "acceptance_criteria": ["the suite passes without SECRET"],
        }
        return Requirements(**the_found), RequirementsAnswer(judged=the_judged, **the_found)

    def plan_the_tests(requirements):
        the_found = {
            "test_strategy": "run the suite",
            "scenarios": ["the fallback is gone"],
        }
        return QaPlan(**the_found), QaPlanAnswer(judged=the_judged, **the_found)

    def describe_the_architecture(clone, repository):
        the_found = {
            "findings": ["one module"],
            "modules": ["test_thing.py"],
            "boundaries": ["none"],
        }
        return ArchitectureReport(**the_found), ArchitectureReportAnswer(
            judged=the_judged, **the_found
        )

    def inspect_for_security(clone, repository) -> SecurityReport:
        return SecurityReport(nothing_found_because="one trivial test")

    def plan(requirements, clone, repository, what_the_suite_announced=""):
        return ImplementationPlanAnswer(
            judged=the_judged,
            plan=ImplementationPlan(
                files_to_add=["health.py"],
                tests_to_add=["test_health.py"],
            ),
        )

    def apply_and_verify(clone, repository, implementation_plan) -> ADeliveredChange:
        a_suite = SuiteOutcome(
            exit_code=0, passed=True, dependencies_installed=True, output="1 passed"
        )
        return ADeliveredChange(
            written=[
                FileToWrite(path="health.py", content="def health():\n    return {'ok': True}\n")
            ],
            verification=VerificationReport(
                suite_before_the_change=a_suite, suite_after_the_change=a_suite
            ),
            what_the_implementer_said="done",
        )

    def supervise(work_item, projects_root, what_the_run_stopped_on) -> object:
        pytest.fail(f"supervisor asked on a run that never refuses: {what_the_run_stopped_on!r}")

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


def _a_delivery_that_only_writes_down(clone_path: Path, what_was_opened: list | None = None):
    def _push(the_clone, name: str) -> PushedBranch:
        return PushedBranch(name=name, address=f"local://{clone_path}/branch/{name}")

    def _open(what_to_open) -> AnOpenedPullRequest:
        if what_was_opened is not None:
            what_was_opened.append(what_to_open.body)
        return AnOpenedPullRequest(
            number=1, address="https://example.invalid/pikuniu/a-project/pull/1"
        )

    return TheDeliveryOfThisRun(
        our_copy=A_REPOSITORY,
        push_the_branch=_push,
        open_the_pull_request=_open,
        ask_whether_the_suite_went_green=lambda pr, repo: WhatTheSuiteSaid(
            head_commit="c" * 40, which_checks_went_green=["the_gate"]
        ),
        merge_the_pull_request=lambda wanted: WhatTheMergeLanded(
            commit=wanted.the_commit_a_merge_may_land, what_github_said="merged"
        ),
        rebase_the_branch_a_run_pushed=_a_rebase_that_refuses(),
    )


def _a_rebase_that_refuses():
    def refusing(*arguments: object):
        raise AssertionError("no test here asked for a conflict")

    return refusing


def _cloning_from_a_local_repository(the_bare: Path):
    def planning(source: Repository, into: Path) -> RepositoryToClone:
        return RepositoryToClone(
            repository=source,
            addresses=Addresses(fetch_from=str(the_bare), origin_of_the_code=str(the_bare)),
            into=into,
        )

    return planning


def _answer_the_gate_now_showing(the_board, the_runs, work_item_id, already_answered) -> None:
    a_question = _wait_until_the_gate_is_asking(the_board, work_item_id, already_answered)
    already_answered.add(a_question["artifact_id"])
    for _ in range(21):
        answered = the_board.post(
            f"/api/runs/{work_item_id}/decisions",
            json={"approved": True, "decided_by": "pikuniu", "reason": "it answers the filing"},
        )
        if answered.status_code == 200:
            return
        if answered.status_code != 409:
            pytest.fail(f"answering was refused: {answered.status_code}: {answered.text}")
        _wait_until(
            lambda: not the_runs.is_this_run_still_walking(work_item_id),
            "run never stopped walking",
        )
    pytest.fail("board stayed busy")


def _wait_until_the_gate_is_asking(the_board, work_item_id, already_answered):
    return _wait_until(
        lambda: _a_question_nobody_has_answered(the_board, work_item_id, already_answered),
        f"{work_item_id} never reached a waiting gate",
    )


def _a_question_nobody_has_answered(the_board, work_item_id, already_answered):
    the_question = the_board.get(f"/api/runs/{work_item_id}").json()["the_question"]
    if the_question is None or the_question["artifact_id"] in already_answered:
        return None
    return the_question


def _wait_until_the_run_has_finished(the_board, work_item_id) -> None:
    def _ended() -> bool:
        about = the_board.get(f"/api/runs/{work_item_id}").json()
        return about["how_it_ended"] is not None or not about["is_still_working"]

    _wait_until(_ended, f"{work_item_id} never finished")


def _wait_until(what_to_read, what_to_say: str):
    waited = 0.0
    while waited < HOW_LONG_A_SMOKE_MAY_WAIT_IN_SECONDS:
        seen = what_to_read()
        if seen:
            return seen
        time.sleep(0.1)
        waited += 0.1
    pytest.fail(f"{what_to_say}, after {HOW_LONG_A_SMOKE_MAY_WAIT_IN_SECONDS}s")
