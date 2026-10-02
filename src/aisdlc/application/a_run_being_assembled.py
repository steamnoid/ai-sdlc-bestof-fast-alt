"""The composition root: a repository and a sentence, and the run that walks them.

**This is the module the engine never had.** Every one of the engine's agents was built and
proved, the graph was wired, and the delivery opened three real pull requests — and the only
code that ever assembled a run was a test in the real tier, which did the job a composition
root does. That is the gap this repository exists to close: a product whose only entry point
is `pytest -m e2e` is a test suite with a user interface.

**One function builds a run, and it is the only one that names a model.** Six of the eight
stages build their own model through a `*_using_the_configured_model()` factory, and the other
two are closed over the one model this function builds. A reader who wants to know which model
reasoned has one file to read.

**The planner's closure drops a parameter rather than passing it through, and the reason is the
engine's own finding.** `plan_the_change` asks the runner which directories it collects, and
that listing cannot be run before the dependencies are installed — which happens later, at
verification. A listing asked at planning time would be of a repository with no runner on it,
which is an empty answer that reads like a decision. So the parameter is named and discarded,
in one visible place, rather than forwarded and silently answered wrongly.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel

from aisdlc.agents.analyze_the_architecture import (
    the_architecture_analyst_using_the_configured_model,
)
from aisdlc.agents.analyze_the_repository import the_product_analyst_using_the_configured_model
from aisdlc.agents.analyze_the_requirements import the_qa_analyst_using_the_configured_model
from aisdlc.agents.apply_the_plan import apply_and_verify
from aisdlc.agents.discover_the_repository import (
    the_discovery_using_the_configured_model,
)
from aisdlc.agents.inspect_for_security_risk import the_security_analyst_using_the_configured_model
from aisdlc.agents.plan_the_change import plan_the_change
from aisdlc.agents.review_an_artifact import a_policy_answering_this_gate
from aisdlc.domain.repository import Repository
from aisdlc.domain.work_item import WorkItem
from aisdlc.graph.agent_state import AgentState
from aisdlc.graph.lifecycle import the_lifecycle
from aisdlc.graph.supervise_a_repair import the_supervisor_using_the_configured_model
from aisdlc.graph.the_agents_this_run import TheAgentsThisRun
from aisdlc.llm.llm_configuration import a_configuration_from_the_environment
from aisdlc.llm.model_factory import a_model_for
from aisdlc.tools.a_delivery_this_system_may_make import the_delivery_this_system_may_make
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.verify_the_change import the_suite_in_a_container

# What a run carries before any node has run. **`AgentState` is a `TypedDict` and has no runtime
# completeness check**, so a channel added to it breaks every hand-built starting state with a
# `KeyError` from inside a node, and the message names a `None` rather than the wiring. Every
# channel is enumerated here, once, for the same reason the engine enumerated them in its test
# support: the next channel added has one place to go rather than eleven.
THE_ARTIFACT_A_RUN_BEGINS_WITH = "DiscoveryReport"
ITS_FIRST_VERSION = 1


class ThisRunCannotBeAssembledError(Exception):
    """A run was asked for and the deployment cannot supply one of its parts.

    **Named and not defaulted, because every part of a run is load-bearing.** A run whose
    planner was left out plans nothing and delivers nothing; a run whose delivery was left out
    verifies a change, writes a branch name into a file, and stops — which reads from the
    outside exactly like success. Both were the failure this composition root was written
    because of, in the engine, and neither is worth a default.
    """

    def __init__(self, what_is_missing: str, why: str) -> None:
        """Name the part and the reason, because the fix is a deployment setting."""
        super().__init__(
            f"this run cannot be assembled: {what_is_missing} is {why}. Every collaborator a "
            "run has is load-bearing, and the ones that are not here fail in the middle of a "
            "delivery rather than before one starts — so this is refused at the door"
        )


def the_model_this_run_reasons_with() -> BaseChatModel:
    """The one model, built from the deployment's own configuration.

    **Refuses rather than returning a model that cannot answer.** The provider comes from the
    environment, and a deployment that has not said which one it has cannot be handed a
    plausible default — the failure otherwise arrives four stages in, as a run that did real
    work and could not finish it.
    """
    try:
        return a_model_for(a_configuration_from_the_environment())
    except Exception as a_problem:
        raise ThisRunCannotBeAssembledError(
            "the model", f"not configured ({a_problem})"
        ) from a_problem


def a_run_of(
    repository: Repository, the_model: BaseChatModel | None = None
) -> TheAgentsThisRun:
    """The cast of a run: every agent that reasons, and every one closed over the same model.

    **Two agents get the model handed in and six build their own.** The six have a
    `*_using_the_configured_model()` factory in the engine and are the ones the engine's own
    tests compare; the planner and the implementer are the two the engine had no factory for,
    because until this module nothing outside a test ever built a run. Both reasons are the
    same reason, and neither is worth hiding: this is the one place that says which model
    reasoned.
    """
    if the_model is None:
        the_model = the_model_this_run_reasons_with()

    return TheAgentsThisRun(
        discover=the_discovery_using_the_configured_model(),
        propose_requirements=the_product_analyst_using_the_configured_model(),
        plan_the_tests=the_qa_analyst_using_the_configured_model(),
        describe_the_architecture=the_architecture_analyst_using_the_configured_model(),
        inspect_for_security=the_security_analyst_using_the_configured_model(),
        plan=_a_planner_using(the_model),
        apply_and_verify=_an_implementer_using(the_model),
        supervise=the_supervisor_using_the_configured_model(),
    )


def _a_planner_using(the_model: BaseChatModel):
    """The real planner, closed over this run's model.

    **The suite announcement is named and discarded here, and nowhere else.** `plan_the_change`
    asks the runner which directories it collects; that listing cannot be run before the
    dependencies are installed, which happens later at verification. A listing asked now would
    be of a repository with no runner on it — an empty answer that reads exactly like a
    decision. Discarding it in one visible place is what keeps that from looking like an
    oversight.
    """

    def planning(
        requirements,
        clone: ClonedRepository,
        repository: Repository,
        what_the_suite_announced: str = "",
    ):
        del what_the_suite_announced
        return plan_the_change(requirements, clone, repository, the_model)

    return planning


def _an_implementer_using(the_model: BaseChatModel):
    """The real implementer, closed over this run's model and the real container.

    **The container and not a local test run.** A verification agent runs a repository's own
    suite, which is arbitrary code from a pull request, with the developer's credentials in
    reach. The boundary goes around execution and not around the run, which is why the same
    agent that reads the clone hands its suite to Docker.
    """

    def applying_and_verifying(clone, repository, plan):
        return apply_and_verify(
            clone, repository, plan, the_model, the_suite_in_a_container
        )

    return applying_and_verifying


def the_graph_for(repository: Repository, the_model: BaseChatModel | None = None):
    """The compiled lifecycle this run walks, with its delivery and — if stated — its policy.

    **`AISDLC_APPROVAL_POLICY` is read here and nowhere else in this repository.** A policy is a
    run that never suspends: it answers its own gates, so the whole pipeline happens inside one
    walk and nobody is ever asked. That is a different product from the one a person drives, and
    the difference is one setting read in one place.
    """
    from aisdlc.agents.review_an_artifact import the_policy_a_deployment_stated

    if the_model is None:
        the_model = the_model_this_run_reasons_with()

    the_policy_name = the_policy_a_deployment_stated()
    if the_policy_name is None:
        return the_lifecycle(
            agents=a_run_of(repository, the_model),
            delivery=the_delivery_this_system_may_make(repository),
        )

    # **The policy is a separate call and not a `**` splat, and the reason is that a splat
    # cannot be read.** `the_lifecycle`'s fourth and fifth parameters are a clone planner and a
    # recorder, so `**{"policy": ...}` is a dict of one value typed as a dict of anything, and
    # mypy's complaint about it is the reader's complaint too: nothing says which parameter the
    # key belongs to. Two calls, one branch, and a person can see that a policy is the only
    # thing that differs between them.
    return the_lifecycle(
        agents=a_run_of(repository, the_model),
        delivery=the_delivery_this_system_may_make(repository),
        policy=a_policy_answering_this_gate(the_model),
    )


def a_run_beginning_at(
    work_item: WorkItem, projects_root: Path
) -> AgentState:
    """Everything a run carries before any node has run, with every channel present.

    **`clone` is `None` and not a repository.** Cloning is the first thing the run does, from
    the repository the work item already carries; a starting state that held a clone would mean
    something had read a repository before the run started, which is the boundary this
    repository's tools exist to hold.
    """
    return {
        "work_item": work_item,
        "projects_root": projects_root,
        "clone": None,
        "the_commit_anything_proved": None,
        "which_checks_went_green": None,
        "requested_stage": work_item.stage,
        "requested_agent": None,
        "requested_role": work_item.role,
        "discovery_report": None,
        "requirements": None,
        "qa_plan": None,
        "architecture_report": None,
        "security_report": None,
        "implementation_plan": None,
        "written_files": None,
        "verification_report": None,
        "pull_request_request": None,
        "opened_pull_request": None,
        "presented_artifact_id": THE_ARTIFACT_A_RUN_BEGINS_WITH,
        "presented_artifact_version": ITS_FIRST_VERSION,
        "repair": None,
        "what_stopped_this_run": None,
        "decisions": [],
        "approvals": [],
    }
