"""That the run answers "is this change observed?" inside the clone, and not beside it.

**A `git checkout` with no working directory acts on whatever repository the process is standing
in.** A run is a process, and the process's directory is the repository that launched it — the one
this system lives in. So the command that takes the change back out, runs the suite, and puts the
change back, ran `git checkout HEAD~1 -- .github/workflows/ci.yml` against *this* repository, where
no such path exists, and was answered:

    error: pathspec '.github/workflows/ci.yml' did not match any file(s) known to git

**Found by a real run, and the run died on it.** Run 11 got through six gates, the implementer
wrote two files, committed, and `npm ci` + `npm test` reported **79 passed, 9 skipped**. Then the
step meant to prove the new guard test *fails* without the change did nothing at all — in the
wrong repository — and the restore afterwards did nothing either, so the suite was green on both
sides of a checkout that never happened and the run could not show its change was observed.

**And it is worse than a failed command.** `git checkout <revision> -- <paths>` is a write. This
one was aimed at the wrong repository by a rule that never says which repository it is aiming at,
and the only thing that stopped it from rewriting a file in this repository is that the path did
not exist here. The sibling that commits the change *does* pass `working_directory`; this call
site was missed, and nothing compares them.

**What the runner reads, and not what is on disk afterwards.** The change is put back in a
`finally` because leaving it undone would drop the work from the pull request — so after the run
the clone is correct whichever repository the checkout ran in, and asserting on that would have
passed against the defect. The one moment that distinguishes them is while the suite is being
answered, which is why the runner in this test reads the clone's file and hands the reading back
rather than letting the test look at it afterwards.

**Real git, and the process moved, because a stub would assert the wrong thing.** Stubbing
`the_outcome_of` would check that an argument was passed, not that a command landed in the clone.
Two real repositories with real commits, and the process standing in the wrong one on purpose —
which is the situation every real run is in.
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

THE_FILE = ".github/workflows/ci.yml"
THE_FIRST_VERSION = "the first version\n"
THE_CHANGE = "the change, committed\n"
THE_REPOSITORY = Repository(owner="paligakrzychu", name="wellbeing-tracker-public")


def _git(where: Path, *words: str) -> None:
    subprocess.run(["git", *words], cwd=where, check=True, capture_output=True)


def _a_repository_that_can_commit(where: Path) -> None:
    """Give a repository an identity, because committing needs one and a machine may have none.

    **This was found by CI and not here.** `git clone` does not carry a local identity across, so
    the clone's `git commit` was left with no `user.name` and no `user.email` — and it exited 128
    on the runner while passing on the machine that ran it, because that machine had a global
    identity. A test that needs somebody's git configuration to pass is a test that reports the
    machine rather than the code, so every repository here is given its own.
    """
    _git(where, "config", "user.email", "a-person@example.com")
    _git(where, "config", "user.name", "a person")


def _an_origin_with_one_version_of_the_file(where: Path) -> Path:
    """A real git repository with one commit putting one file on disk.

    **It commits, because the command under test checks a file out of `HEAD~1`.** A repository
    with no parent commit has nothing to check out, and a test that passed for that reason would
    have proved nothing.
    """
    (where / ".github" / "workflows").mkdir(parents=True)
    _git(where, "init", "--quiet", "--initial-branch=main")
    _a_repository_that_can_commit(where)
    (where / THE_FILE).write_text(THE_FIRST_VERSION)
    _git(where, "add", "--", THE_FILE)
    _git(where, "commit", "--quiet", "-m", "the first version")
    return where


def _a_repository_standing_here_and_nothing_to_do_with_the_clone(where: Path) -> Path:
    """A second real repository, which is where a run's process is standing.

    **Empty of the file under test, on purpose.** If it held `.github/workflows/ci.yml` the
    checkout could succeed here and the run would have proved nothing while looking as though it
    had; the path being absent is what makes the wrong repository answer with an error rather
    than with a file.
    """
    where.mkdir(parents=True)
    _git(where, "init", "--quiet", "--initial-branch=main")
    _a_repository_that_can_commit(where)
    (where / "a-file-that-does-not-matter").write_text("a person was here first\n")
    _git(where, "add", "--", "a-file-that-does-not-matter")
    _git(where, "commit", "--quiet", "-m", "the repository this process stands in")
    return where


def test_the_change_is_taken_back_inside_the_clone_and_not_where_the_process_stands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The suite is answered on the clone without the change, wherever the process is standing."""
    _an_origin_with_one_version_of_the_file(tmp_path / "the-origin")
    the_clone = tmp_path / "the-clone"
    _git(tmp_path, "clone", "--quiet", str(tmp_path / "the-origin"), str(the_clone))
    _a_repository_that_can_commit(the_clone)
    (the_clone / THE_FILE).write_text(THE_CHANGE)
    _git(the_clone, "add", "--", THE_FILE)
    _git(the_clone, "commit", "--quiet", "-m", "the change")

    where_the_process_stands = _a_repository_standing_here_and_nothing_to_do_with_the_clone(
        tmp_path / "the-repository-this-process-stands-in"
    )
    monkeypatch.chdir(where_the_process_stands)

    what_the_suite_was_answered_with: list[str] = []

    def the_suite_that_reads_the_clone(
        clone: ClonedRepository, repository: Repository
    ) -> SuiteOutcome:
        """Read the clone as it stands at the moment the suite is asked, and refuse to answer.

        **It refuses rather than answering, because the answer is not what this test reads.** The
        run puts the change back in a `finally`, so anything returned here would be discarded; a
        refusal ends the closure at the one moment whose state is in question.
        """
        what_the_suite_was_answered_with.append((clone.path / THE_FILE).read_text())
        raise AssertionError("this test is about what the suite was answered on, not its verdict")

    answering_without_the_change = _the_suite_with_the_change_put_back(
        ClonedRepository(
            path=the_clone,
            ref="main",
            commit=_the_commit_the_clone_stands_on(the_clone),
        ),
        THE_REPOSITORY,
        ImplementationPlan(files_to_change=[THE_FILE]),
        the_suite_that_reads_the_clone,
    )

    with pytest.raises(AssertionError):
        answering_without_the_change()

    assert what_the_suite_was_answered_with == [THE_FIRST_VERSION], (
        f"the suite was answered on {what_the_suite_was_answered_with!r} rather than on the "
        f"clone's first version. The change was taken back in {where_the_process_stands} instead "
        f"of in the clone at {the_clone}, so a suite that never ran without the change was "
        "answered on the same files twice, and nothing proved the change was observed"
    )


def _the_commit_the_clone_stands_on(the_clone: Path) -> str:
    """The clone's own `HEAD`, read from the clone rather than composed from anything."""
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=the_clone, check=True, capture_output=True, text=True
    ).stdout.strip()
