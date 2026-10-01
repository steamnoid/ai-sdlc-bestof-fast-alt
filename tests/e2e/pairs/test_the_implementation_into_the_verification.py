"""The implementation agent's real change, verified — the last pair in the pipeline, and the seam
that writes.

**This is a true seam, and the direction of the handover is the whole of it.** `implement_the_plan`
is handed an `ImplementationPlan` and writes the files that plan names; `verify_the_change` is
handed that same clone and a function to call, and the suite has to run *around* the change rather
than after it. So the upstream stage's conclusion is genuinely the next stage's input, and
`test_the_plan_into_the_implementation.py` beside this file cannot see this one at all: it proves a
real planner's plan can be applied, and it never asks whether **what the implementer really wrote is
what the verification was actually asked about**. A change written from a plan nobody approved, or
written somewhere the suite will not look, is a delivery whose every record upstream of it still
reads as complete — and the two isolation files, each holding half the pair, would both stay green
through it.

**`implement_the_plan` writes, so this pair is given `a_clone_this_run_may_write` and never the
shared clone.** Every other stage in this tier reads, and a change left in the shared clone would be
there for the next module to find — so an assertion about *when* something was on the disk could
pass for the wrong reason. That is the same shape as a test that cannot fail, and it is the reason
the ordering below is a fact about this directory rather than about the other one.

**The plan is written by hand, and that is scaffolding rather than a shortcut.** The handover under
test is the one after the plan, and `test_plan_the_change.py` states the case against chaining a
real planner into a file whose job is to isolate one: all a real planner would change here is which
path got named. **A path is read off the checkout rather than written into this file**, because no
test in this repository can know what a repository it has never read holds — the file to change is
the first one of a short list that this clone really has and is small enough to hand back whole, and
the test to add goes in the directory the clone demonstrably keeps tests in. Those two helpers are
written out rather than imported from `test_implement_the_plan.py`, for the reason
`test_the_requirements_into_the_qa_plan.py` gives: importing one real file's helper into another
makes the two agree by construction, and a helper that lost a piece would take the assertion meant
to notice it along.

**The suite is run by a recorder here, and not by the container, and the reason is what this file
is about.** What a verification is *handed* is a question about the handover, and a container
running `npm ci` and vitest answers a different one — `tests/integration/` and the whole-run e2e
already prove a repository's own code runs in a container on both sides of a change, and spending
that again here would buy no seam. **So the recorder never reports green, and that is the honest
answer rather than a compromise.** A `SuiteOutcome` carrying `passed=False` and
`dependencies_installed=False` is exactly what a suite that did not run should say, and a recorder
that reported green would be the one lie this pipeline cannot afford: a report that a change was
verified by tests that never executed looks identical, from every signal this system has, to a
report that a change was verified. The cost of that honesty is stated in the tests rather than
hidden: **`verify_the_change` therefore never called `the_tests_the_suite_never_ran` on this run**,
because that call sits behind `after.passed`, and this recorder is not allowed to claim a pass.

**The two calls below are the two calls `apply_and_verify` makes, in the same order, and two things
that node does are left out.** It commits the change, and it asks whether anything observed the
change by putting it back and running the suite a third time. **That third question's semantics are
already proved in the default suite** — `tests/test_whether_anything_observed_the_change.py` pins
`refuse_a_change_nothing_observed` including the gap it documents — so a real-model file that
asserted them again would be paying minutes for a fact a five-second test already settles, and §0.3
puts what is left to `evals/`.

**What this file therefore does not prove.** It does not prove the repository's own suite ran, in a
container or anywhere; it does not prove `AnUnrunTestError` fires for a real runner, or that the
change was observed by anything; and it does not prove a commit exists. It proves that the change
the implementer really made is on the disk between the two moments the verification was asked
about, and that the report a gate will present holds the two answers from those two moments.

The provider is a parameter rather than a constant, so proving a second one is a different run and
not a rewritten test. A provider the deployment is not configured for says so out loud.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import pytest

from aisdlc.agents.implement_the_plan import (
    AWriteThatChangesNothingError,
    FileToWrite,
    WhatTheImplementerConcluded,
    implement_the_plan,
    the_paths_the_plan_names,
)
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.verification_report import VerificationReport
from aisdlc.domain.commissioned_request import CommissionedRequest
from aisdlc.domain.repository import Repository
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE
from aisdlc.tools.run_tests import SuiteOutcome
from aisdlc.verify_the_change import (
    the_tests_the_suite_never_ran,
    verify_the_change,
)

pytestmark = pytest.mark.e2e

JUDGEMENTS_THE_IMPLEMENTER_MAKES = (
    "what_it_found",
    "what_it_could_not_settle",
    "what_it_expects_next",
)
"""**The three fields' own names, and the spelling is the one the type actually has.**

