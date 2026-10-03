"""That the question "is this change observed?" is refused rather than asked about nothing.

**A run refused a real change with `ATestThatPassesWithoutTheChangeError`, and the refusal was
false.** Four of the six real-tier runs on this repository ended in it, always at the same
assertion and always with the same words, and the log holds the reason:

```text
files_to_change=['package.json']
1 file changed, 29 insertions(+)
```

**The plan named `package.json` and the commit changed something else.** `git show` of that file
at the commit and at its parent returns byte-identical text, so the commit never touched the file
the plan named.

**Which makes the putting back a no-op.** `_the_suite_with_the_change_put_back` runs

```python
git checkout HEAD~1 -- <the files the plan named>
```

and for a file the commit did not change that command succeeds and writes nothing. So the third
question — *does anything observe this change?* — is asked over a checkout that still holds the
change in full, and the run reads the answer as *no, nothing observes it*, and refuses the work.

**It refused a change for a reason that was an artefact of its own command.** Nothing is wrong
with the change; the change is not in the file the plan named, and the checkout had nothing to
take back.

**And this is why it failed four times in six rather than always**: whether the plan names the file
the commit changed is a model's answer. Two runs in six named it, and those passed.

**The refusal belongs before the suite is asked, not after.** A suite run is the most expensive
thing this system does, and here it is spent on a question whose answer cannot mean anything. So
the guard is asked of the commit, not of the checkout's afterwards.

**Real git, and the failure is manufactured in the repository rather than described.** A stub
would let me assert that a comparison happened; what has to be shown is that `git` itself calls two
checkouts identical, which is the whole claim.

**This file asserts a refusal and what it says, and not a class.** The named error arrives with the
behaviour, and a RED that would not import is a RED that failed for the wrong reason — so the
demand here is the one a reader of a traceback has, which is what the sentence tells them.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aisdlc.agents.apply_the_plan import _the_suite_with_the_change_put_back
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.domain.repository import Repository
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.run_tests import SuiteOutcome

THE_FILE_THE_PLAN_NAMED = "package.json"
THE_FILE_THE_COMMIT_CHANGED = "tests/unit/a-test-the-run-wrote.test.ts"
THE_REPOSITORY = Repository(owner="paligakrzychu", name="wellbeing-tracker-public")


def _git(where: Path, *words: str) -> None:
    subprocess.run(["git", *words], cwd=where, check=True, capture_output=True)


def _a_clone(where: Path) -> Path:
    """A real repository with an identity of its own, because a machine may have none."""
    where.mkdir(parents=True)
    _git(where, "init", "--quiet", "--initial-branch=main")
    _git(where, "config", "user.email", "a-person@example.com")
    _git(where, "config", "user.name", "a person")
    (where / THE_FILE_THE_PLAN_NAMED).write_text('{"name": "wellbeing-tracker"}\n')
    _git(where, "add", "--", THE_FILE_THE_PLAN_NAMED)
    _git(where, "commit", "--quiet", "-m", "the first version")
    return where


def _the_commit_the_clone_stands_on(the_clone: Path) -> str:
    """The clone's own `HEAD`, read from the clone rather than composed from anything."""
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=the_clone, check=True, capture_output=True, text=True
    ).stdout.strip()


def _a_clone_whose_commit_changed_a_file_the_plan_never_named(where: Path) -> Path:
    """A real repository, committed, where the plan's file is exactly as it was.

    **`git checkout HEAD~1 -- package.json` succeeds here and writes nothing**, which is the whole
    defect and is why this is built from real git rather than asserted about a list.
    """
    the_clone = _a_clone(where)
    (the_clone / "tests" / "unit").mkdir(parents=True)
    (the_clone / THE_FILE_THE_COMMIT_CHANGED).write_text("it('was here', () => {})\n")
    _git(the_clone, "add", "--", THE_FILE_THE_COMMIT_CHANGED)
    _git(the_clone, "commit", "--quiet", "-m", "the change the run really made")
    return the_clone


