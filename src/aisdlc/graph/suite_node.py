"""The node that asks GitHub whether anything proved the commit about to be merged.

**This node is the caller `the_suite_went_green` was written for and did not have.** The tool's
own eleven tests were green from the day it was written while no run had ever asked it, and a
tool with no caller is a tool that never runs — which reads from the outside exactly like
success, because the run still reaches `DONE` and still says it delivered.

**It sits between the delivery and `DONE`, and it is not a gate of its own.** A person has
already ruled on the delivery; what happens next to it on somebody else's repository is a fact
about the commit GitHub is holding, and this process cannot be the authority for it. So there is
no ninth gate and no ninth decision — **the question is asked and the answer is obeyed.** Every
refusal the tool raises propagates, because a node that caught it and carried on would deliver
on the strength of nothing and put the reason in a log nobody reads.

**What it records is the commit and the checks, not the word *green*.** A person reading the card
in a month has to be able to see which commit was proved and by which checks, and "green" on its
own is a verdict with nothing behind it.
"""

from __future__ import annotations

from collections.abc import Callable

from aisdlc.domain.repository import Repository
from aisdlc.graph.agent_state import AgentState
from aisdlc.tools.github_create_pull_request import AnOpenedPullRequest
from aisdlc.tools.the_suite_went_green import WhatTheSuiteSaid

WHERE_THE_SUITE_IS_ASKED_ABOUT = "ask_github_whether_the_suite_went_green"

AskWhetherTheSuiteWentGreen = Callable[
    [AnOpenedPullRequest, Repository], WhatTheSuiteSaid
]
"""What the delivery is asked for the question, and why in that order.

**The pull request first and the repository second**, because the pull request is what names the
commit and the repository is what GitHub is asked about it. Reversed, a caller would have to
remember which of the two is which at every call site, and there are two call sites.
"""


def the_suite_is_asked_about_in_this_run(
    state: AgentState,
    ask_whether_the_suite_went_green: AskWhetherTheSuiteWentGreen,
) -> dict[str, object]:
    """Ask GitHub, write down what it said, and hand back what the next node needs.

    **A refusal is not caught here.** `the_suite_went_green` raises four named errors and each
    of them is a different fact a reader has to be able to act on; catching them to log them
    would put the one thing that matters in the place nobody reads.
    """
    the_pull_request = _the_pull_request_this_run_opened(state)
    the_repository = state["work_item"].repository

    what_the_suite_said = ask_whether_the_suite_went_green(the_pull_request, the_repository)

    return {
        "the_commit_anything_proved": what_the_suite_said.head_commit,
        "which_checks_went_green": what_the_suite_said.which_checks_went_green,
    }


def _the_pull_request_this_run_opened(state: AgentState) -> AnOpenedPullRequest:
    """The pull request this run opened, and a refusal when the run opened none.

    **Read from the state and not recomputed**, because the delivery already opened it and
    asking GitHub about a pull request number this run did not receive would be asking about
    somebody else's delivery.
    """
    opened = state.get("opened_pull_request")

    if opened is None:
        raise TheRunOpenedNoPullRequestToBeMergedError

    return AnOpenedPullRequest(number=opened.number, address=opened.address)


class TheRunOpenedNoPullRequestToBeMergedError(Exception):
    """The graph reached the merge with no pull request in its state, which the delivery made.

    **A wiring fault rather than a fact about the world.** The delivery node writes
    `opened_pull_request` on the way past, so a run arriving here without one was wired wrong —
    and the run is not equipped to notice, because asking GitHub about nothing returns nothing.
    """