`WhatAnAgentJudged` is one type asked in six places, and each caller lists the three names itself
rather than asking the type — so a name that stopped being a field fails here with the sentence a
reader needs, rather than with a bare `AttributeError` out of a loop over a tuple. Two constants in
this tier carry `what_it_expectes_next`, which is not a field; `plan_the_change` uses its copy in a
prompt and the pair files reach theirs by `getattr`. A reader who copies one of them gets a mistake
that only shows up on a paid run, which is why the spelling is stated here rather than trusted.
"""

# **The files a plan here may change, in the order a repository is most likely to have them.** A
# document a person reads first, and then the manifest every build is defined by. Neither is
# hard-coded as *the* file: the first one this clone really holds is the one the plan names, and a
# repository with neither says so out loud rather than getting a file invented for it.
FILES_A_PLAN_MAY_CHANGE_FIRST = (
    "README.md",
    "README.rst",
    "README.txt",
    "README",
    "package.json",
)

# **A file has to be small enough to hand back whole, because that is what is asked for.** The
# implementer is given the complete text a file should end up holding, so a lockfile would be a
# truncation this file could not tell apart from a model that decided to shorten it.
THE_LONGEST_A_FILE_MAY_BE_BEFORE_IT_IS_HANDED_BACK_WHOLE = 8_000

# The name this file gives the test the plan adds. It says what the file is for — a test this pair's
# verification is asked about — rather than what it asserts, because a plan carries paths and no
# intent, and a name claiming an assertion nobody approved would be a second invention.
THE_NAME_OF_THE_TEST_THIS_PAIR_VERIFIES = "aisdlc-this-pair-verifies-a-real-change"

A_SUITE_THAT_WAS_NEVER_EXECUTED_REPORTS = 127
"""**The code a suite that did not run reports, and it is deliberately not zero and not one.**

