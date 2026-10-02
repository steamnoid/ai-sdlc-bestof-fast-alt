"""What a model may decide about a pull request GitHub will not merge, and the two answers it may.

**Two repairs, and each has to be something a run can actually take.** That is the whole reason
this is a closed set rather than an open question: a model offered a choice between an action
that works and one that does not is answering a coin, not making a decision, and §0.3 puts the
difference between the two exactly where it belongs — in what pytest asserts and what `evals/`
grades, never in prompt text.

**The answer is a name and no prose of its own.** The options are English sentences and they are
the only answers accepted, for the reason this repository has learned the hard way about prompts:
*a prompt that says do not do X is not a check that X did not happen.* So an answer outside the
set is refused by name, and **a decision with no reason behind it is refused too** — a verdict
with no grounds is a coin flip written down at the one place a coin flip is worst.

**Only the conflict a delivery can reach, and that is a decision rather than a narrowness.** A
sibling project carries three: a pull request that will not merge, an opportunity already filed as
somebody else's issue, and two runs having changed one file. **Two of the three do not exist here**
— the duplicate filing is refused by its own rule with nothing routing it, and a branch that moved
under a run has no refusal at all — so a set of three would be two answers with no caller, which is
the shape this repository deleted before as two tables built for a question the pipeline already
answers.

**Frozen and `extra="forbid"`, for the reason every answer type in this package is.** A fact this
system did not ask for is one no human was ever shown, and the set here is closed on purpose — a
model that returned a third field would be read as an artifact with two.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class WhatToDoWhenThePullRequestWillNotMerge(StrEnum):
    """The two repairs for a pull request that will not merge, and no third.

    **Both of these are operations this repository has.** The first is
    `rebase_the_branch_a_run_pushed`, and for a while the set named a rebase there was no tool
    for — a model offered a choice between an action that could be taken and one that could not is
    a coin rather than a decision, and the whole set exists to be the opposite of that.
    """

    REBASE_IT_AND_TRY_AGAIN = "rebase it and try again"
    LEAVE_IT_OPEN_AND_SAY_WHY = "leave it open and say why"


class WhatToDoAroundAConflict(BaseModel):
    """One repair and the grounds for it, and nothing a run may act on without both.

    **`why` is required and may not be blank, and the requirement is the point.** Every other
    verdict in this package carries its grounds for the same reason: `ApprovalDecision.reason` is
    required for the same reason and says so in its own words. An optional reason is two standards
    of evidence in the same table — a person might skip it and a model would never — and this is
    where a model's grounds are read by whoever reads the card afterwards.

    **The set, not a string.** `the_repair` holds a member of the enumeration rather than the text
    a model wrote, so nothing downstream can be exhaustive about a value it never saw validated.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    the_repair: WhatToDoWhenThePullRequestWillNotMerge
    why: str = Field(min_length=1)


class AnAnswerThatIsNotADecisionError(Exception):
    """A model named no repair, or named one and said nothing for it.

    **Both halves are the same fault and one refusal, because both mean the same thing.** A model
    whose answer cannot be expressed **has said nothing**, and a run that received nothing must
    not route on it — a node that read a blank answer as a verdict would be deciding for the model
    while looking as though the model had decided.

    **The answer travels in the message, verbatim.** A refusal that says only that the answer was
    unusable leaves the reader to go and find what the model said, and what it said is the only
    evidence that the question needed rewriting rather than the model needing another try.
    """


def the_question_about_a_conflict_in_these_words(the_conflict_as_it_was_refused: str) -> str:
    """The question, carrying the refusal whole, and naming both repairs by their exact text.

    **The refusal travels in and not a summary of it.** Whoever refused read the facts from GitHub,
    so a decision made on a restatement of them would be a decision about this sentence rather than
    about the pull request.

    **Both repairs are printed rather than described.** A set the model has to have read to act on
    is a set the model is guessing at otherwise, and the names here are the strings
    `WhatToDoWhenThePullRequestWillNotMerge` validates — so what is printed and what is accepted are
    the same list by construction and not by agreement.
    """
    what_there_is = "\n".join(
        f"- {a_repair.value}" for a_repair in WhatToDoWhenThePullRequestWillNotMerge
    )

    return (
        f"A delivery this system made cannot be merged, and here is what GitHub said:\n\n"
        f"{the_conflict_as_it_was_refused}\n\n"
        f"Name the one repair to take. These are the only two answers, and both of them are "
        f"operations this run can carry out:\n\n{what_there_is}\n\n"
        f"Answer with one of those sentences, and then say why that one and not the other."
    )
