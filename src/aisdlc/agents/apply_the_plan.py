"""§10's implementation agent, all three of its responsibilities in one call.

`aisdlc-dev-impl` implements the approved plan, modifies the repository, and runs the tests.
The three are together because the suite has to run *around* the change: a run that wrote the
files and then asked somebody else to run the tests leaves a window in which the checkout can
change, and the answer would be about a repository this system did not produce.

**The container is the default runner**, so a caller who forgets anything gets a real
verification rather than none. A stub is a test's business and a test passes one deliberately.

**Nothing is rolled back when the suite goes red.** The change stays applied and the
verification says so, because the first question a person asks of a failing change is which
files it touched, and that question has no answer on a checkout somebody else put back.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

from aisdlc.agents.a_commit_recording_the_change import a_commit_recording_the_change
from aisdlc.agents.implement_the_plan import (
    FileToWrite,
    WhatTheImplementerConcluded,
    implement_the_plan,
)
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.verification_report import VerificationReport
from aisdlc.domain.repository import Repository
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.run_command import ACommand, the_outcome_of
from aisdlc.tools.run_tests import SuiteOutcome
from aisdlc.verify_the_change import (
    AnswerTheSuiteWithoutTheChange,
    RunTheSuite,
    refuse_a_change_nothing_observed,
    the_suite_in_a_container,
    verify_the_change,
)

# A git checkout of a file this run committed. Bounded, and bounded for the same reason every
# other command is: a run that hangs on its own undo is a run that never delivers.
A_MINUTE = 60.0


class TheImplementerWasNeverAskedError(Exception):
    """The rule is in `apply_and_verify`, and this is the only thing that may say it broke.

    The suite runs inside `changing`, so a verification with no implementer behind it is a
    suite that ran over whatever was already in the clone. A run like that reports green and
    leaves no sentence on the card explaining that nobody wrote anything.
    """


class ADeliveredChange(BaseModel):
    """What was written into the clone, and what the suite said about it.

    Two facts in one value because the graph writes them in the same step and there is nothing
    to be gained by separating them: a run has a change *and* a verification of it, or it has
    a change nobody checked.
    """

    written: list[FileToWrite] = []
    verification: VerificationReport
    what_the_implementer_said: str


def apply_and_verify(
    clone: ClonedRepository,
    repository: Repository,
    plan: ImplementationPlan,
    model: BaseChatModel,
    run_the_suite: RunTheSuite = the_suite_in_a_container,
) -> ADeliveredChange:
    """The change the plan asked for, verified, and the two answers a person needs about it."""
    written: list[FileToWrite] = []
    what_the_implementer_concluded: WhatTheImplementerConcluded | None = None

    def changing() -> None:
        nonlocal what_the_implementer_concluded
        the_answer = implement_the_plan(clone, plan, model)
        what_the_implementer_concluded = the_answer
        written.extend(the_answer.files)
        a_commit_recording_the_change(
            clone.path,
            plan,
            f"{plan.files_to_change[0] if plan.files_to_change else 'The change'}"
            f" — {len(written)} file(s) the approved plan named",
        )

    # **The approved plan is the only thing here that knows which of these files are tests.**
    # `files_to_change` and `tests_to_add` were separated for exactly this reason, and a
    # caller that had to guess which of a change's files are tests would be guessing about a
    # repository's conventions from a file that has never read them.
    verification = verify_the_change(
        clone,
        repository,
        changing,
        run_the_suite,
        the_tests_the_plan_named=plan.tests_to_add,
    )
    # **The third suite run, and it is here rather than inside the verification because this is
    # the only place that knows how to put the change back.** The verification function was one
    # argument short of able to ask, and this node has everything the question needs: the plan
    # that says which files the change touched, the commit it made, and a suite runner. So the
    # answer is built here and the rule is handed one call.
    refuse_a_change_nothing_observed(
        verification,
        plan.tests_to_add,
        _the_suite_with_the_change_put_back(
            clone, repository, plan, run_the_suite
        ),
    )
    if what_the_implementer_concluded is None:
        raise TheImplementerWasNeverAskedError(
            "the change was applied and the suite was run, and the implementer was never "
            "asked what it concluded, so there is nothing for a reader to learn from the run "
            "besides the diff"
        )

    return ADeliveredChange(
        written=written,
        verification=verification,
        what_the_implementer_said=(
            what_the_implementer_concluded.judged.the_text_of_the_note_this_is()
        ),
    )


def _the_suite_with_the_change_put_back(
    clone: ClonedRepository,
    repository: Repository,
    plan: ImplementationPlan,
    run_the_suite: RunTheSuite,
) -> AnswerTheSuiteWithoutTheChange:
    """Put the change's own files back to what they were, run the suite, and put them again.

    **Only the files the plan named, and never the tests.** The tests are what the question is
    about -- a suite with the tests taken away says nothing either way -- and a test the plan adds
    did not exist before, so there is nothing to put back.

    **`HEAD~1`, and the change is put back afterwards however the run went.** The change is the
    most recent commit, so its parent holds the files as this repository had them -- the only
    version of "without the change" that means anything. **The putting back is in a `finally`
    because leaving the change undone would be worse than the bug this rule exists to catch**: the
    delivery that follows pushes this working tree, so an undone change that nobody restored is a
    pull request that silently drops the work.

    **A suite that cannot be run means the answer is no answer, not a green one.** A runner that
    raises has not said the change is unobserved; it has failed, and a rule that read a failure as
    a pass would be the worst kind of rule there is.
    """
    the_files_the_plan_changed = list(plan.files_to_change)

    def put_the_files_back_to(revision: str) -> None:
        if not the_files_the_plan_changed:
            return
        the_outcome_of(
            ACommand(
                program="git",
                arguments=["checkout", revision, "--", *the_files_the_plan_changed],
                seconds_it_may_take=A_MINUTE,
                working_directory=str(clone.path),
            )
        )

    def answering_without_the_change() -> SuiteOutcome:
        put_the_files_back_to("HEAD~1")
        try:
            return run_the_suite(clone, repository)
        finally:
            put_the_files_back_to("HEAD")

    return answering_without_the_change
