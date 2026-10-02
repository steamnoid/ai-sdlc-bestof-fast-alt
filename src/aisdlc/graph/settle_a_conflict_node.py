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

from collections.abc import Callable
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langgraph.types import Command
from pydantic import ValidationError

from aisdlc.agents.what_to_do_when_a_pull_request_will_not_merge import (
    AnAnswerThatIsNotADecisionError,
    WhatToDoAroundAConflict,
    the_question_about_a_conflict_in_these_words,
)
from aisdlc.graph.agent_state import AgentState
from aisdlc.graph.router import THE_RUN_IS_OVER
from aisdlc.llm.asking_a_model_for import ask_a_model_for
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
    """Ask which of the two repairs to take, and refuse an answer that is not one of them."""
    the_decision = _the_decision_a_model_made(
        a_model, the_question_about_a_conflict_in_these_words(the_conflict_as_it_was_refused)
    )

    return Command(
        goto=THE_RUN_IS_OVER,
        update={
            "what_stopped_this_run": (
                f"{the_conflict_as_it_was_refused}\n\nThis run chose to leave the pull request "
                f"open. Its grounds: {the_decision.why}"
            )
        },
    )


def _the_decision_a_model_made(
    a_model: BaseChatModel, the_question: str
) -> WhatToDoAroundAConflict:
    """The model's answer, validated, and a refusal that carries the answer it refused."""
    try:
        return WhatToDoAroundAConflict.model_validate(
            ask_a_model_for(a_model, WhatToDoAroundAConflict).invoke(the_question)
        )
    except ValidationError as no_repair_was_named:
        raise AnAnswerThatIsNotADecisionError(
            f"the model named no repair this run could take, and said nothing for one. What it was "
            f"given cannot be a decision:\n\n{no_repair_was_named}"
        ) from no_repair_was_named
