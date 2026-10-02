"""The lifecycle, wired: the nodes, the edges between them, and the checkpointer."""

from __future__ import annotations

from collections.abc import Callable

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from aisdlc.agents.architecture_report import ArchitectureReport
from aisdlc.agents.artifact import Artifact
from aisdlc.agents.discovery_report import DiscoveryReport, EvidenceFile
from aisdlc.agents.implement_the_plan import FileToWrite
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.pull_request_request import PullRequestRequest
from aisdlc.agents.qa_plan import QaPlan
from aisdlc.agents.requirements import Requirements
from aisdlc.agents.requirements_answer import (
    AnAmbiguity,
    WhoCanAnswerThisAmbiguity,
)
from aisdlc.agents.review_an_artifact import AnswerTheGate, no_policy_was_given_to_this_run
from aisdlc.agents.security_report import SecurityFinding, SecurityReport
from aisdlc.agents.severity import Severity
from aisdlc.agents.verification_report import VerificationReport
from aisdlc.approval.approval_decision import ApprovalDecision
from aisdlc.approval.approval_question import ApprovalQuestion
from aisdlc.approval.gate_node import (
    ask_a_human,
    record_what_was_decided,
)
from aisdlc.domain.approval import Approval
from aisdlc.domain.commissioned_request import CommissionedRequest
from aisdlc.domain.repository import Repository
from aisdlc.domain.role import Role
from aisdlc.domain.stage import Stage
from aisdlc.domain.the_issue_this_answers import TheIssueThisAnswers
from aisdlc.domain.the_work_each_agent_has_done import (
    TheWorkEachAgentHasDone,
    TheWorkOneAgentHasDone,
)
from aisdlc.domain.work_item import WorkItem
from aisdlc.graph.agent_state import AgentState
from aisdlc.graph.analyze_node import Analyze, analyze_the_repository_in_this_run
from aisdlc.graph.apply_node import (
    ApplyAndVerify,
    apply_and_verify_in_this_run,
)
from aisdlc.graph.architecture_node import (
    AnalyzeTheArchitecture,
    analyze_the_architecture_in_this_run,
)
from aisdlc.graph.clone_node import PlanTheClone, clone_the_repository_for_this_run
from aisdlc.graph.deliver_node import a_request_for_the_delivery, open_the_delivery
from aisdlc.graph.discover_node import (
    Discover,
    discover_the_repository_in_this_run,
)
from aisdlc.graph.merge_node import (
    WHERE_THE_CONFLICT_IS_SETTLED,
    WHERE_THE_DELIVERY_IS_MERGED,
    merge_the_delivery_in_this_run,
)
from aisdlc.graph.pickup_node import (
    begin_delivering_the_work_item,
    begin_describing_the_architecture,
    begin_implementing_the_plan,
    begin_inspecting_for_security_risk,
    begin_planning_the_change,
    begin_planning_the_tests,
    begin_the_product_analysis,
    begin_working_on_the_work_item,
    hand_the_architecture_report_to_a_human,
    hand_the_delivery_to_a_human,
    hand_the_plan_to_a_human,
    hand_the_qa_plan_to_a_human,
    hand_the_requirements_to_a_human,
    hand_the_security_report_to_a_human,
    hand_the_verification_to_a_human,
    hand_the_work_to_a_human,
    mark_the_work_item_delivered,
    offer_the_work_item_to_discover,
    offer_the_work_item_to_the_architecture_analyst,
    offer_the_work_item_to_the_implementer,
    offer_the_work_item_to_the_planner,
    offer_the_work_item_to_the_product_analyst,
    offer_the_work_item_to_the_pull_request_agent,
    offer_the_work_item_to_the_qa_analyst,
    offer_the_work_item_to_the_security_analyst,
)
from aisdlc.graph.plan_node import PlanTheChange, plan_the_change_in_this_run
from aisdlc.graph.qa_node import (
    AnalyzeTheRequirements,
    analyze_the_requirements_in_this_run,
)
from aisdlc.graph.router import (
    THE_NEXT_ARTIFACT_IS_A_PLAN,
    THE_NEXT_ARTIFACT_IS_THE_CHANGE,
    THE_RUN_IS_OVER,
    WHERE_AN_APPROVED_ARTIFACT_LEADS,
    where_a_gate_outcome_leads,
)
from aisdlc.graph.security_node import (
    InspectForSecurityRisk,
    inspect_for_security_risk_in_this_run,
)
from aisdlc.graph.settle_a_conflict_node import (
    RebaseTheBranchARunPushed,
    the_repair_chosen_using_the_configured_model,
)
from aisdlc.graph.suite_node import the_suite_is_asked_about_in_this_run
from aisdlc.graph.supervise_a_repair import (
    WHERE_THE_SUPERVISOR_DECIDES_WHETHER_TO_REPAIR,
    SuperviseARepair,
)
from aisdlc.graph.supervise_a_repair_in_this_run import supervise_a_repair_in_this_run
from aisdlc.graph.the_agents_this_run import TheAgentsThisRun
from aisdlc.graph.the_delivery_of_this_run import TheDeliveryOfThisRun
from aisdlc.graph.the_policy_answers_this_gate import the_policy_answers_this_gate
from aisdlc.graph.transition_node import transition_the_work_item
from aisdlc.graph.what_to_repeat import (
    WhatOneAgentMustDoAgain,
    WhatToRepeat,
    WhereTheRunShouldStartAgain,
)
from aisdlc.graph.who_answers_a_gate import (
    THE_GATE_IS_ANSWERED_BY,
    WHERE_A_PERSON_ANSWERS,
    WHERE_A_POLICY_ANSWERS,
    where_the_gate_leads,
)
from aisdlc.graph.write_nodes import Record, record_what_this_run_has
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.github_create_pull_request import AnOpenedPullRequest
from aisdlc.tools.github_fork_repository import a_clone_this_system_may_write_to
from aisdlc.tools.run_tests import SuiteOutcome

