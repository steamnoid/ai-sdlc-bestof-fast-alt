"""That a plan's change being nothing is refused at the writing, not three stages later.

**A real run delivered a test and nothing else, and was recorded as having applied its plan.**
The log holds the whole shape of it:

```text
files_to_change=['package.json']
files_to_add=[]
tests_to_add=['tests/unit/aisdlc-a-real-run-wrote-this.test.ts']
1 file changed, 29 insertions(+)
```

The implementer *answered* with `package.json` - so `PlannedFileNotWrittenError`, which demands
every path the plan names, saw nothing wrong. **But it wrote it byte-identically.** And the rule
that guards that only fires when *every* file is unchanged, which the new test made false.

**So one new test was enough for a plan that lost its whole substantive change to be recorded as
applied**, and the run carried on to verify it, deliver it, and push it.

**The existing rule is right and this does not undo it.** Its own docstring defends it: *a plan
naming four files where one was already right changed three, and refusing it would punish an
implementer for being thorough.* That is a real argument about a real case. **Here the one
unchanged file was the whole of `files_to_change`, and the only thing that moved was a test** -
so the thing the plan was commissioned to do is not in the run.

**And the rule belongs at the writing, which is the last moment the fact costs nothing.** Every
later place it could live is worse: the commit stage sees a change that exists, the suite stage
has already spent a container, and `apply_and_verify` only found it by comparing two checkouts
that `git` had let it believe were the same.

**The fake model answers `FileToWrite` objects, so the answer is accepted first time.** This is
plumbing under the rule that reasoning quality is owned by a grader and never by pytest; what
pytest owns here is which files count as the change, and that is a statement about this
function's shape.

**Real files in a real clone, and not a list, because the fact being judged is a fact about the
disk.** Asserting on a list of paths would assert on the input rather than on what was refused.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aisdlc.agents.implement_the_plan import (
    AWriteThatChangesNothingError,
    FileToWrite,
    implement_the_plan,
)
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.what_an_agent_judged import WhatAnAgentJudged
from aisdlc.tools.github_clone_repository import ClonedRepository

THE_FILE_THE_PLAN_NAMED = "package.json"
WHAT_IT_ALREADY_HOLDS = '{"name": "wellbeing-tracker"}\n'
THE_TEST_THE_PLAN_ADDED = "tests/unit/a-real-run-wrote-this.test.ts"


class _AModelThatAnswers:
    """A model whose answer is already decided, and hands it over unchanged.

    **LangChain's two entry points and nothing else.** `with_structured_output` returns the model
    itself, because the answers are `FileToWrite` objects already and there is nothing to parse.
    """

    def __init__(self, what_it_answers: list[FileToWrite]) -> None:
        self._what_it_answers = what_it_answers
        self.what_it_was_asked: list[str] = []

    def with_structured_output(self, *arguments: object, **keywords: object) -> object:
        """LangChain's entry point, and the answers are already decided, so this is the model."""
        return self

    def invoke(self, the_question: str) -> object:
        """Hand back the whole answer, so this stage is asked once and nothing else happens."""
        self.what_it_was_asked.append(the_question)
        return {
            "files": self._what_it_answers,
            "judged": WhatAnAgentJudged(
                what_it_found="the plan's file already held the content proposed for it",
                what_it_could_not_settle="why the plan asked for what was already there",
                what_it_expects_next="the plan, or a file that is not yet right",
            ),
        }


def _a_clone_holding_the_file_as_it_already_is(where: Path) -> ClonedRepository:
    """A real directory holding `package.json`, because that is where the comparison happens."""
    where.mkdir(parents=True, exist_ok=True)
    (where / THE_FILE_THE_PLAN_NAMED).write_text(WHAT_IT_ALREADY_HOLDS)
    return ClonedRepository(path=where, ref="main", commit="a-commit")


def _the_plan_from_the_log() -> ImplementationPlan:
    """One file to change and one test to add, which is what the real run's plan held."""
    return ImplementationPlan(
        files_to_change=[THE_FILE_THE_PLAN_NAMED],
        tests_to_add=[THE_TEST_THE_PLAN_ADDED],
    )


def _the_answer_the_implementer_gave() -> list[FileToWrite]:
    """Both files answered for, with `package.json` reproduced byte for byte.

    **The answer has to include the unchanged file**, because that is the case. The implementer was
    asked for the plan's file and returned it, so a refusal here is about *the content* and not
    about an omission a different rule already owns.
    """
    return [
        FileToWrite(path=THE_FILE_THE_PLAN_NAMED, content=WHAT_IT_ALREADY_HOLDS),
        FileToWrite(path=THE_TEST_THE_PLAN_ADDED, content="it('was here', () => {})\n"),
    ]


def test_a_plan_whose_whole_change_is_a_test_is_refused_at_the_writing(tmp_path: Path) -> None:
    """The test moved and the plan's file did not, so nothing the plan was for has happened.

    **This is the pair of facts the current rule cannot see.** One file moved and one did not, so
    `AWriteThatChangesNothingError` does not fire - and yet the file that did not move is the whole
    of `files_to_change`, which is the change the plan was commissioned to make.
    """
    the_clone = _a_clone_holding_the_file_as_it_already_is(tmp_path / "the-clone")

    with pytest.raises(AWriteThatChangesNothingError) as it_raised:
        implement_the_plan(
            the_clone,
            _the_plan_from_the_log(),
            _AModelThatAnswers(_the_answer_the_implementer_gave()),  # type: ignore[arg-type]
        )

    the_refusal = str(it_raised.value)

    assert THE_FILE_THE_PLAN_NAMED in the_refusal, (
        f"the refusal does not name {THE_FILE_THE_PLAN_NAMED!r}, which is the file the plan named "
        f"to change and which the clone already held. It says: {the_refusal}"
    )
    assert THE_TEST_THE_PLAN_ADDED not in the_refusal, (
        f"the refusal names {THE_TEST_THE_PLAN_ADDED!r}, which the plan asked for and which was "
        "written as asked. It is not what went wrong: what went wrong is that the file the plan "
        "named to change was written unchanged, and a refusal naming the test sends the reader to "
        f"the one file that was fine. It says: {the_refusal}"
    )
