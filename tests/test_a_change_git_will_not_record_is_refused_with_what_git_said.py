"""That a change git will not record is refused with git's own words.

**This refusal has production evidence and no test.** `AWriteThatChangesNothingError`'s own
docstring records how it came to exist:

> an implementer asked to add ignore rules wrote a file byte-identical to the one already in
> the clone, `git add` staged nothing, `git commit` answered *nothing to commit, working tree
> clean*, and the run raised `TheChangeWasNotCommittedError` - which says the change is not
> recorded, when the truth is that there was no change to record.

**And the test that would have caught it earlier was never written.** Across the whole package,
**four refusals are raised and no test names any of them**; this is the one with a run behind it.

**The refusal carries git's own words, and that is the half worth pinning.** A reader holding
*git refused* has to go and find out why, and the answer is already on the terminal. `git commit`
saying *nothing to commit, working tree clean* and `git push` saying *permission denied* are two
different problems for a person to act on, and a refusal that says only that git refused has thrown
the second one away.

**Real git, and the failure is produced rather than described.** A stub would assert that a command
was handed an argument; what has to be shown is that **git itself answers that way**, which is why
this repository does not stub `git` anywhere it can help.

**The change is already on the disk**, so the commit has nothing to record - which is precisely the
state the run reached, and it is also the state a person would find after an agent wrote a file
byte-identical to the one already there.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aisdlc.agents.a_commit_recording_the_change import (
    TheChangeWasNotCommittedError,
    a_commit_recording_the_change,
)
from aisdlc.agents.implementation_plan import ImplementationPlan

THE_FILE_THE_PLAN_NAMED = ".gitignore"
WHAT_THE_CLONE_ALREADY_HOLDS = "e2e.db-wal\n"


def _git(where: Path, *words: str) -> None:
    subprocess.run(["git", *words], cwd=where, check=True, capture_output=True)


def _a_clone_whose_change_is_already_there(where: Path) -> Path:
    """A real repository where the plan's file is committed, so there is nothing left to record.

    **The file is committed in the setup and not written afterwards**, because the state a commit
    refuses is "the working tree holds nothing new" - which needs a repository with history, not a
    file written into a working tree that git has not been told about.
    """
    where.mkdir(parents=True, exist_ok=True)
    _git(where, "init", "--quiet", "--initial-branch=main")
    (where / THE_FILE_THE_PLAN_NAMED).write_text(WHAT_THE_CLONE_ALREADY_HOLDS)
    _git(where, "add", "--", THE_FILE_THE_PLAN_NAMED)
    _git(where, "-c", "user.email=a-person@example.com", "-c", "user.name=a person",
         "commit", "--quiet", "-m", "already there")
    return where


def test_a_commit_git_will_not_make_is_refused_with_what_git_said(tmp_path: Path) -> None:
    """Nothing to commit is refused, and the refusal carries git's own sentence.

    **The message is what a person acts on after a long run**, so it is asserted rather than
    which problem this is.
    """
    the_clone = _a_clone_whose_change_is_already_there(tmp_path / "the-clone")
    a_plan = ImplementationPlan(files_to_change=[THE_FILE_THE_PLAN_NAMED])

    with pytest.raises(TheChangeWasNotCommittedError) as it_raised:
        a_commit_recording_the_change(the_clone, a_plan, "a change the run verified")

    the_refusal = str(it_raised.value)

    assert "nothing to commit" in the_refusal.lower(), (
        "the refusal does not carry what git said, so whoever holds it has to go and reproduce the "
        f"commit to find out why. git said *nothing to commit, working tree clean* and the "
        f"refusal says: {the_refusal}"
    )
    assert "not recorded" in the_refusal, (
        f"the refusal does not say the change is not recorded, which is the half that tells a "
        f"reader a delivery would push a branch carrying nothing. It says: {the_refusal}"
    )


def test_a_change_that_is_recorded_is_not_refused(tmp_path: Path) -> None:
    """The half the first test cannot show, because a test that only ever refuses is green.

    **A new file, which `git add` genuinely has something to stage** - the one shape where the two
    commands in this function have work to do.
    """
    the_clone = _a_clone_whose_change_is_already_there(tmp_path / "the-clone")
    a_new_file = "tests/unit/a-run-wrote-this.test.ts"
    (the_clone / "tests" / "unit").mkdir(parents=True)
    (the_clone / a_new_file).write_text("it('was here', () => {})\n")

    the_commit = a_commit_recording_the_change(
        the_clone, ImplementationPlan(tests_to_add=[a_new_file]), "a test this run wrote"
    )

    what_the_commit_is = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=the_clone,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert the_commit.standard_output.strip() == what_the_commit_is, (
        f"the commit the caller was handed is {the_commit.standard_output.strip()!r} while the "
        f"clone stands on {what_the_commit_is!r}, so a caller reporting the delivery would report "
        "a commit the branch does not carry"
    )