# The production collaborator, built once. It reads the environment when it is *called*
# rather than now, so importing this module does not depend on a setting being present.
PLAN_THE_CLONE: PlanTheClone = a_clone_this_system_may_write_to()

# Every node the router can return, read from the declaration rather than listed here. A
# route the router produces and the graph has no edge for is a run that stops with nothing
# said, so the two lists are not maintained separately: a stage added to the pipeline appears
# in the declaration and this set grows with it.
EVERY_DESTINATION_A_GATE_OUTCOME_MAY_LEAD_TO = sorted(
    {THE_RUN_IS_OVER, *WHERE_AN_APPROVED_ARTIFACT_LEADS.values()}
)


# The run's delivery, and the three collaborators it takes rather than looks up. **No default
# on any of them**, and that is the whole point: a delivery that defaulted to doing nothing
# would be a pipeline that verifies a change, writes a branch name into a file, and stops —
# which is what this one did, and which reads from the outside exactly like success.
#
# They are not in `TheAgentsThisRun` because none of them reasons. §10 gives the PR agent four
# responsibilities and none is a model call, so naming them agents would put a lie in the type
# that exists to say what a run reasons with.


def the_lifecycle(
    agents: TheAgentsThisRun,
    delivery: TheDeliveryOfThisRun,
    policy: AnswerTheGate | None = None,
    plan_the_clone: PlanTheClone = PLAN_THE_CLONE,
    record: Record = record_what_this_run_has,
) -> CompiledStateGraph:
    """The commissioned path: discovery, then a plan, then the change, and a person at each.

    **The run no longer ends at the first gate, and the docstring that said it did is what
    this change had to argue with.** A run reaches `record_what_was_decided` once per
    gate, so one conditional edge from it and one router serve all of them, and the router
    reads which artifact the decision was about. Where a gate outcome leads is therefore no
    longer an unmade decision: it is the pipeline, written down in `router.py`.

    **The wiring is split into one function per stage**, because a single function registering
    twenty-two nodes and their edges had run past the limit where a reader can hold it, and
    because three functions named after the three stages read top to bottom as the pipeline
    itself rather than as a list of names.

    **One function moves the work item, whatever the node is called.** LangGraph needs a
    distinct name per node, and a node with two outbound edges runs them in parallel rather
    than in sequence, so a move that both hands over and asks would fork the run and have two
    branches write the same channel — which the runtime refuses. Nine names, one writer, and a
    test holds the list of names to the set that are registered.

    **Three collaborators have no default**, and the asymmetry with `plan_the_clone` is
    deliberate. Deciding which model reasons, which one plans and which one writes is not
    something this file can know, so a test has to say so out loud. Cloning is different: the
    repository to clone follows from `owner/name` and there is exactly one right answer, so it
    gets a default and the graph tests — whose runs always arrive carrying a clone — never
    reach it.

    **The product analyst is not wired here, and the discomfort of that is recorded rather
    than left for a reader to guess at.** `aisdlc-po-analyze` is built: it produces
    `Requirements`, it has a node, and a real model has been watched proposing against a real
    repository. It is absent from this graph because the specification's order puts it between
    discovery and planning, with QA, architecture and security in between them — and none of
    those three exist yet. Inserting it today either ends the run at a requirements gate that
    has no successor, taking the delivered path with it, or routes `Requirements` straight to
    the planner, which is a pipeline skipping three stages and reads exactly like a decision.
    The same rule that made `VerificationReport` terminal: **a stage is not invented to have
    somewhere to send it.** The four analysis agents are built and proved first, and this graph
    gains all four in one cycle when the last one exists.

    The checkpointer is in memory. Nothing has earned the right to reach Postgres yet, and an
    `InMemorySaver` needs no server, no credentials and no infrastructure. A durable
    checkpointer is what makes a suspended approval survive a restart, and that is a later
    decision with a real cost.
    """
    graph = StateGraph(AgentState)

    _the_gate_nodes(graph, policy)
    _the_nodes_that_move_the_work_item(graph)
    _the_discovery_stage(graph, agents.discover, plan_the_clone)
    _the_product_analysis_stage(graph, agents.propose_requirements)
    _the_qa_analysis_stage(graph, agents.plan_the_tests)
    _the_architecture_analysis_stage(graph, agents.describe_the_architecture)
    _the_security_analysis_stage(graph, agents.inspect_for_security)
    _the_planning_stage(graph, agents.plan)
    _the_implementation_stage(graph, agents.apply_and_verify)
    _the_delivery_stage(graph, delivery)
    _the_conflict_repair(graph, delivery.rebase_the_branch_a_run_pushed)
    _the_repair_stage(graph, agents.supervise)

    graph.add_edge(START, "offer_the_work_item_to_discover")
    graph.add_conditional_edges(
        "record_what_was_decided",
        where_a_gate_outcome_leads,
        EVERY_DESTINATION_A_GATE_OUTCOME_MAY_LEAD_TO,
    )
    graph.add_edge(THE_RUN_IS_OVER, END)

    return graph.compile(checkpointer=InMemorySaver(serde=a_checkpoint_serializer()))


