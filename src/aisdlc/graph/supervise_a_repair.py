"""The repair supervisor: it reads the card, decides, and says where the run starts again.

**A node that returns a `Command` rather than a dictionary, and that is the whole point.** Every
other node in this graph hands back channels and lets a declared edge decide where the run goes
next. A supervisor deciding which stage to repeat cannot be a channel and an edge, because the
edge is chosen *by the answer* — so the branch is written where the decision is made, as a
visible `if` over two literals, rather than in a table a reader has to find elsewhere.

**The two targets are literals here and not values read from the answer.** `Command(goto=...)`
takes a node name, and a node name read from a model is a model routing the graph — the one
thing in this pipeline declared as code rather than reasoned about. So the answer says *which of
these two*, and this function says *which node that is*.

**The supervisor leaves a comment before it acts, not after.** A decision nobody can find later
is a claim, and a run that repeats an agent's work and leaves no record of why is a run whose
second attempt is unexplainable to whoever reads it third.

**It decides whether to stop, and stopping is a refusal rather than a branch.** Every agent told
to stand down raises, naming `what_has_not_changed`, because a run that quietly returns to
nothing reads as a run that finished — and the two ways a repair loop ends must not look alike
in a record.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.types import Command
from pydantic import ValidationError

from aisdlc.domain.work_item import WorkItem
from aisdlc.graph.repeat_budget import (
    NO_REPEAT_APPLIES,
    THE_SETTING_NAMING_THE_REPEAT_BUDGET,
    how_many_repeats_a_run_may_buy,
)
from aisdlc.graph.the_prompt_to_supervise_a_repair import (
    THE_AGENT_THAT_SUPERVISES_A_REPAIR,
    the_prompt_to_supervise_a_repair,
)
from aisdlc.graph.what_to_repeat import WhatToRepeat, WhereTheRunShouldStartAgain
from aisdlc.llm.asking_a_model_for import ask_a_model_for
from aisdlc.llm.llm_configuration import a_configuration_from_the_environment
from aisdlc.llm.model_factory import a_model_for
from aisdlc.tools.what_people_said_about_a_work_item import (
    a_comment_was_left,
    what_people_said_about,
)

# **The two node names, named once, and a run may be put back to these two only.** A value read
# from the model would be a model routing the graph.
WHERE_THE_SUPERVISOR_DECIDES_WHETHER_TO_REPAIR = "supervise_a_repair"

# **The seam a graph is given, beside the node's own name.** The node takes a model, and a model
# is a fact about the deployment rather than about a run, so the graph is handed a callable and
# the factory closes over the model — the same arrangement every other reasoning node uses.
SuperviseARepair = Callable[..., Command]


class ThereIsNoSupervisorForThisRunError(Exception):
    """A refusal a stage could have been wrong, on a run nobody gave a supervisor to.

    **Raised rather than answered with a decision, because the run is not stopping.** The
    delivery reached a red suite, which is the one failure this whole mechanism is for, and
    answering it here would either end the run silently or invent a routing decision nobody
    made. The refusal names what is missing, and a test that reaches it finds out that it
    forgot to build a run that can repair rather than discovering it in production.
    """

    def __init__(self) -> None:
        """Say what is missing, because the run is at a stage that was wrong and not stopping.

        **The wording carries the instruction, not just the fact.** Whoever reads this in a
        trace is a person deciding whether to wire a supervisor into their deployment, and
        saying what to do about it is the difference between an hour and an afternoon.
        """
        super().__init__(
            "This run reached a stage that was wrong and nobody was given a supervisor to "
            "decide what to do about it. A run is given one by naming a supervise on "
            "TheAgentsThisRun, and a run that cannot repair stops instead of pretending."
        )


class ARefusalWithNoReasonToRepairError(Exception):
    """A run handed the supervisor a refusal and left the reason out of it.

    **Not the same fault as a missing supervisor, and it is named apart for that reason.** A
    supervisor that was never given is a deployment that cannot repair; a refusal with no reason
    is a caller that reached the repair without saying what is wrong. Reusing one error for both
    would have told whoever reads the trace that a supervisor was missing when one was standing
    right there — the failure this repository's own record is full of: a message that looks like
    the right shape and names the wrong thing.
    """

    def __init__(self) -> None:
        """Say that the reason is missing, and not that the supervisor is — which it is.

        **A trace that names the wrong fault sends the reader after something present.** Both
        of these refusals end a run at the same node, and the whole reason they are two errors
        is that a reader who was told the supervisor was missing would go looking for a
        deployment problem and find a working one.
        """
        super().__init__(
            "This run was sent to the supervisor without saying what stopped it. The supervisor "
            "decides on the refusal's own words, so a refusal that carries none is a question "
            "with half of it missing."
        )


def no_supervisor_was_given_to_this_run(*_arguments: object, **_keywords: object) -> Command:
    """The default seam, which refuses, so a run cannot arrive here having quietly done nothing.

    **A default that refuses rather than a required field, and the reason is fifty-four tests.**
    Every graph test that assembles a run would otherwise have to name a supervisor it never
    reaches, and a field added for one node's sake would be paid for by every test in the
    package. This refuses when it runs — the same choice as
    `an_implementation_this_test_did_not_ask_for` and `a_delivery_that_refuses_to_deliver`:
    louder than doing nothing quietly, and it names the omission.
    """
    raise ThereIsNoSupervisorForThisRunError
WHERE_THE_IMPLEMENTATION_IS_REWRITTEN = "offer_the_work_item_to_the_implementer"
WHERE_THE_PLAN_IS_REWRITTEN = "offer_the_work_item_to_the_planner"


class TheSupervisorJudgedThisIsNotRepairingError(Exception):
    """The rule is in this module: a run stops when every agent is told to stand down.

    Raised rather than returning the end of the run, because the two ways a repair loop ends
    must not look alike in a record. A run that returns quietly reads as a run that finished,
    and a reader finding a work item stopped will look for the reason and find none. The reason
    is in the message: the sentence the supervisor named as unchanged.
    """


class TheRepeatBudgetRanOutError(Exception):
    """The rule is that a deployment's ceiling on repeats is what stopped this run.

    A separate type from `TheSupervisorJudgedThisIsNotRepairingError` because the two are
    different facts: the supervisor judged a repair pointless, or the supervisor judged a repair
    worth trying and the deployment overruled it. A reader who cannot tell them apart goes to
    the wrong place — one to read the card, the other to read the setting.
    """


class ThereIsNoNodeForThatPlaceToStartAgainError(Exception):
    """The rule is that the answer is a closed set and this function is where it becomes a node.

    A destination with no node behind it is a run that stops for ever with no refusal to show,
    and the set is small enough that reaching this means the enum grew a value and the `if` below
    did not — which is a change and not a run.
    """


class ARepairThatOnlyAGateMayDecideError(Exception):
    """The rule is that the state machine releases a work item to a person and not to a peer.

    **This type exists so a run that is sent back to another discipline stops with a sentence
    rather than with a `StateMachineError` traceback.** The refusal underneath is correct — see
    `_takes_the_work_item_from_the_holding_agent` — and a correct refusal delivered as a traceback
    is still a defect, because the person reading it learns that something about agents is broken
    rather than which hand-over was asked for and what the table allows instead.

    **Nothing raises it yet.** It is the shell a test needs in order to be a test at all, and a
    shell that raises nothing is the honest shape: a test that demanded this name before any code
    produced it would fail on `ImportError`, which says nothing about the rule.
    """


def supervise_a_repair(
    work_item: WorkItem,
    projects_root: Path,
    what_stopped_the_run: str,
    model: BaseChatModel,
) -> Command:
    """Read the card, ask the model what to repeat, leave a comment, and return where to go.

    **The card is read from the project directory rather than from the run's state**, because a
    resumed run finds it there — and a supervisor handed a state channel is a supervisor handed
    whatever the last node happened to write down, which on a resumed run is not necessarily what
    the earlier attempt said.

    **An answer that cannot be validated stops this run, and says the validator's words.** This is
    the one node in the pipeline with no correction loop: seven others spend from the shared budget
    to ask a model again, and the supervisor asked once and propagated the `ValidationError`. A
    real run reached the repair loop for the first time in this copy's history — six gates
    approved, the change written, the suite run three times in a container — and died there with
    `1 validation error for WhatToRepeat`, because the model gave verdicts for two agents and
    forgot five. **A run that stops on a Python exception has stopped on a fault rather than on a
    decision**, and the rule this repository exists to keep is that a refusal is a decision and is
    recorded as one.

    So the validators that make a supervisor's answer mean anything are also what makes it
    un-answerable, and the two are the same thing: a verdict for every agent, a stop that names
    what has not changed. A model whose answer cannot be expressed **has said nothing**, and a run
    that received nothing should stop for the same reason and say why — naming the agents it
    forgot, because a model correcting itself has to be told what it missed and not only that it
    was wrong.

    **A correction is not added here, and the reason is that the budget is shared.** Every other
    node asks again and spends from `may_this_run_keep_asking`; adding a loop here would make the
    eighth claim on one budget, and the count of things that may ask again is exactly the kind of
    number that drifts when it is written per node. What is added instead is the outcome that was
    already in this module for a model that declined in words — a refusal carrying the reason — so
    an un-answerable model and an answerable one that declines leave the same kind of record.
    """
    what_the_record_says = what_people_said_about(
        work_item.repository, work_item.work_item_id, projects_root
    )

    try:
        the_decision = WhatToRepeat.model_validate(
            ask_a_model_for(model, WhatToRepeat).invoke(
                the_prompt_to_supervise_a_repair(
                    work_item, what_the_record_says.comments, what_stopped_the_run
                )
            )
        )
    except ValidationError as no_verdict_was_reachable:
        why_this_run_stops = (
            f"{THE_AGENT_THAT_SUPERVISES_A_REPAIR} reached no verdict about what to repeat. The "
            f"answer it was given cannot be one:\n\n{no_verdict_was_reachable}\n\nThis run "
            "stops rather than trying again, and the reason is that there was nothing to act on. "
            "A run that returned quietly would read as a run that finished."
        )

        # **The card is written before the refusal, not after, because after is never reached.**
        # Every other note this module leaves is written on the way to a `Command`; a run that
        # raises here would otherwise leave a card saying it was refused for the reason the
        # *implementer* gave, which is now a lie. This one is written first so that the sentence a
        # person reads is the sentence that stopped the run.
        a_comment_was_left(
            work_item,
            what_was_said=why_this_run_stops,
            by=THE_AGENT_THAT_SUPERVISES_A_REPAIR,
            at=datetime.now(UTC),
            projects_root=projects_root,
        )

        raise TheSupervisorJudgedThisIsNotRepairingError(why_this_run_stops) from (
            no_verdict_was_reachable
        )

    a_comment_was_left(
        work_item,
        what_was_said=the_text_of_the_decision_this_is(the_decision),
        by=THE_AGENT_THAT_SUPERVISES_A_REPAIR,
        at=datetime.now(UTC),
        projects_root=projects_root,
    )

    _note_which_ceiling_applies(work_item, the_decision, projects_root)

    if the_decision.nobody_is_to_repeat_anything():
        raise TheSupervisorJudgedThisIsNotRepairingError(
            f"{the_decision.what_has_not_changed}. Every agent was told to stand down, so this "
            f"run stops rather than trying again, and the sentence above is the reason: a run "
            f"that returned quietly would read as a run that finished"
        )

    the_ceiling_stops = _an_agent_the_supervisor_named_is_out_of_turns(work_item, the_decision)
    if the_ceiling_stops is not None:
        how_many_repeats_may_be_bought = how_many_repeats_a_run_may_buy()
        raise TheRepeatBudgetRanOutError(
            f"{the_ceiling_stops} has already had every turn the ceiling allows, and the "
            f"supervisor's judgement was that it should have another. So this run stops on the "
            f"ceiling rather than on the judgement: the supervisor read the same card on every "
            f"attempt, asked for another, and was overruled. Its judgement failed, and a record "
            f"reading as a clean stop would hide that. {THE_SETTING_NAMING_THE_REPEAT_BUDGET} "
            f"is {how_many_repeats_may_be_bought} here"
        )

    if the_decision.where_to_start_again is WhereTheRunShouldStartAgain.THE_CHANGE_IS_PLANNED_AGAIN:
        return Command(goto=WHERE_THE_PLAN_IS_REWRITTEN, update={"repair": the_decision})

    if the_decision.where_to_start_again is WhereTheRunShouldStartAgain.THE_CHANGE_IS_WRITTEN_AGAIN:
        return Command(goto=WHERE_THE_IMPLEMENTATION_IS_REWRITTEN, update={"repair": the_decision})

    raise ThereIsNoNodeForThatPlaceToStartAgainError(
        f"{the_decision.where_to_start_again} is one of the two places a run may be put back to "
        f"and neither has a node behind it, which is a change to this function and not a run"
    )


def _note_which_ceiling_applies(
    work_item: WorkItem, the_decision: WhatToRepeat, projects_root: Path
) -> None:
    """Say on the card that a ceiling stopped this run, when one did.

    **Written as a second note rather than folded into the decision's own**, because the
    decision is the supervisor's and the ceiling is the deployment's, and a record blending them
    attributes to one of them a decision the other made.
    """
    an_agent_out_of_turns = _an_agent_the_supervisor_named_is_out_of_turns(
        work_item, the_decision
    )
    if an_agent_out_of_turns is None:
        return

    a_comment_was_left(
        work_item,
        what_was_said=(
            f"the ceiling stopped this run: {an_agent_out_of_turns} had already had every turn "
            f"the ceiling allows, and the supervisor asked for another anyway. The judgement "
            f"above failed and the deployment overruled it; read "
            f"{THE_SETTING_NAMING_THE_REPEAT_BUDGET} for the number"
        ),
        by=THE_AGENT_THAT_SUPERVISES_A_REPAIR,
        at=datetime.now(UTC),
        projects_root=projects_root,
    )


def _an_agent_the_supervisor_named_is_out_of_turns(
    work_item: WorkItem, the_decision: WhatToRepeat
) -> str | None:
    """The first agent the supervisor named whose turns are spent, or `None` when none are.

    **Zero means the ceiling does not apply and nothing is ever out of turns**, which is what a
    deployment lifting it wrote and the reason the constant is named rather than read as a count.
    """
    how_many_repeats_may_be_bought = how_many_repeats_a_run_may_buy()

    if how_many_repeats_may_be_bought == NO_REPEAT_APPLIES:
        return None

    for verdict in the_decision.what_each_agent_must_do:
        if not verdict.must_repeat_its_work:
            continue
        turns_taken = work_item.work_done.how_many_times_this_agent_has_worked(verdict.agent)
        if turns_taken >= how_many_repeats_may_be_bought:
            return verdict.agent

    return None


def the_text_of_the_decision_this_is(the_decision: WhatToRepeat) -> str:
    """What the supervisor left on the card, and the two things a person reads to judge it.

    **Every verdict is written out, including the ones that stand an agent down.** A record
    saying only who repeats cannot be argued with afterwards, and a reader who disagrees with
    the plan being rewritten has nothing to point at.
    """
    verdicts = "\n".join(
        f"- {verdict.agent}: "
        f"{'repeat' if verdict.must_repeat_its_work else 'stand down'} — {verdict.why}"
        for verdict in sorted(the_decision.what_each_agent_must_do, key=lambda v: v.agent)
    )
    return (
        f"where this run starts again: {the_decision.where_to_start_again.value}\n"
        f"what has not changed: {the_decision.what_has_not_changed}\n"
        f"{verdicts}"
    )


def the_supervisor_using_the_configured_model() -> SuperviseARepair:
    """The real supervisor: the model the deployment's environment names.

    **This factory exists because a real run reached the node and found nothing there.** The
    default `TheAgentsThisRun.supervise` keeps is a function that refuses, which is the right
    default for a graph test that never reaches a repair and the wrong one for a run that does.
    A factory rather than a default argument on `the_lifecycle`, for the reason every other
    agent has one: the graph is handed a function and does not know how a model is obtained.
    """
    def supervising(
        work_item: WorkItem, projects_root: Path, what_stopped_the_run: str
    ) -> Command:
        return supervise_a_repair(
            work_item,
            projects_root,
            what_stopped_the_run,
            a_model_for(a_configuration_from_the_environment()),
        )

    return supervising