def _answering_without_the_change(
    the_clone: Path,
    a_suite: object,
    files_the_plan_named: list[str],
) -> object:
    """The real closure, wired to a real clone and a real repository.

    **Built here rather than at both call sites** because the two tests differ only in what the
    commit holds and in what the suite does, and a helper that takes both makes that visible.
    """
    return _the_suite_with_the_change_put_back(
        ClonedRepository(
            path=the_clone,
            ref="main",
            commit=_the_commit_the_clone_stands_on(the_clone),
        ),
        THE_REPOSITORY,
        ImplementationPlan(files_to_change=files_the_plan_named),
        a_suite,  # type: ignore[arg-type]
    )


def test_a_change_in_none_of_the_files_the_plan_named_is_refused_by_name(tmp_path: Path) -> None:
    """The commit holds none of the plan's files, so the question has nothing to put back.

    **The suite must not be run, and that is the half of this that matters.** Everything else is
    free; a suite run against a checkout that still has the change in it is the most expensive way
    to learn nothing, and this run learned nothing and then refused the work over it.
    """
    the_clone = _a_clone_whose_commit_changed_a_file_the_plan_never_named(tmp_path / "the-clone")
    the_suite_was_asked_about: list[str] = []

    def a_suite_that_records_being_asked(
        clone: ClonedRepository, repository: Repository
    ) -> SuiteOutcome:
        """Answer, and record that it was asked at all — being asked is half of what is wrong."""
        the_suite_was_asked_about.append((clone.path / THE_FILE_THE_PLAN_NAMED).read_text())
        return SuiteOutcome(
            exit_code=0, passed=True, dependencies_installed=True, output="88 passed"
        )

    with pytest.raises(Exception) as it_raised:
        _answering_without_the_change(
            the_clone, a_suite_that_records_being_asked, [THE_FILE_THE_PLAN_NAMED]
        )()

    the_refusal = str(it_raised.value)

    assert the_suite_was_asked_about == [], (
        f"the suite was asked {len(the_suite_was_asked_about)} times about a change that is in "
        "none of the files the plan named, so it was answered on a checkout that still held the "
        "change in full. That is the most expensive way to learn nothing"
    )
    assert THE_FILE_THE_PLAN_NAMED in the_refusal, (
        f"the refusal does not name {THE_FILE_THE_PLAN_NAMED!r}, so whoever holds it has to go and "
        f"find which of the plan's files the commit missed. It says: {the_refusal}"
    )
    assert THE_FILE_THE_COMMIT_CHANGED in the_refusal, (
        f"the refusal does not name {THE_FILE_THE_COMMIT_CHANGED!r}, which is the file the commit "
        "really changed. A refusal that names what was asked for and not what was done leaves the "
        f"reader to diff the commit themselves, which is the work the refusal exists to save. It "
        f"says: {the_refusal}"
    )


def test_a_change_in_a_file_the_plan_named_is_still_answered(tmp_path: Path) -> None:
    """The half this guard must not cost, and the only way to show it costs nothing.

    **Without this, a guard that refused everything would be green.** That is not a hypothetical:
    refusing by default is how a real run in this repository was handed a collaborator that did
    not exist, and nobody found out for twenty minutes.
    """
    the_clone = _a_clone(tmp_path / "the-clone")
    (the_clone / THE_FILE_THE_PLAN_NAMED).write_text('{"name": "wellbeing-tracker", "x": 1}\n')
    _git(the_clone, "commit", "--quiet", "-am", "the change, in the file the plan named")

    the_suite_was_asked_about: list[str] = []

    def a_suite_that_records_being_asked(
        clone: ClonedRepository, repository: Repository
    ) -> SuiteOutcome:
        """Read the clone as it stands while the question is being asked, and answer."""
        the_suite_was_asked_about.append((clone.path / THE_FILE_THE_PLAN_NAMED).read_text())
        return SuiteOutcome(
            exit_code=0, passed=True, dependencies_installed=True, output="88 passed"
        )

    the_answer = _answering_without_the_change(
        the_clone,
        a_suite_that_records_being_asked,
        [THE_FILE_THE_PLAN_NAMED],
    )()

    assert the_answer.passed, "this run's suite was green, and the guard is not about verdicts"
    assert len(the_suite_was_asked_about) == 1, (
        f"the suite ran {len(the_suite_was_asked_about)} times"
    )