def _the_gate_nodes(graph: StateGraph, policy: AnswerTheGate | None) -> None:
    """The two nodes every gate shares, and the two writers of the run's artifacts.

    Registered once because every stage ends at the same two. A run has as many gates as it has
    artifacts, and a node registered twice is an error rather than a second visit — so the gate
    is one place and the stages are the paths between them.
    """
    for name in ("write_what_this_run_found", "write_how_this_run_ended"):
        graph.add_node(name, record_what_this_run_has)
    graph.add_node(WHERE_A_PERSON_ANSWERS, ask_a_human)
    graph.add_node("record_what_was_decided", record_what_was_decided)
    # **Always registered, which the dangling-`goto` guard is what forced.** Registering it only
    # when a policy was given made this graph's node list depend on how the graph was built, and
    # that guard exists precisely to ask what the graph holds — a destination that is sometimes
    # there is a promise with a condition on it. Registering always costs one node that is never
    # reached, and a `goto` that is always true.
    # **Through a lambda, like every other seam here.** `add_node` infers its type from the
    # callable it is handed, and a bare `Callable` alias does not carry the state type through —
    # the same reason the discovery and planning seams are wrapped rather than passed.
    graph.add_node(
        WHERE_A_POLICY_ANSWERS,
        lambda state: the_policy_answers_this_gate(
            state, policy if policy is not None else no_policy_was_given_to_this_run
        ),
    )
    graph.add_edge(WHERE_A_POLICY_ANSWERS, "record_what_was_decided")
    graph.add_edge(WHERE_A_PERSON_ANSWERS, "record_what_was_decided")


def _the_nodes_that_move_the_work_item(graph: StateGraph) -> None:
    """One function registered under every name that asks it to move, and nothing else.

    Nine names, one writer. LangGraph needs a distinct name per node, so a node with two
    outbound edges runs them in parallel, and the two branches would both write the work item
    channel — which the runtime refuses. Registering the same function under a second name is
    therefore the only way to make a chain of moves, and the test below holds the list of names
    to the set that are registered.
    """
    for name in (
        "apply_the_pickup",
        "apply_the_work_begun",
        "apply_the_handover_to_a_human",
        "apply_the_pickup_by_the_planner",
        "apply_the_planning_begun",
        "apply_the_handover_of_the_plan",
        "apply_the_pickup_by_the_implementer",
        "apply_the_implementation_begun",
        "apply_the_handover_of_the_verification",
    ):
        graph.add_node(name, transition_the_work_item)


def _the_discovery_stage(
    graph: StateGraph, discover: Discover, plan_the_clone: PlanTheClone
) -> None:
    """Pick the work up, clone, discover, and hand the report to a person.

    One stage of the pipeline in one function, so the whole shape is read top to bottom as
    three stages rather than as sixty lines of wiring. The stage ends at the shared gate.
    """
    graph.add_node("offer_the_work_item_to_discover", offer_the_work_item_to_discover)
    graph.add_node("begin_working_on_the_work_item", begin_working_on_the_work_item)
    graph.add_node("hand_the_work_to_a_human", hand_the_work_to_a_human)
    graph.add_node(
        "clone_the_repository",
        lambda state: clone_the_repository_for_this_run(state, plan_the_clone),
    )
    graph.add_node(
        "discover_the_repository",
        lambda state: discover_the_repository_in_this_run(state, discover),
    )
    graph.add_edge("offer_the_work_item_to_discover", "apply_the_pickup")
    graph.add_edge("apply_the_pickup", "begin_working_on_the_work_item")
    graph.add_edge("begin_working_on_the_work_item", "apply_the_work_begun")
    graph.add_edge("apply_the_work_begun", "clone_the_repository")
    graph.add_edge("clone_the_repository", "discover_the_repository")
    graph.add_edge("discover_the_repository", "write_what_this_run_found")
    graph.add_edge("write_what_this_run_found", "hand_the_work_to_a_human")
    graph.add_edge("hand_the_work_to_a_human", "apply_the_handover_to_a_human")
    graph.add_conditional_edges(
        "apply_the_handover_to_a_human", where_the_gate_leads, THE_GATE_IS_ANSWERED_BY
    )


