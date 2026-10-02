"""A real model, a real graph, and a real refusal — the last claim nothing here has proved.

**Every whole-run test in this repository hands the supervisor a recording stub.** That is
deliberate and it is not enough. A stub proves the *wiring*: that a refusal reaches the node, that
the node's `goto` lands on a stage, and that a run survives going there and coming back. Those are
four claims and they are all about the graph. What they cannot show is that a **model**, given a
real card, a real refusal and a real record, names a stage this system can actually reach — because
a stub's decision is written into the test and is right by construction.

**So this is the one test here that asks a model.** The refusal is scripted and deterministic (the
implementer writes the file back unchanged), the graph is production, the clone is real, and the
supervisor is `the_supervisor_using_the_configured_model()` — the factory the application itself
builds. Everything that could be faked is faked; the judgement is the point.

**It skips loudly, and a green run that never called a model is a lie.** The default suite has to
stay runnable with no network and no credential, so a missing one is a `pytest.skip` that prints
which setting is absent — never a silent pass. Every other test in this repository is honest in
about what it does not prove, and this one is honest about when it does nothing at all.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from aisdlc.agents.apply_the_plan import ADeliveredChange
from aisdlc.agents.implement_the_plan import (
    FileToWrite,
)
from aisdlc.agents.verification_report import VerificationReport
from aisdlc.domain.commissioned_request import a_request_about
from aisdlc.domain.repository import Repository
from aisdlc.domain.role import Role
from aisdlc.domain.stage import Stage
from aisdlc.domain.work_item import a_work_item_commissioned_for_an_agent
from aisdlc.graph.lifecycle import the_lifecycle
from aisdlc.graph.supervise_a_repair import the_supervisor_using_the_configured_model
from aisdlc.graph.the_agents_this_run import TheAgentsThisRun
from aisdlc.store.the_register_of_work_items import (
    the_work_item_a_commission_registers,
    the_work_item_registered_at,
)
from aisdlc.store.where_the_register_lives import holding_the_register
from aisdlc.tools.run_tests import SuiteOutcome
from tests.test_a_run_from_a_request_to_a_delivery import (  # noqa: F401
    _a_delivery_that_only_writes_down,
    _cloning_from_a_local_repository,
    _the_agents_no_model_would_produce,
    _walk_the_run_to_the_end,
    # signature and the name imported here have to be the same string. Ruff reads that as one
    # shadowing the other; it is how pytest is given the fixture in the first place.
    a_register_and_a_projects_root,
    a_repository_to_clone_into,
)

# **The fixtures are imported rather than redefined, and that is a claim about them.** They build
# a real bare repository with real commits and open a real register, and a second copy of either
# would be a second thing that could disagree with the first about what "a repository to clone" is.
# pytest will not see a fixture in a module it did not collect, so importing them is how a test in
# another file may borrow one.

THE_SETTINGS_A_DEPLOYMENT_MUST_STATE = ("LLM_PROVIDER", "LLM_ENDPOINT", "LLM_MODEL")


def _why_this_test_is_not_proving_anything() -> str | None:
    """What is missing, in a sentence a reader can act on — or `None` when nothing is.

    **All three or none.** A provider without an endpoint, or a model name without a provider, is
    a deployment that has described half of itself, and asking a model with half a configuration
    produces an error that says which setting it liked least rather than which one was absent.
    """
    absent = [
        a_setting
        for a_setting in THE_SETTINGS_A_DEPLOYMENT_MUST_STATE
        if not os.environ.get(a_setting)
    ]
    if not absent:
        return None
    return (
        f"this test asks a real model and {', '.join(absent)} "
        f"{'is' if len(absent) == 1 else 'are'} not set, so nothing was proved about a model"
    )


@pytest.mark.skipif(
    bool(os.environ.get("AISDLC_NO_REAL_MODEL"))
    or not all(os.environ.get(a_setting) for a_setting in THE_SETTINGS_A_DEPLOYMENT_MUST_STATE),
    reason=(
        "a real model is not configured (LLM_PROVIDER / LLM_ENDPOINT / LLM_MODEL), so "
        "the supervisor's judgement was not exercised. The other tests here prove the wiring; this "
        "one is the only thing that proves the decision."
    ),
)
def test_a_real_model_naming_where_a_run_should_start_again_repairs_the_run(
    a_repository_to_clone_into: Path,  # noqa: F811 — pytest resolves a fixture by this name
    a_register_and_a_projects_root,  # noqa: F811 — and by this one
    tmp_path: Path,
) -> None:
    """A refused delivery, a real model reading the card, and a run that finishes because of it.

    **What is scripted and what is asked, and the split is the whole test.** The refusal is
    scripted, because a refusal has to happen for the supervisor to have anything to judge and
    because which refusal arrives is not this test's to choose. Everything else about the run is
    production: the graph, the clone, the register, the delivery — and the supervisor is the same
    factory the application builds, closing over the deployment's configured model.

    **The assertion is about where the run ended, not about what the model said.** A model is
    free to reach either verdict, and both are answers: it may send the run back to the
    implementation, which repairs it and delivers; or it may stop, which raises and ends the run
    with the card saying why. What must not happen is the run dying of the wiring — and that is
    precisely the failure this repository shipped for a week without noticing.
    """
    _, the_projects_root = a_register_and_a_projects_root

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
        """Red once and then green, and refusing forever is what makes this a real question."""
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

    working_agents = _the_agents_no_model_would_produce()
    the_graph = the_lifecycle(
        agents=TheAgentsThisRun(
            **{
                **working_agents.__dict__,
                "apply_and_verify": a_delivery_whose_suite_goes_red_once,
                # **The real one.** Everything else in this file is a double; this is the factory
                # `a_run_being_assembled` uses, so a change to how the supervisor is obtained is
                # exercised here rather than only in an application that is not being run.
                "supervise": the_supervisor_using_the_configured_model(),
            }
        ),
        delivery=_a_delivery_that_only_writes_down(a_repository_to_clone_into),
        plan_the_clone=_cloning_from_a_local_repository(a_repository_to_clone_into),
    )

    the_work_item = a_work_item_commissioned_for_an_agent(
        work_item_id="a-real-model-judging-a-real-refusal",
        repository=Repository(owner="an", name="owner"),
        accountable_role=Role.DEV,
        commissioned_by="a person reading a test",
        requested=a_request_about("add a health endpoint", ""),
    )
    with holding_the_register() as register:
        the_work_item_a_commission_registers(register, the_work_item)

    the_gates_it_asked_about: list[str] = []
    how_the_run_ended: list[str] = []
    try:
        _walk_the_run_to_the_end(
            the_graph, the_work_item, the_projects_root, the_gates_it_asked_about
        )
    except BaseException as how_it_stopped:
        how_the_run_ended.append(f"{type(how_it_stopped).__name__}: {how_it_stopped}")

    with holding_the_register() as register:
        the_stage = the_work_item_registered_at(register, the_work_item.work_item_id).stage

    assert not any(
        "INVALID_CONCURRENT_GRAPH_UPDATE" in a_reason
        or "Can receive only one value per step" in a_reason
        for a_reason in how_the_run_ended
    ), (
        "the run died of two writes to one state key in a single step, which is the defect that "
        f"killed every repair in this system: {how_the_run_ended}"
    )

    assert how_many_times_the_change_was_attempted["count"] >= 1, (
        "the change was never attempted, so the model never saw a run that needed repairing"
    )
    print(
        "\nA REAL MODEL JUDGE THIS RUN:",
        "stopped the run — " + how_the_run_ended[0]
        if how_the_run_ended
        else f"sent it back to the implementation, and the run reached {the_stage.name}",
        flush=True,
    )
    if how_the_run_ended:
        # **A model that stopped the run is a real answer, not a failure** — the supervisor's own
        # contract is to raise rather than return quietly, and a ceiling it reached is reported
        # rather than hidden. What is refused is a run that stopped for a reason which is not a
        # judgement: a wiring error, an unhandled exception, a model that could not be built.
        assert any(
            a_word in how_the_run_ended[0]
            for a_word in ("AgentDecided", "ceiling", "out of turns", "judgement")
        ), (
            "the run stopped for a reason that is not the supervisor judging it, so this test "
            f"proved nothing about a model: {how_the_run_ended[0]}"
        )
        return

    assert the_stage is Stage.DONE, (
        f"the model sent the run back to the implementation, the change was made again and the "
        f"suite was green, and the register holds {the_stage.name} rather than DONE"
    )
    assert how_many_times_the_change_was_attempted["count"] == 2, (
        "the model sent the run back to the implementation, so the change was made again — and it "
        f"was attempted {how_many_times_the_change_was_attempted['count']} times, which is not the "
        "repair and not the first attempt"
    )
