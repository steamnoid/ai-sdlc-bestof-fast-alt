"""The implementation stage whole: it writes the approved plan, records it, and runs the suite
around it.

**This is the only stage in this pipeline that writes to somebody else's repository and then
runs that repository's own code, and that is the whole reason it needs proving on its own.**
Every stage beside it produces a claim about a checkout, and a claim can be read afterwards and
checked against the thing it was about. A change cannot — it either is on the disk and in the
history or it is not. **So every assertion below is made against the files and against `git`,
and never against what this stage says it did.**

**The commit is asserted because a real run delivered nothing at all.** An earlier run wrote its
files, reported a plan, a verification and a suite green on both sides of the change, and pushed
a branch that pointed at the same commit as `main` — because nothing had committed anything.
GitHub's answer was `No commits between main and aisdlc/…`, forty-five minutes later, and
`git rev-parse HEAD` inside the clone was the only thing that would have shown it at the time.
A pull request whose diff is empty is the one thing this pipeline must never produce.

**The suite is not run for real here, and that is a decision rather than a shortcut.** The
container tier is where a repository's own code is executed, because it takes minutes and
because its answer depends on npm reaching a registry — so a file whose job is what this stage
*does with* an answer would be measuring npm rather than this stage. What is replaced is the
judge and nothing else: the suite is still asked before the change, after it, and once more
with the change put back, and every one of those answers is a real `SuiteOutcome`.

**And the suite that answers here is a witness rather than a judge, which is the only honest
thing a test can be.** It records the text every file the plan changes held at the moment it was
called, and which planned tests were on the disk, and it never looks at how many times it has
been called — so it is honest for one call or three. It answers green on every call, because a
witness that cannot run npm is not entitled to say a suite failed. **Which is why the third
question, when this stage puts it, is answered exactly as the first was, and that is the
finding `refuse_a_change_nothing_observed` exists for**: a suite that cannot tell a change from
no change has observed nothing. The rule's own semantics are proved in
`tests/test_whether_anything_observed_the_change.py`, so what is proved here is that this stage
asks the question at all, that the change really comes off the disk while it is asked, and that
it is put back afterwards.

**Two plans, and each answers a different question.** The first names one file this repository
really has, and the call returns a delivered change — which is where the four contracts of this
stage are asserted. The second names that file *and* a test, which is what puts the third
question, and the call is expected to be **refused**, because the recording suite cannot tell
the two checkouts apart and so nothing observed the change. A run that expects the refusal and
gets a delivery is a run whose test would pass for the wrong reason.

**Both plans are assembled from the checkout rather than written out here, because a file name
cannot be guessed.** The repository this tier is pointed at is stated in a deployment's own
`.env`, this repository has never read it, and a plan naming a file that is not there fails
inside the agent — leaving a green tick about nothing. The plan below is read off the clone, and
it is named as the stand-in for the plan a person would have approved.

**So this stage is handed `a_clone_this_run_may_write`, and never the shared clone.** Every other
file in this tier reads the read-only one, and a commit left there would be there for whatever
came next to find. The read-only clone is still used here, as the record of what the repository
was before this run touched anything.

**The provider is a parameter rather than a constant, so proving a second one is a different run
and not a rewritten test.** A provider the deployment is not configured for says so out loud
rather than passing quietly.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pytest
from pydantic import BaseModel

from aisdlc.agents.apply_the_plan import (
    ADeliveredChange,
    TheCommitHoldsNoneOfTheFilesThePlanNamedError,
    apply_and_verify,
)
from aisdlc.agents.implement_the_plan import (
    AWriteThatChangesNothingError,
    FileOutsideThePlanError,
    FileToWrite,
    PlannedFileNotWrittenError,
)
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.domain.repository import Repository
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE
from aisdlc.tools.run_command import ACommand, the_outcome_of
from aisdlc.tools.run_tests import SuiteOutcome
from aisdlc.verify_the_change import ATestThatPassesWithoutTheChangeError, RunTheSuite

pytestmark = pytest.mark.e2e

# What `WhatAnAgentJudged.the_text_of_the_note_this_is` calls its three sentences when it writes
# them out. **The labels rather than the field names, because the note is the text and the text
# says `what it found`.** A check that searched the note for `what_it_found` would be looking for
# a spelling the note never uses, and would fail on a note carrying all three of them.
JUDGEMENTS_THE_IMPLEMENTER_MAKES = (
    "what it found",
    "what it could not settle",
    "what it expects next",
)

# The three things a run records about the commit it made, written out rather than imported
# from the module that sets them. A commit naming a person for work a machine did is a forged
# trail, and it looks exactly like the real thing at the moment somebody has to tell them
# apart — which is the same reason an approval keeps `decided_by` verbatim. Importing the
# constants would make these assertions agree with the production code by construction, and an
# identity that moved with the code would move with the check that it is the agent's.
THE_AGENT_THAT_OWNS_THE_COMMIT = "aisdlc-dev-impl"
THE_ADDRESS_THE_COMMIT_CAN_BE_READ_FROM = "aisdlc@localhost"

# The files a change about what a repository states may go into, in the order a repository is
# most likely to hold them. A document a person reads first, then the manifest every build is
# defined by. **None of them is *the* file**: the first one this clone really holds is the one
# the plan names, and a repository holding none of them says so out loud rather than getting a
# file invented for it.
FILES_A_CHANGE_ABOUT_A_REPOSITORY_MAY_GO_INTO = (
    "README.md",
    "README.rst",
    "README.txt",
    "README",
    "CONTRIBUTING.md",
    "package.json",
    "tsconfig.json",
    "Dockerfile",
    ".dockerignore",
)

# A file has to be small enough to hand back whole, because that is what the implementer is
# asked for. It is given the complete text a file should end up holding, so a lockfile would be
# a truncation this file could not tell apart from a model that decided to shorten it.
THE_LONGEST_A_FILE_MAY_BE_BEFORE_IT_IS_HANDED_BACK_WHOLE = 8_000

# The name this test gives the test the second plan adds. It says what the file is rather than
# what it asserts, because the plan carries paths and no intent, and a name claiming an
# assertion nobody approved would be a second invention.
THE_NAME_OF_THE_TEST_THE_SECOND_PLAN_ADDS = "aisdlc-a-real-run-wrote-this"
A_MINUTE_OF_GIT = 60.0

REFUSALS_THAT_MEAN_THIS_RUN_DELIVERED_NOTHING = (
    ATestThatPassesWithoutTheChangeError,
    PlannedFileNotWrittenError,
    AWriteThatChangesNothingError,
    FileOutsideThePlanError,
    TheCommitHoldsNoneOfTheFilesThePlanNamedError,
)
"""The stages between the plan and the delivery, and every way each of them can stop — a list.