# The four analysis stages, in the order §9 and the specification's demo both give them.
# **Four functions rather than one parameterised over a table of stages, and that is a
# decision.** A table would put the four stages' differences in a data structure and leave the
# graph reading as a loop, which is a layer hiding control flow: a reader would have to look
# up three names to learn what one line does, and a stage wired wrong would look identical to
# a stage wired right. The stages are the domain, and the domain reads top to bottom.
#
# Each registers its *own* three transition nodes, as the discovery and planning stages do, so
# the single writer stays single and the list of node names is the list of moves a run makes.

_PRODUCT_ANALYSIS_STAGE = "The product analyst's stage: the run's third piece of reasoning."
_QA_ANALYSIS_STAGE = (
    "The QA analyst's stage: the first reasoning in this graph about a *decision* rather than "
    "about code, which is why it is handed the requirements and not the clone."
)
_ARCHITECTURE_ANALYSIS_STAGE = (
    "The architecture analyst's stage, third of the four, and the one whose findings are "
    "about boundaries rather than about what should be built."
)
_SECURITY_ANALYSIS_STAGE = (
    "The security analyst's stage, last of the four: the last gate before anything is written, "
    "and the one whose silence a reader would take for safety."
)


def _the_product_analysis_stage(graph: StateGraph, propose: Analyze) -> None:
    """Ask the product analyst what should be built, and hand the proposal to a person.

    Reached only through the router, so nothing here decides *whether* to propose — that is the
    router's whole job, and it is the difference between a pipeline and a run that does
    whatever it feels like next.
    """
    graph.add_node(
        "offer_the_work_item_to_the_product_analyst", offer_the_work_item_to_the_product_analyst
    )
    graph.add_node("begin_the_product_analysis", begin_the_product_analysis)
    graph.add_node("hand_the_requirements_to_a_human", hand_the_requirements_to_a_human)
    graph.add_node("apply_the_pickup_by_the_product_analyst", transition_the_work_item)
    graph.add_node("apply_the_product_analysis_begun", transition_the_work_item)
    graph.add_node("apply_the_handover_of_the_requirements", transition_the_work_item)
    graph.add_node(
        "write_what_the_product_analyst_found",
        record_what_this_run_has,
    )
    graph.add_node(
        "propose_requirements_for_this_run",
        lambda state: analyze_the_repository_in_this_run(state, propose),
    )
    graph.add_edge(
        "offer_the_work_item_to_the_product_analyst",
        "apply_the_pickup_by_the_product_analyst",
    )
    graph.add_edge("apply_the_pickup_by_the_product_analyst", "begin_the_product_analysis")
    graph.add_edge("begin_the_product_analysis", "apply_the_product_analysis_begun")
    graph.add_edge("apply_the_product_analysis_begun", "propose_requirements_for_this_run")
    graph.add_edge("propose_requirements_for_this_run", "write_what_the_product_analyst_found")
    graph.add_edge("write_what_the_product_analyst_found", "hand_the_requirements_to_a_human")
    graph.add_edge("hand_the_requirements_to_a_human", "apply_the_handover_of_the_requirements")
    graph.add_conditional_edges(
        "apply_the_handover_of_the_requirements", where_the_gate_leads, THE_GATE_IS_ANSWERED_BY
    )


def _the_qa_analysis_stage(graph: StateGraph, plan_the_tests: AnalyzeTheRequirements) -> None:
    """Ask the QA analyst how the work should be tested, and hand the plan to a person.

    The only stage whose node reads no clone, and the docstring on `qa_node.py` says why. It
    matters here too: the stage's *input* is the approved requirements, so this is the first
    place in the graph where a node's input is a thing a person ruled on rather than a thing
    the system fetched.
    """
    graph.add_node("offer_the_work_item_to_the_qa_analyst", offer_the_work_item_to_the_qa_analyst)
    graph.add_node("begin_planning_the_tests", begin_planning_the_tests)
    graph.add_node("hand_the_qa_plan_to_a_human", hand_the_qa_plan_to_a_human)
    graph.add_node("apply_the_pickup_by_the_qa_analyst", transition_the_work_item)
    graph.add_node("apply_the_test_planning_begun", transition_the_work_item)
    graph.add_node("apply_the_handover_of_the_qa_plan", transition_the_work_item)
    graph.add_node(
        "write_what_the_qa_analyst_planned",
        record_what_this_run_has,
    )
    graph.add_node(
        "plan_the_tests_for_this_run",
        lambda state: analyze_the_requirements_in_this_run(state, plan_the_tests),
    )
    graph.add_edge("offer_the_work_item_to_the_qa_analyst", "apply_the_pickup_by_the_qa_analyst")
    graph.add_edge("apply_the_pickup_by_the_qa_analyst", "begin_planning_the_tests")
    graph.add_edge("begin_planning_the_tests", "apply_the_test_planning_begun")
    graph.add_edge("apply_the_test_planning_begun", "plan_the_tests_for_this_run")
    graph.add_edge("plan_the_tests_for_this_run", "write_what_the_qa_analyst_planned")
    graph.add_edge("write_what_the_qa_analyst_planned", "hand_the_qa_plan_to_a_human")
    graph.add_edge("hand_the_qa_plan_to_a_human", "apply_the_handover_of_the_qa_plan")
    graph.add_conditional_edges(
        "apply_the_handover_of_the_qa_plan", where_the_gate_leads, THE_GATE_IS_ANSWERED_BY
    )


