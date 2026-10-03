"""The node that settles a conflict, and the question it puts to a model.

**A conflict is the one refusal the merge node does not simply let propagate.**
`merge_a_pull_request` reads `mergeable: false` and refuses without asking, because GitHub words a
conflict and a protected base branch alike — and swallowing that to log it would put the one thing
that matters in the place nobody reads.

**What is known arrives as the caller's own words.** The tool that refused read the facts from
GitHub, and **a decision made on a summary of a conflict is a decision about the summary** — so
the refusal is passed through whole and nothing here restates it. What this node adds is the
question and the validation, which is the two halves of what §0.3 lets pytest own.

**The question is reached by name and not written here**, because a sentence written in a node is a
sentence no agent owns and `evals/` cannot grade. `the_question_about_a_conflict_in_these_words`
lives beside the answer it produces.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langgraph.types import Command
from pydantic import ValidationError

from aisdlc.agents.what_to_do_when_a_pull_request_will_not_merge import (
    AnAnswerThatIsNotADecisionError,
    WhatToDoAroundAConflict,
    WhatToDoWhenThePullRequestWillNotMerge,
    the_question_about_a_conflict_in_these_words,
)
from aisdlc.graph.agent_state import AgentState
from aisdlc.graph.merge_node import (
    NothingWasProvedAboutAnyCommitError,
)
from aisdlc.graph.router import THE_RUN_IS_OVER
from aisdlc.graph.suite_node import WHERE_THE_SUITE_IS_ASKED_ABOUT
from aisdlc.llm.asking_a_model_for import ask_a_model_for
from aisdlc.llm.correction_budget import (
    how_a_model_is_told_what_was_wrong,
    may_this_run_keep_asking,
)
from aisdlc.llm.llm_configuration import a_configuration_from_the_environment
from aisdlc.llm.model_factory import a_model_for
from aisdlc.tools.rebase_the_branch_a_run_pushed import WhatTheRebaseLanded

RebaseTheBranchARunPushed = Callable[[Path, str, str, str], WhatTheRebaseLanded]
"""The rebase, and the four facts it is asked with, in the order it is asked with them.

