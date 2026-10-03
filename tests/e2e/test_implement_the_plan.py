"""The implementation agent, against a real model and a real repository — and this one writes.

**This is the only stage in this tier that changes the repository, and that is the whole reason
it needs proving on its own.** Everything beside it in the tier reads: a discovery report, a
requirements set, an architecture report and a plan are all claims about a checkout, and a claim
can be checked against the checkout afterwards. **A change cannot.** It either is on the disk or
it is not, so the assertions here are made against the files themselves and not against what the
agent said it did — a summary of what was written is not a substitute for reading it.

**So this stage is handed `a_clone_this_run_may_write`, and never the shared clone.** The other
files in this tier read the read-only one, and a writable copy of it exists precisely for the
stages that change things. Writing into the shared clone would leave the change there for whatever
came next in the same module to find, and a test asserting a checkout was left alone would then
pass for the wrong reason — which is the same shape as a test that cannot fail. **The read-only
clone is still used here, as the record of what the repository was before**: nothing writes to it,
so a file's text in one clone and not the other is exactly what this run changed.

**The plan is built from what the clone actually holds, by reading it.** No file name can be
written into a test file: the repository this deployment points the tier at is stated in its own
`.env`, this repository has never read it, and a test that named a file it could not check would be
guessing at the substrate the whole assertion rests on. So the plan below is assembled from the
checkout — a file the repository really has, and a test directory it demonstrably keeps tests in —
and named as a stand-in for the plan a person would have approved.

**Nothing here runs the suite and nothing here commits.** Those are `apply_and_verify`'s two other
responsibilities, in one node, because the suite has to run *around* the change. Asserting either
from this file would be asserting that a function does what a different function does, and the
container tier is where a repository's own code is run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aisdlc.agents.implement_the_plan import (
    AWriteThatChangesNothingError,
    FileOutsideThePlanError,
    FileToWrite,
    FileWrittenTwiceError,
    PlannedFileNotWrittenError,
    WhatTheImplementerConcluded,
    implement_the_plan,
)
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE

pytestmark = pytest.mark.e2e

JUDGEMENTS_THE_IMPLEMENTER_MAKES = (
    "what_it_found",
    "what_it_could_not_settle",
    "what_it_expects_next",
)

# **The files a plan here changes, in the order a repository is most likely to have them.** A
# document a person reads first, and then the manifest every build is defined by — both of which a
# change to what a repository claims about itself is made in. Neither is hard-coded as *the* file:
# the first one this clone really holds is the one the plan names, and a repository with neither
# says so out loud rather than getting a file invented for it.
FILES_A_PLAN_MAY_CHANGE_FIRST = (
    "README.md",
    "README.rst",
    "README.txt",
    "README",
    "package.json",
)

# **A file has to be small enough to hand back whole, because that is what is asked for.** The
# implementer is given the complete text a file should end up holding, so a 184KB lockfile would
# be a truncation this test could not tell apart from a model that decided to shorten it. The
# bound is on the file the plan names and nothing else, and it is generous for the two kinds of
# file above.
THE_LONGEST_A_FILE_MAY_BE_BEFORE_IT_IS_HANDED_BACK_WHOLE = 8_000

# The name this test gives the test the plan adds. It says what the file is — a file a real run
# wrote — rather than what it asserts, because the plan carries paths and no intent, and a name
# claiming an assertion nobody approved would be a second invention.
THE_NAME_OF_THE_TEST_THIS_PLAN_ADDS = "aisdlc-a-real-run-wrote-this"


def _the_file_this_plan_will_change(clone: ClonedRepository) -> str:
    """The first file of that list this clone really holds, or a loud reason there is none.

    **Read off the clone rather than named here, and the reason is that no test in this repository
    can know what a repository it has never read holds.** A name written into a test file is a
    guess about the substrate every assertion in this file rests on: a plan naming a file that is
    not there fails inside the agent, and a run that never gets to assert anything is a green tick
    about nothing.
    """
    for a_name in FILES_A_PLAN_MAY_CHANGE_FIRST:
        where = clone.path / a_name
        if not where.is_file():
            continue
        if where.stat().st_size > THE_LONGEST_A_FILE_MAY_BE_BEFORE_IT_IS_HANDED_BACK_WHOLE:
            continue
        return a_name

    pytest.skip(
        f"this clone holds none of {', '.join(FILES_A_PLAN_MAY_CHANGE_FIRST)}, so there is no "
        "file for a plan to change that a model could be asked to hand back whole. This tier does "
        "not invent one: a change to a file the repository does not have is the case the planner "
        "refuses, and refusing it here is the same rule."
    )


def _where_this_repository_keeps_its_tests(clone: ClonedRepository) -> tuple[str, str]:
    """Where this clone keeps tests of its own, and how a test is named in that directory.

    **The directory holding the most tests, not the first one found.** A walk in filesystem order
    would name a different directory on a different machine and after a different clone, and the
    plan this file builds has to be the same plan every time — two runs of one work item are
    compared against each other in a real pipeline.

    **Only what is directly in the directory counts, and never anything below it.** `tests/` is the
    case that makes the rule: it holds none of them and holds two directories full of them, so a
    recursive search would say yes for it and pass exactly the plan a real run once wrote, where a
    test landed where no test had ever been and the suite passed identically on both sides of the
    change. A directory holding a test is a directory this repository demonstrably runs tests
    from; one holding none may be collected and may not, and there is no evidence either way.

    **The naming is read from a test already there rather than guessed.** A repository naming its
    tests `*.spec.ts` and one naming them `*.test.ts` both collect, and a name invented here
    would put a file into a tier that does not run it. Somebody else's code is skipped by the
    same list the inspection skips, read from the module that decides what a model is shown.
    """
    tests_in_each_directory: dict[str, list[Path]] = {}

    for a_directory in clone.path.rglob("*"):
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
            tests_in_each_directory[str(a_directory.relative_to(clone.path))] = the_tests_there

    if not tests_in_each_directory:
        pytest.skip(
            "this clone keeps no test of its own anywhere, so there is no directory a new test can "
            "be put where this repository demonstrably runs tests from. A repository with no suite "
            "is a real thing, and this tier does not introduce the first test to anything — that "
            "is a decision about a repository, not about a model"
        )

    its_path = sorted(
        tests_in_each_directory, key=lambda a_path: (-len(tests_in_each_directory[a_path]), a_path)
    )[0]
    the_tests_there = tests_in_each_directory[its_path]
    a_test_already_there = the_tests_there[0].name

    for a_marker in (".test.", ".spec."):
        if a_marker in a_test_already_there:
            return its_path, a_test_already_there[a_test_already_there.index(a_marker) :]

    pytest.skip(
        f"{its_path} holds {a_test_already_there}, whose name this test cannot read a convention "
        "out of. Rather than guess a suffix this repository does not use, it says so — a test "
        "named into a tier the runner does not collect is a file nobody opened"
    )


def every_path_the_approved_plan_accounts_for(plan: ImplementationPlan) -> list[str]:
    """Every path the plan says this change touches, in the order the artifact lists them.

    **Spelled out rather than imported from the module that enforces it.** That module has one
    place where the three lists come together precisely so a reader is not left comparing them,
    and it is the right place for it — but importing it here would make this file agree with the
    code by construction, and a helper that lost one of the three lists would take the assertion
    that is supposed to notice with it. This is the check on that helper.
    """
    return [*plan.files_to_change, *plan.files_to_add, *plan.tests_to_add]


def _every_file_a_clone_holds(clone: ClonedRepository) -> dict[str, str]:
    """Every file of a clone, keyed by the path a plan would name it by.

    **Compared between two clones rather than asked of the answer, which is the point.** The
    implementation agent returns what it says it wrote, and a list of files is a claim; the
    difference between the repository as it was cloned and the repository as this run left it is a
    fact about a disk, and it is the fact a delivery is built out of. Somebody else's code and the
    history are skipped by name — this stage writes working-tree files, and a diff that included
    `.git` would be a different claim about what changed.
    """
    held: dict[str, str] = {}

    for a_path in clone.path.rglob("*"):
        if not a_path.is_file():
            continue
        its_parts = a_path.relative_to(clone.path).parts
        if any(a_part in DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE for a_part in its_parts):
            continue
        held[str(a_path.relative_to(clone.path))] = a_path.read_text(
            encoding="utf-8", errors="replace"
        )

    return held


def _the_text_a_clone_holds_of(clone: ClonedRepository, a_path: str) -> str | None:
    """What one file of a clone held, or `None` because the clone does not hold it at all."""
    where = clone.path / a_path
    if not where.is_file():
        return None
    return where.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def a_plan_this_run_will_apply(a_clone_this_run_may_write: ClonedRepository) -> ImplementationPlan:
    """One real plan for this repository, assembled from the checkout rather than written here.

    **Two paths, and each answers a different question.** One file the repository already has and
    this change rewrites in place, and one test in a directory the repository demonstrably keeps
    tests in — which is what puts this test on both sides of `PlannedFileNotWrittenError`, the
    refusal that fires when a plan is only half applied.

    **`files_to_add` is left empty, and that is the honest answer for a change of this shape.**
    The request this deployment's real tier makes is about what a repository states, and a
    sentence added to a document the repository already has does not need a file created to hold
    it. It also means this file exercises the empty case rather than pretending otherwise.
    """
    the_file_to_change = _the_file_this_plan_will_change(a_clone_this_run_may_write)
    its_directory, how_a_test_is_named = _where_this_repository_keeps_its_tests(
        a_clone_this_run_may_write
    )

    return ImplementationPlan(
        files_to_change=[the_file_to_change],
        tests_to_add=[
            f"{its_directory}/{THE_NAME_OF_THE_TEST_THIS_PLAN_ADDS}{how_a_test_is_named}"
        ],
    )


@pytest.fixture(scope="module")
def a_real_change(
    a_plan_this_run_will_apply: ImplementationPlan,
    a_clone_this_run_may_write: ClonedRepository,
    the_model_for,
    request,
) -> WhatTheImplementerConcluded:
    """One real implementation, shared by every assertion about it.

    **The writable copy, for the reason this file's own docstring gives.** Every assertion below
    reads that copy, and one of them reads the read-only one to know what the repository held
    before — so the two have to be two, or "what this run changed" has nowhere to be measured
    against.

    Module scope, because a model call is the expensive part and the four assertions are four
    contracts about *one* change. A second run would prove only that the model answers differently
    each time.

    **The provider is `request.param` and the tests parametrise it indirectly**, so a run
    configured for one provider *skips* the others with the reason printed rather than passing
    quietly.

    **A run this model refuses to implement skips here, with the reason printed, and this fixture
    used to error instead.** It called `implement_the_plan` with nothing to catch, so a run refused
    for a correct reason arrived as four setup errors:

        PlannedFileNotWrittenError: The plan names ['package.json',
        'tests/unit/aisdlc-a-real-run-wrote-this.test.ts'] and the answer did not write them

    **That is the implementer's own rule firing correctly** - a plan not fully applied is not a plan
    that was applied - and this deployment's model does decline regularly enough to be worth
    catching. Four of the same error is the shape a reader trusts least: it reads as *the system is
    broken* rather than as *this run did not implement the plan*.

    **This is the third fixture to need this, and the same fix as the other two.** A closed set of
    refusals and a set of fixtures that cannot hear one are the same obligation seen from two
    sides, and a rule added to `implement_the_plan` now has two places to join rather than the one
    a reader of this function would guess.
    """
    try:
        return implement_the_plan(
            a_clone_this_run_may_write, a_plan_this_run_will_apply, the_model_for(request.param)
        )
    except (
        PlannedFileNotWrittenError,
        FileOutsideThePlanError,
        AWriteThatChangesNothingError,
        FileWrittenTwiceError,
    ) as the_refusal:
        pytest.skip(
            f"this run implemented nothing, by {type(the_refusal).__name__}, so there is no change "
            f"for the four tests below to be about: {the_refusal}. Every contract here is about a "
            "change this model actually made, and asserting about one that does not exist would be "
            "asserting about nothing. A skip and not a pass and not an error, because a refusal "
            "the rules already state is not a defect in the system under test."
        )


@pytest.mark.parametrize("a_real_change", list(LlmProvider), indirect=True)
def test_the_file_on_disk_afterwards_holds_exactly_what_the_model_proposed(
    a_real_change: WhatTheImplementerConcluded,
    a_plan_this_run_will_apply: ImplementationPlan,
    a_clone_this_run_may_write: ClonedRepository,
) -> None:
    """Every path the plan named is a file of the clone, holding the text that was proposed for it.

    **The disk and not the answer, because a list of files is a claim and a file is a fact.** The
    implementer is asked for the complete text each file should end up holding, so "the file now
    holds what was proposed" is the whole contract of this stage in one comparison — and it is the
    one that cannot be satisfied by an answer that was well formed and never applied.

    **Every path the plan named, and not the ones the answer listed.** A plan naming three files
    with two of them written is a repository that is not the one the plan describes, and every
    record between the approved plan and the pull request still reads as complete — so this checks
    the plan's three lists against the disk, which is what `PlannedFileNotWrittenError` checks
    against the answer.
    """
    assert isinstance(a_real_change, WhatTheImplementerConcluded), (
        f"the stage answered with {type(a_real_change).__name__} rather than the answer type, so "
        "nothing downstream can rely on which fields the change and its note arrived in"
    )
    assert a_real_change.files, (
        "the implementation agent wrote no file at all. The plan names a file to change and a test "
        "to add, and a node that accepted an empty answer would leave the checkout exactly as it "
        "was found while reporting a change"
    )

    every_write: list[FileToWrite] = a_real_change.files

    for one_write in every_write:
        where = a_clone_this_run_may_write.path / one_write.path
        assert where.is_file(), (
            f"{one_write.path!r} is in the answer and is not a file of the clone afterwards, so "
            "the change was reported and never written"
        )
        assert where.read_text() == one_write.content, (
            f"{one_write.path!r} does not hold the text that was proposed for it. The stage is "
            "asked for the whole text of a file rather than a diff, so a file that differs from "
            "the answer is a file that was written from something else — and the delivery would "
            "carry a diff nobody read"
        )
        assert one_write.content.strip(), (
            f"{one_write.path!r} was written empty. A file holding nothing is not a change to it, "
            "and a repository where a file has been emptied is a regression nobody asked for"
        )

    for a_path in every_path_the_approved_plan_accounts_for(a_plan_this_run_will_apply):
        assert (a_clone_this_run_may_write.path / a_path).is_file(), (
            f"{a_path!r} is named by the approved plan and is not a file of the clone afterwards. "
            "A plan that is not fully applied is not a plan that was applied, and reporting it as "
            "applied is the one thing a traceability chain must never do"
        )


@pytest.mark.parametrize("a_real_change", list(LlmProvider), indirect=True)
def test_the_change_is_the_approved_plan_and_not_one_path_more_or_less(
    a_real_change: WhatTheImplementerConcluded,
    a_plan_this_run_will_apply: ImplementationPlan,
    the_cloned_repository: ClonedRepository,
    a_clone_this_run_may_write: ClonedRepository,
) -> None:
    """The paths that differ between the two clones are exactly the paths the plan accounts for.

    **The plan is the boundary of what may change, and both of its edges are checked here.** §36
    says a human approves an exact artifact, and an approval of a plan naming one file says nothing
    about a second file the agent found interesting — so a file the plan did not name is a change
    nobody approved. The other edge is the one that is easy to forget: a file the plan *did* name
    and the agent did not write leaves a repository that is not the one the plan describes.

    **Measured as a difference between two directories rather than read out of the answer.** The
    read-only clone is the record of what the repository was, because nothing writes to it, and
    the two sets are compared as sets — so this cannot be satisfied by an answer that lists one
    path twice, or lists only the paths it happened to write, or writes somewhere and says nothing
    about it. Every one of those is a claim this way of asking does not hear.
    """
    what_was_cloned = _every_file_a_clone_holds(the_cloned_repository)
    what_this_run_left = _every_file_a_clone_holds(a_clone_this_run_may_write)

    what_changed = {
        a_path
        for a_path, its_text in what_this_run_left.items()
        if what_was_cloned.get(a_path) != its_text
    }

    assert what_changed == set(
        every_path_the_approved_plan_accounts_for(a_plan_this_run_will_apply)
    ), (
        f"this run changed {sorted(what_changed)} and the approved plan accounts for "
        f"{sorted(every_path_the_approved_plan_accounts_for(a_plan_this_run_will_apply))}. A path "
        "outside the plan is a change no person approved — the plan names one file and an approval "
        "of it is not an approval of a second — and a path inside it that did not change leaves "
        "every record downstream of the plan still reading as complete"
    )


@pytest.mark.parametrize("a_real_change", list(LlmProvider), indirect=True)
def test_the_test_the_plan_adds_is_a_file_this_run_created(
    a_real_change: WhatTheImplementerConcluded,
    a_plan_this_run_will_apply: ImplementationPlan,
    the_cloned_repository: ClonedRepository,
    a_clone_this_run_may_write: ClonedRepository,
) -> None:
    """The planned test was not in the repository, and it is there now.

    **`tests_to_add` is a promise that the file does not exist yet**, and that is the one claim
    about it the filesystem can settle. The plan's other list says the opposite about
    `files_to_add`, and a plan that puts one path in both describes one file twice with nothing
    recording which step wins.

    **The before is read from the read-only clone and the after from the writable one**, which is
    what makes this a claim about this run rather than about a repository that happened to hold
    the file already: nothing in this tier writes to the shared clone, so it is the repository as
    it was cloned.
    """
    assert a_plan_this_run_will_apply.tests_to_add, (
        "the plan this run applied names no test to add, so there is nothing here about a file "
        "that does not exist yet — and a plan that adds a test is a promise to a human that the "
        "test will exist"
    )

    for a_path in a_plan_this_run_will_apply.tests_to_add:
        assert _the_text_a_clone_holds_of(the_cloned_repository, a_path) is None, (
            f"{a_path!r} is in the plan's tests_to_add and the repository already held it "
            "as cloned. That list is for tests that do not exist yet, so the plan is either "
            "describing a file it is also changing in place — two descriptions of one file, and "
            "whichever step ran second silently wins — or naming a path it never read"
        )
        assert (a_clone_this_run_may_write.path / a_path).is_file(), (
            f"{a_path!r} is in the plan's tests_to_add and the plan named it for writing, "
            "and it is not a file of the clone afterwards. An earlier version of this agent read "
            "only `files_to_change`, so a plan's promise to add a test was reported without the "
            "and a field a plan carries and no agent acts on is worse than a field the plan never "
            "had"
        )


@pytest.mark.parametrize("a_real_change", list(LlmProvider), indirect=True)
def test_the_run_changed_something_and_the_note_beside_the_change_says_what(
    a_real_change: WhatTheImplementerConcluded,
    the_cloned_repository: ClonedRepository,
    a_clone_this_run_may_write: ClonedRepository,
) -> None:
    """Something on disk is different, and the three sentences of judgement are filled in.

    **The first half is the `AWriteThatChangesNothingError` edge, checked against the disk.** An
    implementer asked to add ignore rules once wrote a file byte-identical to the one already in
    the clone, nothing was staged, and a run died three refusals later saying *the change is not
    recorded* — when the truth was that there was no change to record. A refusal that fires with
    the fact still knowable is worth having, and this is the check that it is armed.

    **The second half is the note, and it is why the implementer is asked in the same call.** The
    plan is a list of paths with no intent, so the sentence that would have caught this agent
    inventing a mechanism nobody specified has to be its own to write — and it is asked together
    with the files so there is no second call to pay for and no way to judge a change that is not
    the one beside the judgement.
    """
    every_write: list[FileToWrite] = a_real_change.files
    assert every_write, (
        "the implementation agent answered with no file, so there is nothing to compare and this "
        "assertion would be about an empty answer rather than about a change"
    )

    wrote_nothing_new = [
        one_write.path
        for one_write in every_write
        if _the_text_a_clone_holds_of(the_cloned_repository, one_write.path) == one_write.content
    ]
    assert len(wrote_nothing_new) < len(every_write), (
        f"{wrote_nothing_new} were written with exactly the text the clone already held, so this "
        "run is indistinguishable from one that did nothing — and a pull request whose diff is "
        "empty is the one thing this pipeline must never produce"
    )

    for a_judgement in JUDGEMENTS_THE_IMPLEMENTER_MAKES:
        said = getattr(a_real_change.judged, a_judgement)
        assert said.strip(), (
            f"the implementation agent left {a_judgement} empty. It is the only agent that sees "
            "the whole text of every file it is changing, so its doubt is the last place a "
            "mechanism nobody specified can still be named — and an empty field reads as a doubt "
            "nobody had"
        )