def _the_architecture_analysis_stage(graph: StateGraph, describe: AnalyzeTheArchitecture) -> None:
    """Ask the architecture analyst what the code is shaped like, and hand it to a person.

    The third analysis gate, and the first one whose artifact describes the repository rather
    than proposing something about it — which is why it is the gate most likely to be approved
    quickly and the one most worth a person's time.
    """
    graph.add_node(
        "offer_the_work_item_to_the_architecture_analyst",
        offer_the_work_item_to_the_architecture_analyst,
    )
    graph.add_node("begin_describing_the_architecture", begin_describing_the_architecture)
    graph.add_node(
        "hand_the_architecture_report_to_a_human", hand_the_architecture_report_to_a_human
    )
    graph.add_node("apply_the_pickup_by_the_architecture_analyst", transition_the_work_item)
    graph.add_node("apply_the_description_begun", transition_the_work_item)
    graph.add_node("apply_the_handover_of_the_architecture", transition_the_work_item)
    graph.add_node(
        "write_what_the_architecture_analyst_described",
        record_what_this_run_has,
    )
    graph.add_node(
        "describe_the_architecture_for_this_run",
        lambda state: analyze_the_architecture_in_this_run(state, describe),
    )
    graph.add_edge(
        "offer_the_work_item_to_the_architecture_analyst",
        "apply_the_pickup_by_the_architecture_analyst",
    )
    graph.add_edge(
        "apply_the_pickup_by_the_architecture_analyst", "begin_describing_the_architecture"
    )
    graph.add_edge("begin_describing_the_architecture", "apply_the_description_begun")
    graph.add_edge("apply_the_description_begun", "describe_the_architecture_for_this_run")
    graph.add_edge(
        "describe_the_architecture_for_this_run", "write_what_the_architecture_analyst_described"
    )
    graph.add_edge(
        "write_what_the_architecture_analyst_described", "hand_the_architecture_report_to_a_human"
    )
    graph.add_edge(
        "hand_the_architecture_report_to_a_human", "apply_the_handover_of_the_architecture"
    )
    graph.add_conditional_edges(
        "apply_the_handover_of_the_architecture", where_the_gate_leads, THE_GATE_IS_ANSWERED_BY
    )


def _the_security_analysis_stage(graph: StateGraph, inspect: InspectForSecurityRisk) -> None:
    """Ask the security analyst what is wrong, and hand the findings to a person.

    The last gate before anything is written, so it is the one where an approval is least
    reversible — and the one where the artifact's *silence* is the dangerous case, because a
    report finding nothing reads as a report saying the code is fine. The node refuses an empty
    report for exactly that reason.
    """
    graph.add_node(
        "offer_the_work_item_to_the_security_analyst",
        offer_the_work_item_to_the_security_analyst,
    )
    graph.add_node("begin_inspecting_for_security_risk", begin_inspecting_for_security_risk)
    graph.add_node("hand_the_security_report_to_a_human", hand_the_security_report_to_a_human)
    graph.add_node("apply_the_pickup_by_the_security_analyst", transition_the_work_item)
    graph.add_node("apply_the_inspection_begun", transition_the_work_item)
    graph.add_node("apply_the_handover_of_the_security_report", transition_the_work_item)
    graph.add_node(
        "write_what_the_security_analyst_found",
        record_what_this_run_has,
    )
    graph.add_node(
        "inspect_for_security_risk_in_this_run",
        lambda state: inspect_for_security_risk_in_this_run(state, inspect),
    )
    graph.add_edge(
        "offer_the_work_item_to_the_security_analyst",
        "apply_the_pickup_by_the_security_analyst",
    )
    graph.add_edge("apply_the_pickup_by_the_security_analyst", "begin_inspecting_for_security_risk")
    graph.add_edge("begin_inspecting_for_security_risk", "apply_the_inspection_begun")
    graph.add_edge("apply_the_inspection_begun", "inspect_for_security_risk_in_this_run")
    graph.add_edge("inspect_for_security_risk_in_this_run", "write_what_the_security_analyst_found")
    graph.add_edge("write_what_the_security_analyst_found", "hand_the_security_report_to_a_human")
    graph.add_edge(
        "hand_the_security_report_to_a_human", "apply_the_handover_of_the_security_report"
    )
    graph.add_conditional_edges(
        "apply_the_handover_of_the_security_report", where_the_gate_leads, THE_GATE_IS_ANSWERED_BY
    )