**The clone first, then the lease, then the two branches.** The lease is the commit the checks
were read about and the branch is expected to be at, and it comes before the branches because it is
the fact that decides whether the rebase is allowed to move anything at all.
"""


def settle_a_conflict_in_this_run(
    state: AgentState,
    a_model: BaseChatModel,
    rebase_the_branch: RebaseTheBranchARunPushed,
    the_conflict_as_it_was_refused: str,
) -> Command:
    """Take the repair the model named, and go where that repair leaves the run.

    **Two names and two destinations, and that is the whole of what makes this a choice.** A set
    of repairs where every name leads to the same place is a set of words, and a model asked to
    pick one is being asked to choose a synonym.

    **The rebase goes back to the suite question rather than straight at the merge**, because a
    rebase replaces the commit the checks were read about with a new one that nothing has proved
    yet. Asking again is the only move that learns whether GitHub's answer changed — and
    `NothingHasProvedThisCommitError` is what it will get if the checks have not run on the new
    commit yet, which is the truth and not a fault.
    """
    the_decision = _the_decision_a_model_made(
        a_model, the_question_about_a_conflict_in_these_words(the_conflict_as_it_was_refused)
    )

    if the_decision.the_repair is WhatToDoWhenThePullRequestWillNotMerge.REBASE_IT_AND_TRY_AGAIN:
        return _a_rebase_is_taken(state, rebase_the_branch, the_decision.why)

    return _it_is_left_open(the_conflict_as_it_was_refused, the_decision.why)


def _a_rebase_is_taken(
    state: AgentState, rebase_the_branch: RebaseTheBranchARunPushed, the_grounds: str
) -> Command:
    """Replay the branch on what was fetched, ask about the suite again, and write down why.

    **The card is written on this branch too, and a real model is what showed it was missing.**
    Asked which repair to take, `space-bunny-free` named the rebase and said why — and the run
    rebased and wrote nothing. **The branch where the run does something was the branch that kept
    no record of why it did it**, and the branch that stops wrote a paragraph. Every other verdict
    in this package carries its grounds for the reason `ApprovalDecision.reason` is required, and
    this was the only one whose grounds were assumed to travel with it.

    **What is written is the grounds and nothing about the commit.** `the_commit_anything_proved`
    is the suite node's to write — it overwrites the field with the head GitHub reports — so
    writing it here as well would be a second mechanism for one fact, and the two could disagree
    about which commit the checks were about.
    """
    rebase_the_branch(*_the_rebase_this_run_is_asking_for(state))

    return Command(
        goto=WHERE_THE_SUITE_IS_ASKED_ABOUT,
        update={"what_stopped_this_run": _why_this_run_rebased(the_grounds)},
    )


def _why_this_run_rebased(the_grounds: str) -> str:
    """What the card says about a repair that is going to be taken and is not the end of a run.

    **The same channel the stopping branch uses, and the reason is that it is a note rather than a
    verdict.** `what_stopped_this_run` is what a reader asks to find out why a run did what it
    did, and a rebase stops nothing — so the sentence says what was decided rather than claiming
    the run ended. **A second channel for it would make two places a person looks**, and the whole
    of what makes a note readable is that there is one.
    """
    return (
        f"This run chose to rebase the branch and try the merge again. Its grounds: {the_grounds}"
    )


def _it_is_left_open(the_conflict_as_it_was_refused: str, the_grounds: str) -> Command:
    """Stop, and write down both what GitHub said and the grounds for stopping.

    **The model's own words and not a sentence composed here.** A run that stops because it chose
    to stop has to be distinguishable from a run that finished, and the only place a person reads
    why is this note — so a paraphrase written here would be a reason nobody gave.
    """
    return Command(
        goto=THE_RUN_IS_OVER,
        update={
            "what_stopped_this_run": (
                f"{the_conflict_as_it_was_refused}\n\nThis run chose to leave the pull request "
                f"open. Its grounds: {the_grounds}"
            )
        },
    )


def _the_rebase_this_run_is_asking_for(state: AgentState) -> tuple[Path, str, str, str]:
    """The clone, the lease, and the two branches, every one read from what is already there.

    **The branches come from the request the delivery built and not from a name derived again.**
    `deliver_node` put `branch` and `base` into the state when it opened the pull request, and
    deriving them a third time here would be a third place where the branch a delivery lands on
    could be spelled differently from the branch it was actually opened against.

    **The lease is the commit the checks were read about, and a run without one is wired wrong.**
    The merge node refuses on an absent commit before it ever asks GitHub anything, so it cannot
    have raised a conflict without one — and a rebase handed a blank lease would push over
    whatever is on the branch, which is the one thing the lease exists to prevent.
    """
    the_pull_request_request = state.get("pull_request_request")
    the_commit = state.get("the_commit_anything_proved")
    the_clone = state.get("clone")

    if the_pull_request_request is None:
        raise TheRunOpenedNoPullRequestToConflictOverError

    if not the_commit:
        raise NothingWasProvedAboutAnyCommitError

    if the_clone is None:
        raise TheRunHasNoCloneToRebaseInError

    return (
        the_clone.path,
        the_commit,
        the_pull_request_request.branch,
        the_pull_request_request.base,
    )


def _the_decision_a_model_made(
    a_model: BaseChatModel, the_question: str
) -> WhatToDoAroundAConflict:
    """The model's answer, validated, asked for again on a malformed one, and refused by name.

    **A malformed answer is asked again, and that is the whole of this change.** This node invoked
    the model once and handed whatever came back to `model_validate`, and this deployment's own
    runs say what that costs: **the three tests in `test_settle_a_conflict_in_this_run.py` fail two
    at a time, always the same two, and the reason in the log is the shape itself** -
    `input_value=None`, a message the structured-output parser read as nothing. **A node that dies
    on one malformed answer is effectively dead here**, and it dies while the run is holding an
    open conflict, which is the one place a run most needs a second attempt.

    **`how_a_model_is_told_what_was_wrong` and not the question again unchanged**, because asking
    twice is the loop and saying why the last answer was refused is the other half. Without the
    second half the loop is a second chance at the same question rather than a repair.

    **Bounded by the shared correction budget, and the refusal survives it.** A run whose model can
    name no repair at all delivered a merge nobody can merge, and saying so is the last useful thing
    this node can do - so the refusal is still `AnAnswerThatIsNotADecisionError`, carrying the
    validation error a person actually has to read.
    """
    began_at = time.monotonic()
    asked_so_far = 0
    what_was_wrong = ""

    while may_this_run_keep_asking(asked_so_far, began_at):
        asked_so_far += 1
        try:
            return WhatToDoAroundAConflict.model_validate(
                ask_a_model_for(a_model, WhatToDoAroundAConflict).invoke(
                    the_question + what_was_wrong
                )
            )
        except ValidationError as no_repair_was_named:
            what_was_wrong = how_a_model_is_told_what_was_wrong(no_repair_was_named)
            last = no_repair_was_named
    else:
        raise AnAnswerThatIsNotADecisionError(
            f"the model named no repair this run could take, and said nothing for one after being "
            f"asked {asked_so_far} times. What it was given cannot be a decision:\n\n{last}"
        ) from last


class TheRunOpenedNoPullRequestToConflictOverError(Exception):
    """The graph reached a conflict with no pull request in its state, which the delivery made.

    **The same fault as the suite node's, and refused under the same reasoning.** The delivery
    wrote `pull_request_request` and both branches this repair needs are on it, so a run arriving
    without one was wired wrong — and naming it here beats asking a model about a conflict with no
    pull request in it.
    """


class TheRunHasNoCloneToRebaseInError(Exception):
    """A rebase is a git operation on the clone, and this run has none to perform it in.

    **The clone is written once, by the clone node, before any agent reads the repository.** So a
    run that reached a delivery's merge without one is not unlucky, it is unwired — and a rebase
    handed no directory would be a `git` call in whatever the process considers its working
    directory.
    """


SettleAConflictInThisRun = Callable[[AgentState, str], Command]
"""The conflict repair, and the refusal it settles — the state and the words GitHub used."""


def the_repair_chosen_using_the_configured_model(
    rebase_the_branch: RebaseTheBranchARunPushed,
) -> SettleAConflictInThisRun:
    """The real repair: the model the deployment's environment names, and the rebase beside it.

    **A factory rather than a model read inside the node**, for the reason every other agent here
    has one: the graph is handed a function and does not know how a model is obtained. A node
    that read `AISDLC_*` itself would be a node that cannot be exercised without a deployment.

    **And a model per call rather than one built here**, because a run that settles a conflict
    once has no second model to reuse and a stale one would be a model from a different
    configuration answering about a different run.
    """

    def settling(the_run: AgentState, the_conflict_as_it_was_refused: str) -> Command:
        return settle_a_conflict_in_this_run(
            the_run,
            a_model_for(a_configuration_from_the_environment()),
            rebase_the_branch,
            the_conflict_as_it_was_refused,
        )

    return settling
