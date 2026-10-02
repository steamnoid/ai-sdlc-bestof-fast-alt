"""That the run answers "is this change observed?" inside the clone, and not beside it.

**A `git checkout` with no working directory acts on whatever repository the process is standing
in.** The run is a process, and the process's directory is the repository that launched it — the
one this system lives in. So the command that takes the change back out, runs the suite, and puts
the change back, ran `git checkout HEAD~1 -- .github/workflows/ci.yml` against *this* repository,
where no such path exists, and was answered:

    error: pathspec '.github/workflows/ci.yml' did not match any file(s) known to git

**Found by a real run, and the run died on it.** Run 11 got through six gates, the implementer
wrote two files, committed, and `npm ci` + `npm test` reported **79 passed, 9 skipped**. Then the
step meant to prove the new guard test *fails* without the change did nothing at all — in the
wrong repository — and the restore afterwards did nothing either, so the run could not show its
change was observed and stopped at the supervisor. The suite was green on both sides of a checkout
that never happened.

**And it is worse than a failed command.** `git checkout <revision> -- <paths>` is a write. This
one was aimed at the wrong repository on purpose, by a rule that never says which repository it is
aiming at, and the only thing that stopped it from rewriting a file in this repository was that
the path did not exist here. The author of the sibling that commits the change *does* pass
`working_directory`; this call site was missed, and nothing compares them.

**Why the test moves the process rather than mocking anything.** The bug is a missing argument to
`subprocess.run`, so a test that stubs `the_outcome_of` would assert the argument was passed
rather than that the command lands somewhere. This moves the working directory to a second real
repository with real commits and asks whether the clone's file changed. It is the property a reader
of the code wants, and it fails today for the same reason the run failed.
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
THE_REPOSITORY = Repository(owner="paligakrzychu", name="wellbeing-tracker-public")


def _an_origin_with_one_version_of_the_file(where: Path) -> Path:
    """A real git repository with one commit putting one file on disk.

    **Real git rather than a stub, because the assertion is about which repository a command acts
    on and a fake repository cannot be acted on.** It commits, because the command under test
    checks a file out of `HEAD~1` — a repository with no parent commit has nothing to check out,
    and a test that passed for that reason would have proved nothing.
    """
    (where / ".github" / "workflows").mkdir(parents=True)
    _git(where, "init", "--quiet", "--initial-branch=main")
    _git(where, "config", "user.email", "a-person@example.com")
    _git(where, "config", "user.name", "a person")
    (where / THE_FILE).write_text("the first version\n")
    _git(where, "add", "--", THE_FILE)
    _git(where, "commit", "--quiet", "-m", "the first version")
    return where


def _git(where: Path, *words: str) -> None:
    subprocess.run(["git", *words], cwd=where, check=True, capture_output=True)


def _the_suite_never_run(clone: ClonedRepository, repository: Repository) -> SuiteOutcome:
    """A runner that never runs, because this test is about where the checkout went.

    **And it says so by running nothing at all.** A runner that answered would answer *after* the
    checkout, which is the moment this test reads — so the outcome it produces is never read and
    returning one would be a claim rather than an answer.
    """
    raise AssertionError(
        "this test is about where the change is taken back to, and a suite was run instead"
    )


def test_the_change_is_taken_back_inside_the_clone_and_not_where_the_process_stands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The file goes back to its first version in the clone, whatever directory the process is in.

    **The process is moved to a second repository on purpose.** If the checkout already carried its
    working directory this test would pass with the process left alone; moving it is what makes the
    test able to fail, and it is the situation every real run is in — `aisdlc run` is executed from
    this repository, and the clone it works on is somewhere else entirely.
    """
    elsewhere = tmp_path / "the-repository-this-process-stands-in"
    elsewhere.mkdir()
    _git(elsewhere, "init", "--quiet", "--initial-branch=main")
    _git(elsewhere, "config", "user.email", "a-person@example.com")
    _git(elsewhere, "config", "user.name", "a person")
    (elsewhere / "a-file-that-does-not-matter").write_text("a person was here first\n")
    _git(elsewhere, "add", "--", "a-file-that-does-not-matter")
    _git(elsewhere, "commit", "--quiet", "-m", "the repository this process stands in")

    _an_origin_with_one_version_of_the_file(tmp_path / "the-origin")

    the_clone = tmp_path / "the-clone"
    _git(tmp_path, "clone", "--quiet", str(tmp_path / "the-origin"), str(the_clone))
    (the_clone / THE_FILE).write_text("the change, committed\n")
    _git(the_clone, "add", "--", THE_FILE)
    _git(the_clone, "commit", "--quiet", "-m", "the change")

    monkeypatch.chdir(elsewhere)

    answering_without_the_change = _the_suite_with_the_change_put_back(
        ClonedRepository(path=the_clone, ref="main", commit="the-commit-the-clone-is-on"),
        THE_REPOSITORY,
        ImplementationPlan(files_to_change=[THE_FILE]),
        _the_suite_never_run,
    )

    with pytest.raises(AssertionError):
        answering_without_the_change()

    assert (the_clone / THE_FILE).read_text() == "the first version\n", (
        f"the change was taken back in {elsewhere} instead of in the clone at {the_clone}, so the "
        "suite was answered on the same files twice and nothing proved the change was observed. "
        f"The clone still holds {(the_clone / THE_FILE).read_text()!r}"
    )