def _the_planning_stage(graph: StateGraph, plan: PlanTheChange) -> None:
    """Take the approved work, plan the change, and hand the plan to a person.

    Reached only through the router, so nothing in this function decides *whether* to plan —
    that is the router's whole job, and it is the difference between a pipeline and a run that
    does whatever it feels like next.
    """
    graph.add_node("plan_the_change", lambda state: plan_the_change_in_this_run(state, plan))
    graph.add_node("write_what_the_plan_says", record_what_this_run_has)
    graph.add_node("offer_the_work_item_to_the_planner", offer_the_work_item_to_the_planner)
    graph.add_node("begin_planning_the_change", begin_planning_the_change)
    graph.add_node("hand_the_plan_to_a_human", hand_the_plan_to_a_human)
    graph.add_edge(THE_NEXT_ARTIFACT_IS_A_PLAN, "apply_the_pickup_by_the_planner")
    graph.add_edge("apply_the_pickup_by_the_planner", "begin_planning_the_change")
    graph.add_edge("begin_planning_the_change", "apply_the_planning_begun")
    graph.add_edge("apply_the_planning_begun", "plan_the_change")
    graph.add_edge("plan_the_change", "write_what_the_plan_says")
    graph.add_edge("write_what_the_plan_says", "hand_the_plan_to_a_human")
    graph.add_edge("hand_the_plan_to_a_human", "apply_the_handover_of_the_plan")
    graph.add_conditional_edges(
        "apply_the_handover_of_the_plan", where_the_gate_leads, THE_GATE_IS_ANSWERED_BY
    )


def _the_implementation_stage(graph: StateGraph, apply_and_verify: ApplyAndVerify) -> None:
    """Take the approved plan, make the change, verify it, and hand the verification over.

    The last stage that is built. What follows the gate is the `aisdlc-pr` agent, which is not:
    §37 forbids a pull request being merged automatically, and an approval that leads straight to
    a delivery nobody opened would make the gate decorative.
    """
    graph.add_node(
        "make_and_verify_the_change",
        lambda state: apply_and_verify_in_this_run(state, apply_and_verify),
    )
    graph.add_node("write_what_the_change_says", record_what_this_run_has)
    graph.add_node("offer_the_work_item_to_the_implementer", offer_the_work_item_to_the_implementer)
    graph.add_node("begin_implementing_the_plan", begin_implementing_the_plan)
    graph.add_node("hand_the_verification_to_a_human", hand_the_verification_to_a_human)
    graph.add_edge(THE_NEXT_ARTIFACT_IS_THE_CHANGE, "apply_the_pickup_by_the_implementer")
    graph.add_edge("apply_the_pickup_by_the_implementer", "begin_implementing_the_plan")
    graph.add_edge("begin_implementing_the_plan", "apply_the_implementation_begun")
    graph.add_edge("apply_the_implementation_begun", "make_and_verify_the_change")
    # **No edge out of the node that makes the change, and the node names where it goes.** It
    # returns a `Command` on both outcomes — a refusal goes to the supervisor, a success goes to
    # `write_what_the_change_says` — and an edge here would fire *alongside* whichever `goto`
    # it chose. That is not a theoretical concern: it sent every repair down both paths at once
    # and LangGraph refused the run with "Can receive only one value per step" at
    # `requested_stage`. The same rule the supervisor already follows, for the same reason.
    graph.add_edge("write_what_the_change_says", "hand_the_verification_to_a_human")
    graph.add_edge("hand_the_verification_to_a_human", "apply_the_handover_of_the_verification")
    graph.add_conditional_edges(
        "apply_the_handover_of_the_verification", where_the_gate_leads, THE_GATE_IS_ANSWERED_BY
    )


def _recording_with(record: Record) -> Callable[[AgentState], dict]:
    """A node that writes what the run has and changes no channel.

    A named function rather than a lambda inline, because the difference from `record` is
    the whole point of it: the collaborator writes, and a node has to return a state
    update, and there is nothing here to update.
    """

    def writing_what_the_run_has(state: AgentState) -> dict:
        record(state)
        return {}

    return writing_what_the_run_has


def a_config(thread_id: str) -> dict:
    """The configuration that names the conversation a run belongs to.

    Without a `thread_id` under `configurable` the checkpointer has no primary key: the
    run cannot be resumed after an approval, and `get_state` raises rather than telling
    you why.
    """
    return {"configurable": {"thread_id": thread_id}}