**A model is free to decline to write the file the plan named, and this deployment's does
roughly every other time.** That stops the run at `PlannedFileNotWrittenError`, which is the
implementer's rule firing correctly: *a plan that is not fully applied is not a plan that was
applied, and reporting it as applied is the one thing a traceability chain must never do.*

So the second plan in this file has **more than one** honest ending, and a fixture naming only one
of them fails on the others — with a message that reads as a defect in the system rather than
as a fixture that was too narrow. Every class here is a refusal of *this* run, from one of the
stages between the plan and the delivery, and a delivery is the one outcome not in the list.

**And this list has grown three times, each time by a rule that was correct when it was added.**
A rule added without adding itself here does not fail loudly — it fails as `ERROR at setup`, with
the fixture's own `pytest.raises` letting the refusal through, which is the one shape that reads
as *the system is broken* rather than *the list is short*. So a refusal added here is not finished
until it is in this tuple.

**The last one is why this note had to be rewritten rather than appended to.** It said *the two
ways each of them can stop*, which was already wrong at four classes and became more wrong at
five. A count written in prose is a number nothing checks, and this repository has been bitten by
one of those before.
"""


class WhatTheSuiteWasHanded(BaseModel):
    """One run of the suite, and the checkout it was handed as it stood at that moment.

    **The text and not a verdict, because the double in this file is a witness rather than a
    judge.** What a suite said about a checkout is not knowable without running that checkout's
    own toolchain, so what is kept is the checkout — and every assertion that the suite ran
    before and after the change is read off the difference between two of these, which is a
    fact about a disk rather than a counter a test incremented.
    """

    the_text_each_file_the_plan_changes_held: dict[str, str]
    which_planned_tests_were_on_the_disk: list[str]
    what_it_reported: str

    def what_a_run_of_the_suite_could_have_seen(self) -> tuple[object, ...]:
        """Everything about that checkout a suite could distinguish, as one comparable value.

        **Both halves, and the first version of this compared only the first.** A plan whose
        whole change is a new test file — which is what the second plan in this file is, and what
        a test-only plan is in any repository — leaves `files_to_change` untouched. So comparing
        the texts alone says two different checkouts are identical, the assertion below it fails,
        and the failure reads as *the run behaved correctly and the test is wrong about it*,
        which is what happened on three consecutive runs of this file.

        Which is the trap this method exists to close: **a comparison of one field of a state is
        a claim about that field.** Whether two checkouts differ is a claim about the checkout,
        and the checkout is a file's text *and* which files are there at all. A test that
        observes one of those can be right and still answer wrongly.
        """
        return (
            self.the_text_each_file_the_plan_changes_held,
            tuple(self.which_planned_tests_were_on_the_disk),
        )


class ADeliveredRun(NamedTuple):
    """What one call to this stage left behind, and every run of the suite behind that."""

    the_change: ADeliveredChange
    what_the_suite_was_handed: list[WhatTheSuiteWasHanded]
    the_commit: str


class ARefusedRun(NamedTuple):
    """What one refused call to this stage left behind, and the runs that led to the refusal.

    **`the_refusal` is an `Exception` and not `ATestThatPassesWithoutTheChangeError`, and that
    is the correction this fixture needed.** It used to demand that one named class, and a real
    model that declined to write the plan's test file produced a *different* refusal of the same
    run — `PlannedFileNotWrittenError`, from the stage before the third question is ever put. Both
    are correct: a plan the implementer did not apply is not a plan that was applied, and a change
    nothing observed is not a delivery. **A test that demands one of two correct answers fails
    on the other, and the failure reads as a defect in the system rather than as a fixture that
    was too narrow.**

    So the fixture says what it means — this run did not deliver, and here is what it said — and
    the test below says what it is about, which is the *third question* rather than the identity
    of the rule that caught it.
    """

    the_refusal: Exception
    what_the_suite_was_handed: list[WhatTheSuiteWasHanded]
    the_commit: str


def _the_small_document_this_repository_really_holds(clone: ClonedRepository) -> str:
    """The first of those files this clone really holds, or a loud reason there is none.

    **Read off the clone rather than named here, and the reason is that no test in this
    repository can know what a repository it has never read holds.** A name written into a test
    file is a guess about the substrate every assertion in this file rests on.
    """
    for a_name in FILES_A_CHANGE_ABOUT_A_REPOSITORY_MAY_GO_INTO:
        where = clone.path / a_name
        if not where.is_file():
            continue
        if where.stat().st_size > THE_LONGEST_A_FILE_MAY_BE_BEFORE_IT_IS_HANDED_BACK_WHOLE:
            continue
        return a_name

    pytest.skip(
        f"this clone holds none of {', '.join(FILES_A_CHANGE_ABOUT_A_REPOSITORY_MAY_GO_INTO)} "
        f"under {THE_LONGEST_A_FILE_MAY_BE_BEFORE_IT_IS_HANDED_BACK_WHOLE} bytes, so there is no "
        "file for a plan to change that a model could be asked to hand back whole. This tier does "
        "not invent one: a change to a file the repository does not have is the case the planner "
        "refuses, and refusing it here is the same rule."
    )


def _where_this_repository_keeps_its_tests(clone: ClonedRepository) -> str:
    """Where this clone keeps tests of its own, and how a test is named in that directory.

    **Only what is directly in the directory counts, and never anything below it.** `tests/` is
    the case that makes the rule: it holds none of them itself and holds two directories full of
    them, so a recursive search would say yes for it and place a test in a tier that collects
    nothing. A directory holding a test is a directory this repository demonstrably runs tests
    from; one holding none may be collected and may not, and there is no evidence either way.

    **The directory holding the most tests, so the plan is the same plan on every machine.** A
    walk in filesystem order names a different directory after a different clone, and two runs
    of one work item are compared against each other in a real pipeline.

    **The suffix is read from a test already there rather than guessed.** A repository naming
    its tests `*.spec.ts` and one naming them `*.test.ts` both collect, and a name invented
    here would put a file into a tier nothing runs.
    """
    the_tests_in_each_directory: dict[str, list[Path]] = {}

    for a_directory in sorted(clone.path.rglob("*")):
        if not a_directory.is_dir():
            continue
        its_parts = a_directory.relative_to(clone.path).parts
        if any(a_part in DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE for a_part in its_parts):
            continue
        the_tests_there = [
            a_file
            for a_file in sorted(a_directory.iterdir())
            if a_file.is_file() and (".test." in a_file.name or ".spec." in a_file.name)
        ]
        if the_tests_there:
            the_tests_in_each_directory[str(a_directory.relative_to(clone.path))] = the_tests_there

    if not the_tests_in_each_directory:
        pytest.skip(
            "this clone keeps no test of its own anywhere, so there is no directory a new test "
            "can be put where this repository demonstrably runs tests from. A repository with "
            "no suite is a real thing, and this tier does not introduce the first test to "
            "anything — that is a decision about a repository, not about a model."
        )

    its_path = sorted(
        the_tests_in_each_directory,
        key=lambda a_path: (-len(the_tests_in_each_directory[a_path]), a_path),
    )[0]
    a_test_already_there = the_tests_in_each_directory[its_path][0].name

    for a_marker in (".test.", ".spec."):
        if a_marker in a_test_already_there:
            return (
                f"{its_path}/{THE_NAME_OF_THE_TEST_THE_SECOND_PLAN_ADDS}"
                + (a_test_already_there[a_test_already_there.index(a_marker) :])
            )

    pytest.skip(
        f"{its_path} holds {a_test_already_there}, whose name this test cannot read a convention "
        "out of. Rather than guess a suffix this repository does not use, it says so — a test "
        "named into a tier the runner does not collect is a file nobody opened."
    )


def a_suite_recording_the_checkout_it_was_handed(
    plan: ImplementationPlan,
) -> tuple[RunTheSuite, list[WhatTheSuiteWasHanded]]:
    """The suite this stage is handed, and every call it received, in the order it received them.

    **It answers from the checkout and never from the call count.** A double that remembered
    that this was the third call and answered differently would defeat the one question
    `refuse_a_change_nothing_observed` exists to ask — so the number of calls is not an input to
    anything below, and three calls over two checkouts produce two identical answers and one
    that differs.

    **Green every time, and the reason is that it is not entitled to judge.** It never runs the
    repository's toolchain, so it has no standing to say a suite failed; a double that reported
    a failure it had not observed would be inventing the answer this file is here to check.
    Green three times over is therefore not a rigged green: it is what a witness says when it
    cannot tell the change from no change, and the refusal this produces is the rule working.

    **The report it prints names the planned tests that were on the disk, and only those.**
    A runner names the files it ran, and `the_tests_the_suite_never_ran` reads that as the only
    witness there is — so a planned test that was not on the disk is not named, and the stage
    that forgot to write it is caught by the rule that is armed for exactly that.
    """
    the_calls: list[WhatTheSuiteWasHanded] = []

    def run_the_suite(clone: ClonedRepository, repository: Repository) -> SuiteOutcome:
        del repository
        what_it_was_handed = _what_the_suite_was_handed(clone, plan)
        the_calls.append(what_it_was_handed)
        return SuiteOutcome(
            exit_code=0,
            passed=True,
            dependencies_installed=True,
            output=what_it_was_handed.what_it_reported,
        )

    return run_the_suite, the_calls


def _what_the_suite_was_handed(
    clone: ClonedRepository, plan: ImplementationPlan
) -> WhatTheSuiteWasHanded:
    """What a suite run over this checkout would have been able to see, read off the disk."""
    the_text_each_file_held = {
        a_path: (clone.path / a_path).read_text(encoding="utf-8") for a_path in plan.files_to_change
    }
    which_tests_were_there = [
        a_test for a_test in plan.tests_to_add if (clone.path / a_test).is_file()
    ]
    the_lines = [f"{a_test} (1 test)" for a_test in which_tests_were_there]
    the_lines.append(f"{len(which_tests_were_there)} passed")

    return WhatTheSuiteWasHanded(
        the_text_each_file_the_plan_changes_held=the_text_each_file_held,
        which_planned_tests_were_on_the_disk=which_tests_were_there,
        what_it_reported="\n".join(the_lines),
    )


def _what_git_said(clone: ClonedRepository, arguments: list[str]) -> str:
    """What one `git` command said, run through the same tool every other caller in here runs."""
    return the_outcome_of(
        ACommand(
            program="git",
            arguments=arguments,
            working_directory=str(clone.path),
            seconds_it_may_take=A_MINUTE_OF_GIT,
        )
    ).standard_output


def _the_commit_the_clone_stands_at(clone: ClonedRepository) -> str:
    """`git rev-parse HEAD`, read while the run in question was the last thing to happen."""
    return _what_git_said(clone, ["rev-parse", "HEAD"]).strip()


def _the_files_a_commit_names(clone: ClonedRepository, a_commit: str) -> list[str]:
    """The paths one commit recorded, as `git log` would list them in a history."""
    named = _what_git_said(clone, ["show", "--name-only", "--format=", a_commit])
    return [a_line.strip() for a_line in named.splitlines() if a_line.strip()]


def _the_author_a_commit_is_recorded_under(clone: ClonedRepository, a_commit: str) -> str:
    """Who `git log` says made one commit, in the form it records them."""
    return _what_git_said(clone, ["log", "-1", "--format=%an <%ae>", a_commit]).strip()


def _the_text_a_commit_records_of(clone: ClonedRepository, a_commit: str, a_path: str) -> str:
    """What one commit holds of one path, which is the change and not the working tree."""
    return _what_git_said(clone, ["show", f"{a_commit}:{a_path}"])


@pytest.fixture(scope="module")
def a_plan_this_run_will_apply(a_clone_this_run_may_write: ClonedRepository) -> ImplementationPlan:
    """One real plan for this repository: the one file a change about it may go into.

    **`files_to_add` and `tests_to_add` are both left empty, and that is the honest answer for a
    change of this shape.** A change to what a repository already states about itself needs no
    file created to hold it and no test to prove a sentence is there, so this plan also
    exercises the empty case rather than pretending otherwise.

    **A plan naming no test is a plan that never puts the third question**, which is the second
    fixture's reason for existing rather than this one's.
    """
    return ImplementationPlan(
        files_to_change=[
            _the_small_document_this_repository_really_holds(a_clone_this_run_may_write)
        ]
    )


@pytest.fixture(scope="module")
def a_plan_naming_a_test_this_run_should_refuse(
    a_clone_this_run_may_write: ClonedRepository,
) -> ImplementationPlan:
    """The same file, and one test beside the tests this repository already runs.

    **This plan exists to put the third question.** `refuse_a_change_nothing_observed` asks
    nothing when the approved plan named no test, so a plan naming one is the only way this
    stage can be asked whether anything observed the change — and the answer, from a suite that
    cannot tell the two checkouts apart, has to be a refusal.

    **The test is placed where this repository demonstrably runs tests from**, read off the
    clone rather than guessed, because a test named into a tier nothing collects is a file
    nobody opened and would make the refusal this fixture expects mean nothing.
    """
    return ImplementationPlan(
        files_to_change=[
            _the_small_document_this_repository_really_holds(a_clone_this_run_may_write)
        ],
        tests_to_add=[_where_this_repository_keeps_its_tests(a_clone_this_run_may_write)],
    )


@pytest.fixture(scope="module")
def a_real_delivered_change(
    a_plan_this_run_will_apply: ImplementationPlan,
    the_repository: Repository,
    a_clone_this_run_may_write: ClonedRepository,
    the_model_for,
    request,
) -> ADeliveredRun:
    """One real implementation, recorded and verified, shared by every assertion about it.

    **The writable copy, for the reason this file's own docstring gives**, and the suite it is
    handed is the recording one — so this is a real model writing real files and a real `git`
    commit, with the repository's own toolchain standing in as a witness.

    Module scope, because a model call is the expensive part and the assertions below are
    contracts about *one* change. A second run would prove only that the model answers
    differently each time.

    **The commit is read while this fixture runs**, because the second fixture in this file
    makes a commit of its own and a test that asked `HEAD` afterwards would be asserting about
    whichever call happened last.

    **A run this model refuses to finish skips here, with the reason printed, and this fixture
    used to error instead.** It demanded a delivery with no `pytest.raises` of any kind, so a run
    refused for a correct reason was reported as four setup errors — and four setup errors read as
    *the system is broken* rather than as *this run did not deliver*. Four of them, at once, on one
    fixture, is the shape a reader trusts least.

    **The measurement that made it necessary:** `TheCommitHoldsNoneOfTheFilesThePlanNamedError`
    began arriving on this deployment's plans — `files_to_change=['package.json']` with a commit
    that changed a test file and nothing else. So this is not one unlucky model answer; it is what
    this deployment's plans often look like, and a fixture that cannot hear it is a fixture that
    will go on reporting the wrong thing every time it happens.
    """
    run_the_suite, what_the_suite_was_handed = a_suite_recording_the_checkout_it_was_handed(
        a_plan_this_run_will_apply
    )

    try:
        the_change = apply_and_verify(
            a_clone_this_run_may_write,
            the_repository,
            a_plan_this_run_will_apply,
            the_model_for(request.param),
            run_the_suite,
        )
    except REFUSALS_THAT_MEAN_THIS_RUN_DELIVERED_NOTHING as the_refusal:
        pytest.skip(
            f"this run did not deliver, by {type(the_refusal).__name__}, so there is no change for "
            f"the four tests below to be about: {the_refusal}. Every contract here is about a "
            "delivered change, and asserting about one that does not exist would be asserting "
            "about nothing. This is a skip rather than a pass and rather than an error, because a "
            "refusal the rules already state is not a defect in the system under test."
        )

    return ADeliveredRun(
        the_change=the_change,
        what_the_suite_was_handed=what_the_suite_was_handed,
        the_commit=_the_commit_the_clone_stands_at(a_clone_this_run_may_write),
    )


@pytest.fixture(scope="module")
def a_run_refused_for_nothing_having_observed_the_change(
    a_plan_naming_a_test_this_run_should_refuse: ImplementationPlan,
    the_repository: Repository,
    a_clone_this_run_may_write: ClonedRepository,
    the_model_for,
    request,
) -> ARefusedRun:
    """One real implementation whose plan named a test, and the refusal it has to end in.

    **`pytest.raises` around a tuple of the refusals this run can honestly end in, because two
    of them are correct and the fixture used to accept only one.** A real model that declines to
    write the plan's test file is stopped by `PlannedFileNotWrittenError`, before the third
    question is ever put; a model that writes it is stopped by
    `ATestThatPassesWithoutTheChangeError`, because the recording suite cannot tell the change
    from no change. **Both refusals mean this run did not deliver, and a fixture naming only the
    second fails on the first as though the system were broken.**

    A delivery is the one outcome not accepted, and it is the outcome that would make everything
    below vacuous: the test asserts the suite was asked three times and the change came off the
    disk while it was asked.

    The calls are kept whatever the outcome, because the order is the thing worth looking at.
    """
    run_the_suite, what_the_suite_was_handed = a_suite_recording_the_checkout_it_was_handed(
        a_plan_naming_a_test_this_run_should_refuse
    )

    with pytest.raises(REFUSALS_THAT_MEAN_THIS_RUN_DELIVERED_NOTHING) as the_refusal:
        apply_and_verify(
            a_clone_this_run_may_write,
            the_repository,
            a_plan_naming_a_test_this_run_should_refuse,
            the_model_for(request.param),
            run_the_suite,
        )

    return ARefusedRun(
        the_refusal=the_refusal.value,
        what_the_suite_was_handed=what_the_suite_was_handed,
        the_commit=_the_commit_the_clone_stands_at(a_clone_this_run_may_write),
    )


@pytest.mark.parametrize("a_real_delivered_change", list(LlmProvider), indirect=True)
def test_the_change_is_on_the_disk_holding_exactly_what_the_model_proposed(
    a_real_delivered_change: ADeliveredRun, a_clone_this_run_may_write: ClonedRepository
) -> None:
    """Every path this stage wrote is a file of the clone, holding the text proposed for it.

    **The disk and not the answer, because a list of files is a claim and a file is a fact.**
    The implementer is asked for the complete text each file should end up holding, so "the file
    now holds what was proposed" is the whole contract of that half of this stage in one
    comparison — and it is the one that cannot be satisfied by an answer that was well formed and
    never applied.

    **And every file is non-empty, because an emptied file is a regression nobody asked for.**
    """
    the_change = a_real_delivered_change.the_change
    every_write: list[FileToWrite] = the_change.written

    assert every_write, (
        "the stage applied a plan and wrote no file at all. The plan names a file to change, and "
        "a node that accepted an empty answer would leave the checkout exactly as it was found "
        "while reporting a change"
    )

    for one_write in every_write:
        where = a_clone_this_run_may_write.path / one_write.path
        assert where.is_file(), (
            f"{one_write.path!r} is in what the stage returned and is not a file of the clone "
            "afterwards, so the change was reported and never written"
        )
        assert where.read_text(encoding="utf-8") == one_write.content, (
            f"{one_write.path!r} does not hold the text that was proposed for it. The stage is "
            "asked for the whole text of a file rather than a diff, so a file that differs from "
            "the answer is a file that was written from something else — and the commit beside "
            "it would carry a diff nobody read"
        )
        assert one_write.content.strip(), (
            f"{one_write.path!r} was written empty. A file holding nothing is not a change to it, "
            "and a repository where a file has been emptied is a regression nobody asked for"
        )


@pytest.mark.parametrize("a_real_delivered_change", list(LlmProvider), indirect=True)
def test_the_change_is_recorded_in_a_commit_this_agent_authored(
    a_real_delivered_change: ADeliveredRun,
    a_plan_this_run_will_apply: ImplementationPlan,
    a_clone_this_run_may_write: ClonedRepository,
) -> None:
    """`git` holds the change, in a commit that names the plan's paths and the agent as its author.

    **This is the assertion a real run was missing for forty-five minutes.** It wrote its files,
    reported a verification and a suite green on both sides of the change, and pushed a branch
    pointing at the same commit as `main`, because nothing had committed anything. GitHub's
    `No commits between main and aisdlc/…` was the only report there ever was.

    **Three separate facts, and each is a way that could go wrong on its own.** The commit has
    to exist at all — a working tree is not a commit. It has to name the paths the approved plan
    named, so the pull request this becomes carries the plan and not whatever else was lying
    around in the tree. And it has to be recorded under the agent, because a commit naming a
    person for work a machine did is a forged trail that looks exactly like the real thing at
    the moment somebody has to tell them apart.

    **The commit's own copy of the file is compared, not the working tree's.** A file written
    and never staged, or staged and committed with different content, is the failure a working
    tree cannot show.
    """
    the_change = a_real_delivered_change.the_change
    the_commit = a_real_delivered_change.the_commit

    every_commit_in_the_history = _what_git_said(a_clone_this_run_may_write, ["log", "--format=%H"])
    assert the_commit and the_commit in every_commit_in_the_history, (
        f"{the_commit!r} is not a commit in this clone's history. A delivery pushes a commit, so "
        "a change that is only a working tree does not exist to the person receiving it — and "
        "GitHub's answer to that is `No commits between main and aisdlc/…`"
    )

    the_plan_named = [
        *a_plan_this_run_will_apply.files_to_change,
        *a_plan_this_run_will_apply.files_to_add,
        *a_plan_this_run_will_apply.tests_to_add,
    ]
    assert a_plan_this_run_will_apply.files_to_change, (
        "the plan this run applied names no file to change, so the commit assertion below is "
        "about nothing — and an empty plan is a fault the plan's own rule refuses"
    )
    the_paths_the_commit_names = _the_files_a_commit_names(a_clone_this_run_may_write, the_commit)
    for a_path in the_plan_named:
        assert a_path in the_paths_the_commit_names, (
            f"{a_path!r} is named by the approved plan and is not named by {the_commit}. The "
            f"commit recorded {the_paths_the_commit_names}. A change the plan accounts for and "
            "the history does not is a change nobody is receiving, whatever the working tree says"
        )

    for one_write in the_change.written:
        what_the_commit_records = _the_text_a_commit_records_of(
            a_clone_this_run_may_write, the_commit, one_write.path
        )
        assert what_the_commit_records == one_write.content, (
            f"{the_commit} does not hold the text {one_write.path!r} was proposed as. The working "
            "tree and the history disagreeing is exactly the state a delivery cannot be built "
            "from, and it is invisible to anything that reads the files instead of the commit"
        )

    assert (
        _the_author_a_commit_is_recorded_under(a_clone_this_run_may_write, the_commit)
        == f"{THE_AGENT_THAT_OWNS_THE_COMMIT} <{THE_ADDRESS_THE_COMMIT_CAN_BE_READ_FROM}>"
    ), (
        "the commit this run made is not recorded under the agent that made it. A commit naming "
        "a person for work a machine did is a forged trail, and it looks exactly like the real "
        "thing at the moment somebody has to tell them apart — which is the same reason an "
        "approval keeps `decided_by` verbatim"
    )


@pytest.mark.parametrize("a_real_delivered_change", list(LlmProvider), indirect=True)
def test_the_suite_was_run_before_the_change_and_after_it(
    a_real_delivered_change: ADeliveredRun,
    a_plan_this_run_will_apply: ImplementationPlan,
    the_cloned_repository: ClonedRepository,
) -> None:
    """Two runs happened, the first over the repository as cloned and the second over the change.

    **The order is the property, and the recording is what proves it.** A verification that
    applied the change first and ran the suite twice afterwards would report the same number
    twice and call it before-and-after, and there is no way to catch that from outside
    `verify_the_change` — so this reads the checkout each call was handed and asks which of the
    two was which.

    **The first run is compared with the read-only clone, which nothing in this tier writes
    to.** That makes it a claim about this repository as it was cloned rather than about
    whatever the previous call in this module left behind, which is the difference between a
    before and a merely earlier.

    **The two answers are also in the report the run hands back**, so a report carrying one
    outcome twice would be caught here as well as by the recordings.
    """
    the_change = a_real_delivered_change.the_change
    what_it_was_handed = a_real_delivered_change.what_the_suite_was_handed

    assert len(what_it_was_handed) == 2, (
        f"the suite was run {len(what_it_was_handed)} times for a plan naming no test, so the "
        "report cannot be carrying a suite before the change and a suite after it. A plan that "
        "names no test is never asked whether anything observed the change, which is this "
        "fixture's case and the second fixture's reason for existing"
    )

    before, after = what_it_was_handed
    the_file_the_plan_changes = a_plan_this_run_will_apply.files_to_change[0]
    how_the_repository_was_cloned = (
        the_cloned_repository.path / the_file_the_plan_changes
    ).read_text(encoding="utf-8")

    assert before.the_text_each_file_the_plan_changes_held[the_file_the_plan_changes] == (
        how_the_repository_was_cloned
    ), (
        f"the first run of the suite was not handed the repository as it was cloned. The file "
        f"{the_file_the_plan_changes!r} held something else at that moment, so the report's "
        "`suite_before_the_change` is not a before at all — it is a second run over the same "
        "checkout the change was applied to"
    )
    assert after.the_text_each_file_the_plan_changes_held[the_file_the_plan_changes] == (
        the_change.written[0].content
    ), (
        f"the second run of the suite was not handed the change. {the_file_the_plan_changes!r} "
        "held something other than what the model proposed at that moment, so the verification "
        "describes a repository this run did not produce"
    )
    assert before.the_text_each_file_the_plan_changes_held != (
        after.the_text_each_file_the_plan_changes_held
    ), (
        "both runs of the suite were handed the same checkout, so this run changed nothing on "
        "the disk as far as anything can tell — and a pull request whose diff is empty is the "
        "one thing this pipeline must never produce"
    )

    the_report = the_change.verification
    assert the_report.suite_before_the_change.output == before.what_it_reported, (
        "the report's `suite_before_the_change` is not the first run that happened. A report that "
        "carries one answer twice describes a suite nobody ran"
    )
    assert the_report.suite_after_the_change.output == after.what_it_reported, (
        "the report's `suite_after_the_change` is not the second run that happened, so the "
        "verification a gate presents is not a record of what the suite said"
    )


@pytest.mark.parametrize("a_real_delivered_change", list(LlmProvider), indirect=True)
def test_the_note_beside_the_change_carries_all_three_of_the_implementers_judgements(
    a_real_delivered_change: ADeliveredRun,
) -> None:
    """The implementer's three sentences reach the caller whole, and none of them is blank.

    **The implementer is asked in the same call as the files, so the plan is a list of paths with
    no intent and its doubt is the last place a mechanism nobody specified can still be named.**
    A real run's implementer wrote *whether the plan meant a rule for a file that already exists
    or a whole new file, because the plan names one path and no intent* — a true sentence, not a
    reason to stop, and the single most useful thing on the card.

    **Each of the three is asserted inside the note rather than beside it**, because the note is
    what this stage hands on: a caller receiving a collapsed sentence has lost two of the three
    and has no way of telling which two.
    """
    what_the_implementer_said = a_real_delivered_change.the_change.what_the_implementer_said

    assert what_the_implementer_said.strip(), (
        "the change was applied, the suite was run on both sides of it and the implementer left "
        "no note at all. The next thing that happens to a change is a person reading what the "
        "run concluded, and an empty note reads as *the implementer had nothing to say*, which "
        "is not a thing anybody can check"
    )

    for a_judgement in JUDGEMENTS_THE_IMPLEMENTER_MAKES:
        assert a_judgement in what_the_implementer_said, (
            f"{a_judgement!r} is not in the note this stage handed back. The note is composed of "
            f"the implementer's three judgements, so one of them missing means the caller lost "
            f"it — and the three are {', '.join(JUDGEMENTS_THE_IMPLEMENTER_MAKES)}"
        )


@pytest.mark.parametrize(
    "a_run_refused_for_nothing_having_observed_the_change", list(LlmProvider), indirect=True
)
def test_the_third_question_is_asked_of_a_different_checkout_and_the_run_is_refused(
    a_run_refused_for_nothing_having_observed_the_change: ARefusedRun,
    a_plan_naming_a_test_this_run_should_refuse: ImplementationPlan,
    a_clone_this_run_may_write: ClonedRepository,
) -> None:
    """Three runs, two checkouts, and a refusal — and the change is back on the disk afterwards.

    **The three runs are the whole point, and so is the fact that two of them were handed the
    same checkout.** The first is over the repository as this run found it, the second is over
    the change, and the third is over the repository again with the change put back — which is
    what `_the_suite_with_the_change_put_back` exists to ask. A double that answered the third
    call differently from the first by remembering that it was the third call would defeat the
    question entirely, so the recording is compared against `git`: the first and the third calls
    must both hold what the change's parent commit holds, and the second must not.

    **And the refusal is the answer this stage owes the run.** The recording suite cannot tell
    the change from no change, so the truthful reading of its three answers is that nothing
    observed the change, and a change nothing observed is not a delivery. The rule's own
    semantics are proved in `tests/test_whether_anything_observed_the_change.py`; what is proved
    here is that this stage puts the question and stands down on the answer.

    **The last assertion is that the change is back on the disk, and it is the one that matters
    most after the refusal.** The putting back is in a `finally` because the delivery that
    follows pushes this working tree: an undone change that nobody restored is a pull request
    that silently drops the work, which is worse than the bug the question was asked to catch.
    """
    the_refusal = a_run_refused_for_nothing_having_observed_the_change.the_refusal
    what_it_was_handed = (
        a_run_refused_for_nothing_having_observed_the_change.what_the_suite_was_handed
    )
    the_commit = a_run_refused_for_nothing_having_observed_the_change.the_commit

    if not isinstance(the_refusal, ATestThatPassesWithoutTheChangeError):
        pytest.skip(
            f"this run was refused earlier, by {type(the_refusal).__name__}, so the third "
            f"question was never put: {the_refusal}. The model declined to write every file the "
            "plan named, or named a file the commit never touched — both are the implementer's "
            "own rules firing correctly. A plan that is not fully applied is not a plan that was "
            "applied, and a change that is in no file the plan named is a change there is nothing "
            "to put back. Everything below is about what happens *after* a change is on the disk, "
            "so on this run there was nothing to ask about, and asserting the suite's three "
            "answers would be asserting about two."
        )

    for a_test in a_plan_naming_a_test_this_run_should_refuse.tests_to_add:
        assert a_test in str(the_refusal), (
            f"{a_test!r} is in the approved plan and is not named by the refusal. Whoever reads "
            "it has to go and find the test that was supposed to notice the change"
        )

    assert len(what_it_was_handed) == 3, (
        f"the suite was run {len(what_it_was_handed)} times and this plan named a test, so the "
        "question that decides whether anything observed the change was never put"
    )

    the_file_the_plan_changes = a_plan_naming_a_test_this_run_should_refuse.files_to_change[0]
    before, after, with_the_change_put_back = what_it_was_handed
    what_the_parent_commit_holds = _the_text_a_commit_records_of(
        a_clone_this_run_may_write, f"{the_commit}~1", the_file_the_plan_changes
    )
    what_the_change_commit_holds = _the_text_a_commit_records_of(
        a_clone_this_run_may_write, the_commit, the_file_the_plan_changes
    )

    assert before.the_text_each_file_the_plan_changes_held[the_file_the_plan_changes] == (
        what_the_parent_commit_holds
    ), (
        "the first run of the suite was not handed the repository as this run found it, so the "
        "comparison the third run is part of has nothing to compare against"
    )
    assert after.the_text_each_file_the_plan_changes_held[the_file_the_plan_changes] == (
        what_the_change_commit_holds
    ), (
        "the second run of the suite was not handed the change, so this run applied nothing the "
        "suite was ever asked about"
    )

    # **The whole checkout and not one field of it, and the reason is the second plan's shape.**
    # This plan's change is a test file that did not exist before, so `files_to_change` is
    # identical across all three runs and comparing it alone says the checkouts never differed.
    # That assertion is not a weak version of the claim — it is the wrong claim, and it fails on
    # a run that behaved perfectly.
    what_the_third_run_saw = with_the_change_put_back.what_a_run_of_the_suite_could_have_seen()
    what_the_second_run_saw = after.what_a_run_of_the_suite_could_have_seen()
    what_the_first_run_saw = before.what_a_run_of_the_suite_could_have_seen()

    # **The third run must equal the first on the files and exceed it by exactly the tests.**
    #
    # This assertion was `what_the_third_run_saw == what_the_first_run_saw`, and it could not pass
    # on any run — verified failing at `8745235~1` and at `8745235`, byte-identically. The reason
    # is a rule in `apply_the_plan.py` that is deliberate and stated: *"Only the files the plan
    # named, and never the tests. The tests are what the question is about — a suite with the tests
    # taken away says nothing either way."* So the third run holds the parent's text **and** the
    # tests the plan added, and the first run holds the parent's text and not those tests.
    #
    # **And the contradiction was introduced by the very method written to prevent a false pass.**
    # `what_a_run_of_the_suite_could_have_seen` exists because comparing the texts alone says two
    # different checkouts are identical; it closed that trap by adding which files are on the
    # disk, and then the assertion above demanded equality on that second half too. The two
    # decisions are each defensible alone and together they are unsatisfiable.
    #
    # So the claim is split into the two things it is actually made of: the text went back to the
    # parent's, and the only thing the third run holds that the first does not is the plan's own
    # tests. A weaker version would compare `files_to_change` alone — which is empty for a
    # test-only plan, and would pass without observing anything.
    the_text_the_third_run_saw, the_tests_the_third_run_saw = what_the_third_run_saw
    _, the_tests_the_first_run_saw = what_the_first_run_saw

    assert the_text_the_third_run_saw[the_file_the_plan_changes] == what_the_parent_commit_holds, (
        f"the third run of the suite was handed {the_file_the_plan_changes} holding "
        f"{the_text_the_third_run_saw[the_file_the_plan_changes]!r} rather than what this run's "
        f"parent commit holds. The change was not put back before the question was asked, so the "
        f"third run is the second run wearing a different name"
    )
    assert set(the_tests_the_third_run_saw) - set(the_tests_the_first_run_saw) == set(
        a_plan_naming_a_test_this_run_should_refuse.tests_to_add
    ), (
        "the third run does not hold exactly the tests this plan added and the first run did not. "
        f"It holds {sorted(the_tests_the_third_run_saw)} where the first held "
        f"{sorted(the_tests_the_first_run_saw)}, so the checkout the third question was asked "
        "about is not the checkout this design describes — which is the file the plan changed plus "
        "the tests it named, and anything else is something else entirely"
    )
    assert what_the_second_run_saw != what_the_third_run_saw, (
        "the second and the third runs were handed identical checkouts, so this change is "
        "indistinguishable from no change as far as anything in this repository can tell — which "
        "is the finding, and it is why the run was refused"
    )
    assert what_the_second_run_saw != what_the_first_run_saw, (
        "the second run was handed the same checkout as the first, so the change was not on the "
        "disk while the suite was asked about it"
    )

    what_the_checkout_holds_now = (
        a_clone_this_run_may_write.path / the_file_the_plan_changes
    ).read_text(encoding="utf-8")
    assert what_the_checkout_holds_now == what_the_change_commit_holds, (
        "the run refused this change and left the change off the disk. The putting back is in a "
        "`finally` because the delivery that follows pushes this working tree, and an undone "
        "change nobody restored is a pull request that silently drops the work — worse than the "
        "bug the third question was asked to catch"
    )