Zero is a pass and one is a red suite that ran and failed, and this recorder is neither. A person
reading a `VerificationReport` cannot tell the two apart from `passed` alone, and `exit_code` is
the second field in front of them — so it carries a code of its own rather than borrowing a
meaning that is already taken.
"""


class WhatTheSuiteWasAskedAt(NamedTuple):
    """One instant the suite was asked to run at, and the two things that are true only there."""

    the_clone_it_held: dict[str, str | None]
    the_outcome_it_answered: SuiteOutcome


class WhatThePairWasHanded(NamedTuple):
    """The plan, the change the implementer made, and the instants the verification was asked at."""

    the_plan: ImplementationPlan
    the_tests_the_verification_was_handed: list[str]
    what_the_implementer_concluded: WhatTheImplementerConcluded
    the_verification: VerificationReport
    what_the_suite_was_asked: list[WhatTheSuiteWasAskedAt]

    @property
    def every_write(self) -> list[FileToWrite]:
        """The files the implementer said it wrote, which is what a reader of the plan approved."""
        return self.what_the_implementer_concluded.files


def _the_file_this_plan_will_change(clone: ClonedRepository) -> str:
    """The first file of that list this clone really holds, or a loud reason there is none."""
    for a_name in FILES_A_PLAN_MAY_CHANGE_FIRST:
        where = clone.path / a_name
        if not where.is_file():
            continue
        if where.stat().st_size > THE_LONGEST_A_FILE_MAY_BE_BEFORE_IT_IS_HANDED_BACK_WHOLE:
            continue
        return a_name

    pytest.skip(
        f"this clone holds none of {', '.join(FILES_A_PLAN_MAY_CHANGE_FIRST)} at or under "
        f"{THE_LONGEST_A_FILE_MAY_BE_BEFORE_IT_IS_HANDED_BACK_WHOLE} characters, so there is no "
        "file for a plan to change that a model could be asked to hand back whole. This tier does "
        "not invent one: a change to a file the repository does not have is the case the planner "
        "refuses, and refusing it here is the same rule."
    )


def _where_this_repository_keeps_its_tests(clone: ClonedRepository) -> tuple[str, str]:
    """Where this clone keeps the most tests of its own, and how a test is named in that directory.

    **The most tests and not the first one found.** A walk in filesystem order would name a
    different directory on a different machine and after a different clone, and the plan this file
    builds has to be the same plan every time — two runs of one work item are compared against each
    other in a real pipeline.

    **Only what is directly in the directory counts, and never anything below it.** `tests/` is the
    case that makes the rule: it holds none of them and holds two directories full of them, so a
    recursive search says yes for it — and a directory holding a test is a directory this
    repository demonstrably runs tests from, where one holding none may be collected and may not.
    Somebody else's code is skipped by the same list the inspection skips, read from the module that
    decides what a model is shown.

    **The suffix is read from a test already there rather than guessed.** A repository naming its
    tests `*.spec.ts` and one naming them `*.test.ts` both collect, and a name invented here would
    put a file into a tier the runner does not run. `test_implement_the_plan.py` argues this at
    length; the argument is not repeated here because the rule is the same one, not a second one.
    """
    how_many_tests_each_directory_holds: dict[str, list[Path]] = {}

    for a_directory in clone.path.rglob("*"):
        if not a_directory.is_dir():
            continue
        its_parts = a_directory.relative_to(clone.path).parts
        if any(a_part in DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE for a_part in its_parts):
            continue
        the_tests_directly_in_it = [
            a_file
            for a_file in sorted(a_directory.iterdir())
            if a_file.is_file() and (".test." in a_file.name or ".spec." in a_file.name)
        ]
        if the_tests_directly_in_it:
            how_many_tests_each_directory_holds[str(a_directory.relative_to(clone.path))] = (
                the_tests_directly_in_it
            )

    if not how_many_tests_each_directory_holds:
        pytest.skip(
            "this clone keeps no test of its own anywhere, so there is no directory a new test can "
            "be put where this repository demonstrably runs tests from. A repository with no suite "
            "is a real thing, and this tier does not introduce the first test to anything — that "
            "is a decision about a repository, not about a model"
        )

    its_path = sorted(
        how_many_tests_each_directory_holds,
        key=lambda a_path: (-len(how_many_tests_each_directory_holds[a_path]), a_path),
    )[0]
    a_test_already_there = how_many_tests_each_directory_holds[its_path][0].name

    for a_marker in (".test.", ".spec."):
        if a_marker in a_test_already_there:
            return its_path, a_test_already_there[a_test_already_there.index(a_marker) :]

    pytest.skip(
        f"{its_path} holds {a_test_already_there}, whose name this file cannot read a convention "
        "out of. Rather than guess a suffix this repository does not use, it says so — a test "
        "named into a tier the runner does not collect is a file nobody opened"
    )


def _the_text_a_clone_holds_of(clone: ClonedRepository, a_path: str) -> str | None:
    """What one file of a clone held, or `None` because the clone does not hold it at all."""
    where = clone.path / a_path
    if not where.is_file():
        return None
    return where.read_text(encoding="utf-8", errors="replace")


def _what_a_recorder_has_to_say(what_the_clone_held: dict[str, str | None]) -> str:
    """The record, as text, and nothing claimed about a suite that was never executed.

    **One line per path and a count, and the text itself is kept out of it.** The text is recorded
    in the structure the assertions read, so an outcome carrying a whole manifest and a whole new
    test file would be a report nobody reads — and its only jobs are to say that nothing ran and to
    be visibly a different answer from the one at the other instant, which the counts do.

    **The path is followed by a colon and never by a space, and that half is load-bearing.**
    `the_tests_the_suite_never_ran` decides whether a runner ran a test by asking whether one of
    the suite's own lines ends in that test's path *or carries the path followed by a space* — so
    the obvious wording, `the/path held: …`, is read as a suite that ran the test. This recorder ran
    nothing, and none of its own lines may say otherwise. The first version of this file printed
    the whole text after the path and did exactly that, which is why the rule found nothing to
    complain about in a run that named no tests at all.
    """
    lines = [
        "This run did not execute the repository's suite. It recorded what the approved plan's "
        "paths held at the instant the suite was asked to run, and that is the whole of its answer."
    ]

    for a_path, its_text in what_the_clone_held.items():
        if its_text is None:
            lines.append(f"{a_path}: not a file of the clone")
            continue
        lines.append(f"{a_path}: {len(its_text)} characters")

    return "\n".join(lines)


def _a_recorder_of_what_the_clone_held_at_each_call(
    the_plan: ImplementationPlan,
) -> tuple[Callable[[ClonedRepository, Repository], SuiteOutcome], list[WhatTheSuiteWasAskedAt]]:
    """The callable `verify_the_change` runs the suite with, and the list it writes to.

    **Every path the approved plan accounts for, and all three of its lists.** That is imported
    rather than spelled out, which is the opposite of the choice the two helpers above make and for
    the opposite reason: this recorder decides *what it watches*, and the module that owns "every
    path the approved plan accounts for" is the one place that knows about `files_to_change`,
    `files_to_add` and `tests_to_add` together. A recorder watching only `files_to_change` would
    report an unchanged clone for a change whose whole content is a new test — which is the exact
    failure `implement_the_plan`'s own docstring records, and a check that could not hear it would
    be no check at all.

    **A list rather than a count, because the ordering is the property.** `verify_the_change` runs
    the suite, then applies the change, then runs it again, and there is no way to catch a swap from
    outside the function. What the list holds is therefore a fact *about an instant* rather than an
    answer compared afterwards, and that is the only thing that makes "the change was on the disk
    when the second run was asked for" an observation rather than a reconstruction.
    """
    what_the_suite_was_asked: list[WhatTheSuiteWasAskedAt] = []

    def the_suite_is_run(clone: ClonedRepository, _repository: Repository) -> SuiteOutcome:
        what_the_clone_held_at_this_instant = {
            a_path: _the_text_a_clone_holds_of(clone, a_path)
            for a_path in the_paths_the_plan_names(the_plan)
        }
        the_answer = SuiteOutcome(
            exit_code=A_SUITE_THAT_WAS_NEVER_EXECUTED_REPORTS,
            passed=False,
            dependencies_installed=False,
            output=_what_a_recorder_has_to_say(what_the_clone_held_at_this_instant),
        )
        what_the_suite_was_asked.append(
            WhatTheSuiteWasAskedAt(
                the_clone_it_held=what_the_clone_held_at_this_instant,
                the_outcome_it_answered=the_answer,
            )
        )
        return the_answer

    return the_suite_is_run, what_the_suite_was_asked


@pytest.fixture(scope="module")
def what_the_pair_was_handed(
    the_repository: Repository,
    a_clone_this_run_may_write: ClonedRepository,
    a_request: CommissionedRequest,
    the_model_for,
    request,
) -> WhatThePairWasHanded:
    """One real implementation and one real verification, with the suite asked in between.

    **The change is applied by `verify_the_change` and not before it.** The function takes the
    change as a callable precisely so the ordering can only be honoured by doing the work in the
    middle, and a fixture that called `implement_the_plan` itself would have applied the change
    before either run and made every assertion below a comparison of two identical instants. So the
    implementer runs inside `what_the_change_does`, which is where `apply_and_verify` puts it too.

    **`the_tests_the_plan_named` is `the_plan.tests_to_add`, which is what `apply_and_verify`
    passes.** Nothing here guesses which of a change's files are tests: the plan separates the two
    lists exactly so that a caller never has to work it out from a repository's conventions.

    **`a_request` is taken and not read, and that is what keeps this file honest on a deployment
    with no sentence.** The plan below is written by hand about the request this deployment states,
    so without one there is nothing for it to be a plan *of* — and `a_request` skips with that
    reason printed rather than leaving a run about a repository and nothing else.

    **A change that writes nothing is skipped with the refusal printed.** `implement_the_plan`
    refuses it at the writing, where the fact is still knowable, and it fires only after this
    deployment's correction budget is spent — so it is slow, and it is about something upstream of
    the seam this file measures.
    """
    the_model = the_model_for(request.param)
    del a_request

    the_file_to_change = _the_file_this_plan_will_change(a_clone_this_run_may_write)
    its_directory, how_a_test_is_named = _where_this_repository_keeps_its_tests(
        a_clone_this_run_may_write
    )
    the_plan = ImplementationPlan(
        files_to_change=[the_file_to_change],
        tests_to_add=[
            f"{its_directory}/{THE_NAME_OF_THE_TEST_THIS_PAIR_VERIFIES}{how_a_test_is_named}"
        ],
    )

    what_the_implementer_concluded: list[WhatTheImplementerConcluded] = []

    def the_change_this_run_makes() -> None:
        try:
            what_the_implementer_concluded.append(
                implement_the_plan(a_clone_this_run_may_write, the_plan, the_model)
            )
        except AWriteThatChangesNothingError as refused:
            pytest.skip(
                f"a real implementation agent, given a plan naming "
                f"{the_paths_the_plan_names(the_plan)} and this checkout, proposed exactly the "
                f"text every one of those files already held, and the change was refused at the "
                f"writing where the fact is still knowable. {str(refused).strip()}\n\nThat is a "
                f"fact about this repository and this deployment's model, and it is decided before "
                f"the seam this file measures begins."
            )

    the_suite_is_run, what_the_suite_was_asked = _a_recorder_of_what_the_clone_held_at_each_call(
        the_plan
    )

    the_verification = verify_the_change(
        a_clone_this_run_may_write,
        the_repository,
        the_change_this_run_makes,
        run_the_suite=the_suite_is_run,
        the_tests_the_plan_named=the_plan.tests_to_add,
    )

    if not what_the_implementer_concluded:
        pytest.fail(
            "the suite was asked to run twice, the change was applied in between them, and no "
            "implementer's answer came back. A verification with nobody behind it is a suite that "
            "ran over whatever was already in the clone, and a report that cannot say so looks "
            "exactly like one that can."
        )

    return WhatThePairWasHanded(
        the_plan=the_plan,
        the_tests_the_verification_was_handed=list(the_plan.tests_to_add),
        what_the_implementer_concluded=what_the_implementer_concluded[0],
        the_verification=the_verification,
        what_the_suite_was_asked=what_the_suite_was_asked,
    )


@pytest.mark.parametrize("what_the_pair_was_handed", list(LlmProvider), indirect=True)
def test_the_suite_was_asked_twice_and_the_report_holds_two_answers_not_one(
    what_the_pair_was_handed: WhatThePairWasHanded,
) -> None:
    """Two calls happened, the report holds one real outcome per call, and they are not one.

    **The count is the non-vacuous half.** Everything else in this file reads the two answers, and
    an implementation that called the suite once and copied the answer into both fields would leave
    every other assertion here true. The recorder appends one entry per call, so its length is the
    number of real calls and nothing else.

    **Identity rather than equality, then equality.** The report holding *the recorder's own second
    value* is what makes "the report's after-outcome" a fact about that instant; the two values
    also being unequal is a consequence of the clone having changed, which the next test shows
    directly rather than leaving it as a difference nobody can account for.
    """
    the_verification = what_the_pair_was_handed.the_verification
    what_the_suite_was_asked = what_the_pair_was_handed.what_the_suite_was_asked

    assert len(what_the_suite_was_asked) == 2, (
        f"the suite was asked to run {len(what_the_suite_was_asked)} time(s) and the report holds "
        f"two outcomes. `verify_the_change` runs it, applies the change and runs it again, so a "
        f"number other than two means the ordering this module exists to check is not what "
        f"happened — and a report built over one run is a report about a repository this run never "
        f"measured twice"
    )

    for a_side in ("suite_before_the_change", "suite_after_the_change"):
        the_outcome = getattr(the_verification, a_side)
        assert isinstance(the_outcome, SuiteOutcome), (
            f"{a_side} holds {type(the_outcome).__name__} rather than the outcome a suite returns, "
            "so a reader of this report cannot tell an install that failed from a suite that ran "
            "and failed — which is the whole of what `SuiteOutcome.dependencies_installed` is for"
        )

    assert (
        the_verification.suite_before_the_change
        is what_the_suite_was_asked[0].the_outcome_it_answered
    ), (
        "the report's before-outcome is not the value the first run answered with, so the report "
        "is not holding what happened at that instant — and a report that paraphrases a run is a "
        "report a person cannot check against the clone it claims to describe"
    )
    assert (
        the_verification.suite_after_the_change
        is what_the_suite_was_asked[1].the_outcome_it_answered
    ), (
        "the report's after-outcome is not the value the second run answered with, so the pair of "
        "outcomes the gate will present is not the pair of instants this run measured"
    )

    assert the_verification.suite_before_the_change != the_verification.suite_after_the_change, (
        "the two outcomes are equal, so this run's report says the same thing twice and calls it "
        "before-and-after. A reader of that report is being shown one fact dressed as two, and the "
        "clone did change in between — the next test is where that is shown"
    )


@pytest.mark.parametrize("what_the_pair_was_handed", list(LlmProvider), indirect=True)
def test_the_change_was_on_the_disk_at_the_moment_the_suite_was_asked_the_second_time(
    what_the_pair_was_handed: WhatThePairWasHanded,
) -> None:
    """At the first instant the change was not there; at the second, every file of it was.

    **Read out of what the recorder caught, and not out of the clone afterwards.** A file read after
    `verify_the_change` returns cannot say *when* it was written, and "when" is the entire claim:
    the suite has to run on both sides of the change, and a change already applied before the first
    run would give a report whose two numbers are the same number twice. The recorder took a
    reading at each call, so this is a fact observed while it was true rather than a reconstruction
    of a tree that has since been written to.

    **Every path the plan accounts for, in the second reading, is the text the implementer proposed
    for it** — not merely *a* file at that path, and not merely different from what was there. The
    implementer is asked for the whole text a file should end up holding, so holding exactly that is
    the whole contract of the writing, and this is the one comparison an answer that was well formed
    and never applied cannot pass.

    **The first and second readings differ, and the path that proves it is the test the plan
    added.** `tests_to_add` names files that do not exist yet, so that path is not a file of the
    clone at the first instant by construction and a file's text at the second — and it is the path
    a recorder watching only `files_to_change` would have missed, which is the bug this recorder's
    own docstring says it is here to avoid.
    """
    the_plan = what_the_pair_was_handed.the_plan
    every_write = what_the_pair_was_handed.every_write
    what_the_suite_was_asked = what_the_pair_was_handed.what_the_suite_was_asked

    assert every_write, (
        f"the implementation agent answered with no file against a plan naming "
        f"{the_paths_the_plan_names(the_plan)}, so there is no change to have been on the disk and "
        f"every assertion below would be true of nothing having been written"
    )

    at_the_first_instant = what_the_suite_was_asked[0].the_clone_it_held
    at_the_second_instant = what_the_suite_was_asked[1].the_clone_it_held

    for one_write in every_write:
        assert at_the_second_instant[one_write.path] == one_write.content, (
            f"{one_write.path!r} does not hold the text the implementer proposed for it at the "
            f"moment the suite was asked to run the second time. It holds "
            f"{at_the_second_instant[one_write.path]!r}. The stage is asked for the whole text of "
            f"a file rather than a diff, so a file holding something else is one written from a "
            f"different answer — and the verification this run is about would be a report about a "
            f"repository that is not the one the change produced"
        )

    for a_test_the_plan_added in the_plan.tests_to_add:
        assert at_the_first_instant[a_test_the_plan_added] is None, (
            f"{a_test_the_plan_added!r} is in the plan's tests_to_add and the clone already held "
            f"it when the suite was asked to run the first time. That list is for tests that do "
            f"not exist yet, so the plan is describing a file it is also changing in place — or "
            f"the name this file invented has collided with a test the repository already had"
        )

    assert at_the_first_instant != at_the_second_instant, (
        "the two readings of the clone are identical, so nothing about the repository differed "
        "between the two moments the suite was asked about and this run's report is a report about "
        "one instant described twice"
    )


@pytest.mark.parametrize("what_the_pair_was_handed", list(LlmProvider), indirect=True)
def test_the_report_says_no_suite_ran_and_the_plans_tests_reached_the_rule_that_asks(
    what_the_pair_was_handed: WhatThePairWasHanded,
) -> None:
    """The report says no suite ran, and the rule about unrun tests names the plan's own tests.

    **The honest half first, and it is the reason for the recorder.** `passed` and
    `dependencies_installed` are both false, so the report a gate will present cannot be read as a
    repository whose tests ran. A recorder reporting green would produce a `VerificationReport`
    that is indistinguishable, from every field a reader has, from one backed by a real suite — and
    that is the lie this pipeline is built not to tell.

    **And because it is not green, `verify_the_change` never asked `the_tests_the_suite_never_ran`
    on this run.** That call sits behind `after.passed`, so this file does not prove the refusal
    fires for a real runner, and saying so is part of the claim rather than a footnote. What it
    proves instead is that the two inputs the rule is about were handed over: the list carries every
    test the approved plan said the change adds, and the report holds the very outcome the second
    run answered with — so the rule, given this report and this plan, compares what the second
    instant actually held.

    **The non-empty guard is first, and it is the assertion that could not hear.** Every test of a
    plan that names none is a test the rule names, and a list of zero would satisfy a check about
    which tests reached the rule more perfectly than a correct one.
    """
    the_verification = what_the_pair_was_handed.the_verification
    the_tests_that_reached_the_rule = what_the_pair_was_handed.the_tests_the_verification_was_handed

    assert not the_verification.suite_after_the_change.passed, (
        "the report says the suite passed after the change, and this run's suite runner did not "
        "execute anything — it recorded what the clone held. A report that claims a suite passed "
        "over a run that never happened is the one lie `SuiteOutcome.dependencies_installed` "
        "exists to keep out, and a person reading the report has no way to tell it from a real one"
    )
    assert not the_verification.suite_after_the_change.dependencies_installed, (
        "the report says the repository's dependencies were installed. Nothing installed anything, "
        "so a report that says they were is claiming that a suite ran which never did"
    )

    assert the_tests_that_reached_the_rule, (
        f"the verification was handed no test at all, and the plan names "
        f"{what_the_pair_was_handed.the_plan.tests_to_add}. `tests_to_add` is the field that says "
        "which of a change's files are tests, and a caller handing over an empty list hands the "
        "rule a question with no subject — which is why the count is asserted before the list"
    )

    not_accounted_for = [
        a_test_the_plan_added
        for a_test_the_plan_added in what_the_pair_was_handed.the_plan.tests_to_add
        if a_test_the_plan_added not in the_tests_that_reached_the_rule
    ]
    assert not not_accounted_for, (
        f"{not_accounted_for} is in the plan's tests_to_add and was not handed to the "
        "verification. `the_tests_the_suite_never_ran` is then unable to ask about a test nobody "
        "told it, and a rule handed a shorter list than the plan approved reports a cleaner change "
        "than the one that was made"
    )

    the_tests_the_runner_never_ran = the_tests_the_suite_never_ran(
        the_tests_that_reached_the_rule, the_verification.suite_after_the_change
    )
    assert the_tests_the_runner_never_ran == the_tests_that_reached_the_rule, (
        f"given the report's own after-outcome, the rule named {the_tests_the_runner_never_ran} "
        f"rather than every test the approved plan said the change adds "
        f"({the_tests_that_reached_the_rule}). That would be right and not a defect if this run's "
        f"runner had reported running some of them: it recorded a listing of the clone rather than "
        f"a report of tests, and it names no test at all, so every one of them is unrun. What this "
        f"asserts is that the rule was handed the report's own second answer *and* the plan's "
        f"list, because nothing else could produce this list and no other outcome was in the report"
    )


@pytest.mark.parametrize("what_the_pair_was_handed", list(LlmProvider), indirect=True)
def test_the_implementer_says_what_it_found_about_the_change_it_wrote(
    what_the_pair_was_handed: WhatThePairWasHanded,
    the_placeholders: frozenset[str],
) -> None:
    """The three sentences beside the change are filled, and none of them is a shape.

    **The guard is the change, not the sentences.** `WhatAnAgentJudged` refuses a blank at
    validation, so a blank cannot reach this assertion and saying otherwise would be claiming more
    than the code shows. What the sentences are *for* is the plan: a plan is a list of paths with no
    intent, so the sentence that catches an implementer inventing a mechanism nobody specified is
    the implementer's to write — and an implementer that wrote no file has written them about
    nothing, which reads in a card exactly like an implementer with nothing to report. So the
    first assertion is that files were written, and only then what was said about them.

    **Placeholders are refused and silence is not.** The system offers an agent with nothing to
    report two whole sentences to say so, and those are honest answers; what is refused is a field
    carrying the *shape* of an answer.
    """
    every_write = what_the_pair_was_handed.every_write
    what_the_implementer_concluded = what_the_pair_was_handed.what_the_implementer_concluded

    assert every_write, (
        f"the implementation agent wrote no file, so the three sentences beside it were written "
        f"about no change at all — and a note about nothing reads on a card as though there had "
        f"been a change to have an opinion about. The plan names "
        f"{the_paths_the_plan_names(what_the_pair_was_handed.the_plan)}"
    )

    for a_judgement in JUDGEMENTS_THE_IMPLEMENTER_MAKES:
        said = getattr(what_the_implementer_concluded.judged, a_judgement)
        assert said.strip(), (
            f"the implementation agent left {a_judgement} empty. It is the only agent that sees "
            f"the whole text of every file this change touches, so its doubt is the last place a "
            f"mechanism nobody approved can still be named — and an empty field reads as a doubt "
            f"nobody had"
        )
        assert said.strip().lower() not in the_placeholders, (
            f"{said!r} is placeholder text in {a_judgement}, which means the model returned a "
            f"shape rather than a judgement"
        )