# The types a checkpoint is allowed to hold. This is a security control and not a way to
# silence a warning: the runtime deserialises a checkpoint, so anything in it is code
# that will be constructed on read, and the safe default is to allow nothing it did not
# ship with. Naming our own types is the narrow way to say "these, and nothing else",
# and a test refuses to let a type be added to the domain without being named here.
#
# A bare `"aisdlc."` prefix would be the same claim with none of the checking, and a
# permissive serializer would be no claim at all.
TYPES_A_CHECKPOINT_MAY_HOLD = (
    # **`Artifact` and not `str`, and the reason a resumed run cannot do without it.** An enum
    # member is a `str` at runtime, so the serializer would very probably cope — and a
    # serializer that is very probably coping is how a run written to disk becomes a run that
    # cannot be resumed, on the day the runtime enforces it rather than the day it is written.
    Artifact,
    Stage,
    Role,
    Repository,
    WorkItem,
    # **Where a request was filed, named by the filing itself.** A checkpoint holding a work item
    # holds this inside it through `CommissionedRequest.filed_as`, and an unnamed type stops being
    # readable from a checkpoint in a later version of the runtime. The guard reported it the
    # moment the field was added, which is the whole reason it is a guard and not a comment.
    TheIssueThisAnswers,
    # **What every agent has done on a work item, and one agent's share of it.** A checkpoint holds
    # a work item holds this inside it, and the count is what makes a repeated artifact a new
    # version, so a checkpoint that could not read it back would resume a run that had forgotten
    # which versions a person had already approved. Both types are named because a checkpoint
    # holding the outer one holds the inner one inside it.
    TheWorkEachAgentHasDone,
    TheWorkOneAgentHasDone,
    # **A supervisor's answer, the per-agent verdict inside it, and the closed set it names a
    # place in.** A checkpoint of a run that was put back on a work item holds this, and a
    # checkpoint that could not read it back would resume a run that had forgotten it was being
    # repaired -- which is the one thing a repair has to be able to say about itself. All three
    # are named because a checkpoint holding the outer one holds the inner two inside it.
    WhatToRepeat,
    WhatOneAgentMustDoAgain,
    WhereTheRunShouldStartAgain,
    Approval,
    ApprovalQuestion,
    ApprovalDecision,
    # The clone a run is working on, and every artifact a run has produced so far. The
    # allowlist is a promise about the domain, and a state channel that gained a type
    # without this would stop being readable from a checkpoint in a future version of
    # the runtime — which is the failure `test_every_type_a_state_channel_holds_is_named_
    # for_the_serializer` exists to report, and it reported this one.
    ClonedRepository,
    DiscoveryReport,
    Requirements,
    # **An ambiguity says whether it blocks the work**, and it lives inside a requirements set in a
    # state channel. Named for the same reason every other name here is: an unnamed type stops
    # being readable from a checkpoint in a later version of the runtime, and this guard reported it
    # the moment the type appeared.
    AnAmbiguity,
    # **The attribution inside an ambiguity, named for the same reason the ambiguity is.** A
    # checkpoint holds a `Requirements` and that holds the enum, and the guard reported it the
    # moment the field was introduced — a second time for the same type of omission.
    WhoCanAnswerThisAmbiguity,
    QaPlan,
    ArchitectureReport,
    SecurityReport,
    FileToWrite,
    ImplementationPlan,
    VerificationReport,
    PullRequestRequest,
    AnOpenedPullRequest,
    # The types those artifacts hold rather than are. A checkpoint holds a whole
    # `SecurityReport` with its findings and their severities, so the runtime has to
    # construct every one of them to read the state back, and naming only the artifact
    # left the inner types unbuildable. `EvidenceFile` and `SuiteOutcome` were missing for
    # as long as `DiscoveryReport` and `VerificationReport` existed, which means every run
    # so far printed a deserialisation warning nobody had seen.
    EvidenceFile,
    SecurityFinding,
    Severity,
    SuiteOutcome,
    CommissionedRequest,
)


def a_checkpoint_serializer() -> JsonPlusSerializer:
    """A serializer that will read back exactly the types this graph puts in a state.

    LangGraph will block unlisted types in a future version, so the warning it prints
    today is a real deadline rather than noise. Turning it into an explicit list is
    better than setting a permissive flag, because a permissive flag means any type
    anybody ever put in a checkpoint is read back, and this is a process that runs
    untrusted pull requests.
    """
    # The constructor, not `with_msgpack_allowlist`: a default serializer is
    # permissive, and that method only adds to the hook without narrowing what the
    # deserialiser will accept, so the claim would have been true in name only.
    return JsonPlusSerializer(allowed_msgpack_modules=TYPES_A_CHECKPOINT_MAY_HOLD)


def _the_conflict_repair(
    graph: StateGraph, rebase_the_branch: RebaseTheBranchARunPushed
) -> None:
    """The one node a pull request GitHub will not merge is handed to, and nothing leaves it.

    **Registered beside the merge rather than inside a stage, because the merge owns it.** The
    refusal is raised by the merge and nowhere else, so a node wired into any other stage would be
    unreachable from the one place the conflict can happen.

    **No edge out of it either, because it hands control itself.** It names a repair and returns
    `Command(goto=...)`; an edge from here would be a second, competing answer to the same
    question, and the router's own rule is that a route has one destination.
    """
    settle = the_repair_chosen_using_the_configured_model(rebase_the_branch)

    graph.add_node(
        WHERE_THE_CONFLICT_IS_SETTLED,
        lambda state: settle(state, state["the_conflict_that_stopped_this_merge"]),
    )


def _the_repair_stage(graph: StateGraph, supervise: SuperviseARepair) -> None:
    """The one node a refusal is handed to, registered here because it is reachable from any stage.

    **Registered on its own rather than inside a stage, because no stage owns it.** The delivery
    hands a red suite here, the verification hands a test that observed nothing here, and the
    planner hands an uncollected test directory here — three stages that are not neighbours. A
    node wired into one of them would be reachable from that one, and the other two would get a
    refusal they cannot route.

    **The node takes no edge out of it, because it hands control itself.** It reads the card,
    asks the model, and returns `Command(goto=...)` naming the stage the run should start again
    at. An edge from here would be a second, competing answer to the same question, and the
    router's own rule is that a route has one destination.
    """
    graph.add_node(
        WHERE_THE_SUPERVISOR_DECIDES_WHETHER_TO_REPAIR,
        lambda state: supervise_a_repair_in_this_run(state, supervise),
    )


