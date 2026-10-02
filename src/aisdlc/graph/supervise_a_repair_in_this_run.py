"""The node that reads a run's card and asks a model what to repeat.

**The state is read here and nowhere else, because the model is the seam and the state is not.**
`supervise_a_repair` takes a work item, a projects root, the refusal's own words and a model.
Which of those live in the run's state is a fact about this graph and not about the supervisor,
so it is settled in this one place — and every other node in this package is wired the same way,
by a lambda that turns a state into arguments.

**The refusal arrives as text and is not summarised on the way in.** A supervisor asked to decide
on a paragraph written for a person is deciding on a summary, and the whole note mechanism
exists so that a later agent reads what an earlier one actually wrote.
"""

from __future__ import annotations

from langgraph.types import Command

from aisdlc.domain.stage import Stage
from aisdlc.domain.work_item import WorkItem
from aisdlc.graph.agent_state import WHAT_STOPPED_THIS_RUN, AgentState
from aisdlc.graph.supervise_a_repair import (
    WHERE_THE_PLAN_IS_REWRITTEN,
    ARefusalWithNoReasonToRepairError,
    ARepairThatOnlyAGateMayDecideError,
    SuperviseARepair,
)
from aisdlc.graph.the_agents_a_run_reasons_with import THE_DEVELOPER_PLANNING_AGENT


def supervise_a_repair_in_this_run(state: AgentState, supervise: SuperviseARepair) -> Command:
    """Ask the supervisor what to repeat, having read the refusal out of the run's state.

    **A refusal with no text is refused rather than handed over as an empty question.** The
    supervisor is told a stage was wrong; what it was wrong about is the evidence, and a prompt
    with the first half and not the second is a model asked to guess.
    """
    what_stopped_this_run = state.get(WHAT_STOPPED_THIS_RUN)

    if not what_stopped_this_run:
        raise ARefusalWithNoReasonToRepairError

    where_it_was = state["work_item"]
    where_the_supervisor_says_to_start_again = supervise(
        where_it_was,
        state["projects_root"],
        what_stopped_this_run,
    )

    _refuse_a_repair_only_another_discipline_may_decide(
        where_it_was, where_the_supervisor_says_to_start_again
    )

    return where_the_supervisor_says_to_start_again


def _refuse_a_repair_only_another_discipline_may_decide(
    work_item: WorkItem, where_the_supervisor_says_to_start_again: Command
) -> None:
    """Say the state machine will not carry this repair, before it raises for asking.

    **Here and not inside the supervisor, because the supervisor is the seam.** Every test replaces
    it, and a guard that lived behind the seam would have been green through all of run 13 while
    the run died on the `StateMachineError` it exists to prevent. This is the node that turns the
    supervisor's answer into a route, so this is where the route is checked.

    **The refusal underneath is correct and this does not touch it.** A work item is released to a
    human and not to a peer — the single-writer rule, enforced at the only door a work item has.
    A repair from one agent to another is a hand-over between peers, so
    `IN_PROGRESS_BY_AGENT -> AWAITING_AGENT_PICKUP` naming a different agent is a move the
    transition table allows by stage and the rule refuses by agent. What was missing is the
    sentence: a real run followed this `goto` faithfully and got a traceback saying something
    about agents is broken, with no way through it.

    **And this refuses to pretend to know where the repair should have gone.** The only edge out
    of a stage somebody holds to a stage nobody holds is `AWAITING_HUMAN_APPROVAL`, so a
    hand-over to another discipline is a decision for a gate. Which artifact that gate asks about,
    and whether the supervisor's verdict is what it rules on, are questions about the lifecycle
    rather than about this function — so this names the block and stops, and does not guess.
    """
    if where_the_supervisor_says_to_start_again.goto != WHERE_THE_PLAN_IS_REWRITTEN:
        return

    if work_item.agent is None or work_item.agent == THE_DEVELOPER_PLANNING_AGENT:
        return

    raise ARepairThatOnlyAGateMayDecideError(
        f"{work_item.agent} holds this work item, and the supervisor's answer is to hand it to "
        f"{THE_DEVELOPER_PLANNING_AGENT} instead. A work item is released to a human and not to "
        f"another agent, so that move is refused at the only door a work item has.\n\n"
        f"The work item is at {work_item.stage.value}, and the one move the transition table "
        f"allows from a stage somebody holds to a stage nobody holds is "
        f"{Stage.AWAITING_HUMAN_APPROVAL.value}. A hand-over to another discipline is therefore "
        f"a decision for a gate and not for the supervisor: the supervisor may say what has not "
        f"changed and where to start again, and it may not decide who holds the work."
    )