def _the_delivery_stage(graph: StateGraph, delivery: TheDeliveryOfThisRun) -> None:
    """Describe the delivery, put it to a person, and on their answer push and open it.

    **The last stage, and the only one whose output is a place rather than a finding.** Every
    other stage in this graph produces something somebody reads and rules on; this one, once a
    person has ruled on it, changes a repository somebody else owns. That is why it has its own
    gate and why nothing about it happens before the gate: §10 says a pull request is created
    "only after explicit human approval", and the seven gates before it decide whether a
    change may be *offered* while this one decides whether the offer may be *delivered*.

    Reached only through the router, so nothing here decides *whether* to deliver. The refusal
    for a run whose gates were not all approved lives in `a_request_for_the_delivery`, and the
    refusal for a request nobody approved lives in `open_the_delivery` — two rules, two names,
    and neither of them reachable from inside the graph.
    """
    graph.add_node(
        "offer_the_work_item_to_the_pull_request_agent",
        offer_the_work_item_to_the_pull_request_agent,
    )
    graph.add_node("begin_delivering_the_work_item", begin_delivering_the_work_item)
    graph.add_node("hand_the_delivery_to_a_human", hand_the_delivery_to_a_human)
    graph.add_node("apply_the_pickup_by_the_pull_request_agent", transition_the_work_item)
    graph.add_node("apply_the_delivery_begun", transition_the_work_item)
    graph.add_node("apply_the_handover_of_the_delivery", transition_the_work_item)
    graph.add_node("write_what_this_run_would_deliver", record_what_this_run_has)
    graph.add_node("describe_the_delivery_for_this_run", a_request_for_the_delivery)
    graph.add_node(
        "deliver_this_run",
        lambda state: open_the_delivery(
            state, delivery.our_copy, delivery.push_the_branch, delivery.open_the_pull_request
        ),
    )
    graph.add_edge(
        "offer_the_work_item_to_the_pull_request_agent",
        "apply_the_pickup_by_the_pull_request_agent",
    )
    graph.add_edge("apply_the_pickup_by_the_pull_request_agent", "begin_delivering_the_work_item")
    graph.add_edge("begin_delivering_the_work_item", "apply_the_delivery_begun")
    graph.add_edge("apply_the_delivery_begun", "describe_the_delivery_for_this_run")
    graph.add_edge("describe_the_delivery_for_this_run", "write_what_this_run_would_deliver")
    graph.add_edge("write_what_this_run_would_deliver", "hand_the_delivery_to_a_human")
    graph.add_edge("hand_the_delivery_to_a_human", "apply_the_handover_of_the_delivery")
    graph.add_conditional_edges(
        "apply_the_handover_of_the_delivery", where_the_gate_leads, THE_GATE_IS_ANSWERED_BY
    )
    # **A run that delivered is `DONE`, and the move goes through the transition node.** The run
    # used to go from the delivery straight to its summary, leaving the work item at
    # `AWAITING_HUMAN_APPROVAL` while everything on disk said the work was delivered. One edge
    # into `DONE` exists in the table and the run was not making it.
    graph.add_node("mark_the_work_item_delivered", mark_the_work_item_delivered)
    graph.add_node("apply_the_delivery_of_the_run", transition_the_work_item)
    # **No edge out of `deliver_this_run`; the node names where it goes.** Same reason as the
    # node that implements a plan: this one also returns a `Command(goto=...)` when a suite went
    # red, and an edge here fires alongside that goto, sending the run to the supervisor and down
    # the ordinary delivery path in the same step. It is the same defect that made every repair
    # crash the run, found here by reading for one shape rather than by running into it again.
    # **The question is asked between the delivery and `DONE`, and it is a node rather than
    # part of the delivery node** because the delivery already returned: it cannot be
    # something a node that has already handed control is also going to do. No edge out
    # of `deliver_this_run` either, for the same reason the supervisor has none.
    graph.add_node(
        "ask_github_whether_the_suite_went_green",
        lambda state: the_suite_is_asked_about_in_this_run(
            state, delivery.ask_whether_the_suite_went_green
        ),
    )
    graph.add_node(
        WHERE_THE_DELIVERY_IS_MERGED,
        lambda state: merge_the_delivery_in_this_run(state, delivery.merge_the_pull_request),
    )
    graph.add_edge("ask_github_whether_the_suite_went_green", WHERE_THE_DELIVERY_IS_MERGED)
    # **No edge out of the merge node, and that is why the node names its own destination.**
    # The node returns a `Command(goto=...)` — to the repair when GitHub says the pull request
    # conflicts, on to `mark_the_work_item_delivered` when it merged — so an edge here would fire
    # alongside whichever `goto` came back and mark a delivery that was never merged. Same
    # reason `deliver_this_run` has no edge out of it, found by reading for one shape here
    # rather than by running into it again.
    graph.add_edge("mark_the_work_item_delivered", "apply_the_delivery_of_the_run")
    graph.add_edge("apply_the_delivery_of_the_run", THE_RUN_IS_OVER)
