"""That a rebase lands this run's commit on the branch it joins, and nothing else moves.

**A pull request GitHub will not merge is a branch that has fallen behind the branch it joins, and
replaying it on top of that branch is the whole of the fix.** `merge_a_pull_request` reads
`mergeable: false` and refuses without asking, because GitHub words a conflict and a protected base
branch alike — so something has to act once the conflict has been established.

**Every address here is a remote's name, and that is the rule the whole thing turns on.** The
obvious way to fetch is to compose a URL, and a URL that needs a credential is a URL git prints
back inside its own error message. So the remotes are taken by name and nothing here reads the
environment.

**The branch may be moved only where this run left it, and git is what checks it.**
`create_a_branch_on_a_remote` refuses to push a branch that already exists on the remote, because a
run must never move a branch somebody else is using — and a rebase has to do precisely that, so
that refusal cannot be relaxed, it has to be stated precisely instead. **The commit the branch is
expected to be at is handed to git as a lease**, which git compares against the branch *inside the
same push* that would move it. A read beforehand would leave a window, and what that window admits
is a commit somebody else pushed in between, destroyed.

**Fetching before rebasing is not a detail.** A rebase onto a branch this run has not just read is
a rebase onto whatever the remote held at some earlier moment, and the rebase carries the
**expectation** the fetch was made under.

**A rebase that would change nothing is refused, and that refusal is what stops a run going round.**
A merge refused as a conflict sends the run to this repair; a rebase that changes nothing leaves the
pull request in front of the same `mergeable: false`; the run reaches the same repair again with the
same facts and walks to the recursion limit. **A decision taken once about a fact that has not
changed is not a decision.**

**A real git repository, because every claim here is about git.** A stub would assert that this
code calls a function; the claims are about what the branch holds afterwards, and a fake repository
has no branches.

**And the failing half keeps it honest:** one test drives a conflict git cannot resolve — both
sides changed the same line — and the clone is left as it was found, because a checkout stopped
mid-rebase carries a `.git/rebase-merge` that refuses the next `git` this run makes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aisdlc.tools.rebase_the_branch_a_run_pushed import rebase_the_branch_a_run_pushed
from aisdlc.tools.why_a_rebase_did_not_land import (
    TheBranchMovedUnderThisRunError,
    TheRebaseWasNotFinishedError,
    TheRebaseWouldChangeNothingError,
)

WHERE_THIS_RUNS_BRANCH_IS = "aisdlc/issue-1"
WHERE_IT_JOINS = "main"


def _git(where: Path, *words: str) -> str:
    """One `git` call in one directory, and its output."""
    return subprocess.run(
        ["git", *words], cwd=where, check=True, capture_output=True, text=True
    ).stdout


def _somebody_else_moves_main(
    tmp_path: Path, what_they_wrote: str, in_which_file: str = "a-file-they-added.md"
) -> None:
    """Push one commit onto `main` from a second clone, which is the ordinary case for a rebase."""
    upstream = tmp_path / "upstream.git"
    a_second_copy = tmp_path / "a-second-copy"
    _git(tmp_path, "clone", "--quiet", str(upstream), str(a_second_copy))
    _git(a_second_copy, "config", "user.email", "somebody-else@example.com")
    _git(a_second_copy, "config", "user.name", "somebody else")
    (a_second_copy / in_which_file).write_text(what_they_wrote, encoding="utf-8")
    _git(a_second_copy, "add", in_which_file)
    _git(a_second_copy, "commit", "-m", "somebody else's commit")
    _git(a_second_copy, "push", "--quiet", "origin", "main")


def _a_clone_with_a_pushed_branch(tmp_path: Path) -> tuple[Path, Path, str]:
    """A clone with `upstream` to join, `origin` to write to, and one commit of this run's.

    **A bare upstream plus a real clone rather than two directories**, because the whole tool is
    about what git does across a remote boundary and a local directory is not a remote.

    Returns the clone, the remote this run may write to, and the commit the branch is left on.
    """
    upstream = tmp_path / "upstream.git"
    upstream.mkdir()
    _git(upstream, "init", "--bare", "--initial-branch=main")

    a_first_copy = tmp_path / "a-first-copy"
    a_first_copy.mkdir()
    _git(a_first_copy, "init", "--initial-branch=main")
    _git(a_first_copy, "config", "user.email", "a-run@example.com")
    _git(a_first_copy, "config", "user.name", "a run")
    (a_first_copy / "README.md").write_text("# the project\n", encoding="utf-8")
    _git(a_first_copy, "add", "README.md")
    _git(a_first_copy, "commit", "-m", "the first commit")
    _git(a_first_copy, "remote", "add", "origin", str(upstream))
    _git(a_first_copy, "push", "origin", "main")

    where_this_run_may_write = tmp_path / "where-this-run-may-write.git"
    where_this_run_may_write.mkdir()
    _git(where_this_run_may_write, "init", "--bare", "--initial-branch=main")

    the_clone = tmp_path / "the-clone"
    _git(tmp_path, "clone", "--quiet", str(upstream), str(the_clone))
    _git(the_clone, "config", "user.email", "aisdlc@localhost")
    _git(the_clone, "config", "user.name", "aisdlc-dev-impl")
    _git(the_clone, "remote", "rename", "origin", "upstream")
    _git(the_clone, "remote", "add", "origin", str(where_this_run_may_write))
    _git(the_clone, "checkout", "--quiet", "-b", WHERE_THIS_RUNS_BRANCH_IS)
    (the_clone / "health.py").write_text("def health():\n    return 'this run'\n", encoding="utf-8")
    _git(the_clone, "add", "health.py")
    _git(the_clone, "commit", "-m", "the change this run pushed")
    the_commit = _git(the_clone, "rev-parse", "HEAD").strip()
    _git(the_clone, "push", "--quiet", "origin", f"HEAD:refs/heads/{WHERE_THIS_RUNS_BRANCH_IS}")

    return the_clone, where_this_run_may_write, the_commit


def _what_the_remote_holds_at(where: Path, a_branch: str, a_path: str) -> str:
    """The contents of one file on one branch **on the remote**, read without checking it out."""
    return _git(where, "show", f"{a_branch}:{a_path}")


def test_a_rebase_lands_this_runs_commit_on_the_branch_it_joins(tmp_path: Path) -> None:
    """After the rebase the branch carries both this run's file and the file it joined behind.

    **Read from the remote and not from the clone**, because the clone is where the rebase
    happened and the remote is where the result is a fact. A rebase that stayed local would pass
    every test that looked at the working tree — and the working tree is not what anybody merges.
    """
    the_clone, where_this_run_may_write, the_commit = _a_clone_with_a_pushed_branch(tmp_path)
    _somebody_else_moves_main(tmp_path, "theirs\n")

    what_landed = rebase_the_branch_a_run_pushed(
        the_clone, the_commit, WHERE_THIS_RUNS_BRANCH_IS, WHERE_IT_JOINS
    )

    assert (
        _what_the_remote_holds_at(where_this_run_may_write, WHERE_THIS_RUNS_BRANCH_IS, "health.py")
        == "def health():\n    return 'this run'\n"
    ), "the branch this run pushed no longer holds the change it delivered, on the remote"

    assert (
        _what_the_remote_holds_at(
            where_this_run_may_write, WHERE_THIS_RUNS_BRANCH_IS, "a-file-they-added.md"
        )
        == "theirs\n"
    ), (
        "the branch this run pushed does not hold the commit it joined behind. A rebase that lost "
        "somebody else's work would be a delivery that removed it from somebody's repository"
    )

    assert what_landed.commit != the_commit, (
        f"the rebase reported landing {what_landed.commit}, which is the commit it already had. A "
        "rebase that changes nothing is a decision taken again about a fact that has not changed"
    )


def test_a_rebase_git_cannot_finish_leaves_the_clone_as_it_was_found(tmp_path: Path) -> None:
    """Both sides changed the same line, and the clone is still usable afterwards.

    **The next `git` command is the assertion.** A checkout stopped mid-rebase carries a
    `.git/rebase-merge` that refuses the next `git` this run makes, and the clone is the whole of a
    run's state — so a tool that leaves one behind has destroyed the run rather than failed it.
    """
    the_clone, _, the_commit = _a_clone_with_a_pushed_branch(tmp_path)
    _somebody_else_moves_main(
        tmp_path, "def health():\n    return 'theirs'\n", in_which_file="health.py"
    )

    with pytest.raises(TheRebaseWasNotFinishedError) as it_raised:
        rebase_the_branch_a_run_pushed(
            the_clone, the_commit, WHERE_THIS_RUNS_BRANCH_IS, WHERE_IT_JOINS
        )

    assert "health.py" in str(it_raised.value), (
        f"the refusal does not name the file git could not merge, and git is the only thing here "
        f"that can say which one it was: {it_raised.value}"
    )

    _git(the_clone, "status", "--short")

    assert not (the_clone / ".git" / "rebase-merge").exists(), (
        "the clone was left mid-rebase. A .git/rebase-merge refuses the next git command this run "
        "makes, and the clone is the whole of a run's state"
    )


def test_a_branch_that_moved_under_this_run_is_refused_by_the_lease(tmp_path: Path) -> None:
    """Git compares the lease inside the same push that would move the branch.

    **A lease and not a read**, because a read leaves a window between itself and the push, and
    what that window admits is a commit somebody else pushed in between, destroyed. So the tool is
    handed a commit the branch is *not* on, which is exactly what a window looks like from here.
    """
    the_clone, _, _ = _a_clone_with_a_pushed_branch(tmp_path)
    _somebody_else_moves_main(tmp_path, "theirs\n")

    with pytest.raises(TheBranchMovedUnderThisRunError) as it_raised:
        rebase_the_branch_a_run_pushed(
            the_clone, "0" * 40, WHERE_THIS_RUNS_BRANCH_IS, WHERE_IT_JOINS
        )

    assert WHERE_THIS_RUNS_BRANCH_IS in str(it_raised.value), (
        f"the refusal does not name the branch that moved: {it_raised.value}"
    )


def test_a_rebase_that_would_change_nothing_is_refused(tmp_path: Path) -> None:
    """The branch is already on top of the branch it joins, and there is nothing to replay.

    **This is what stops a run going round.** A merge refused as a conflict sends the run to this
    repair; a rebase that changes nothing leaves the pull request in front of the same
    `mergeable: false`, the run reaches this repair again with the same facts, and it walks to the
    recursion limit.
    """
    the_clone, _, the_commit = _a_clone_with_a_pushed_branch(tmp_path)
    _git(the_clone, "fetch", "--quiet", "upstream", WHERE_IT_JOINS)

    with pytest.raises(TheRebaseWouldChangeNothingError) as it_raised:
        rebase_the_branch_a_run_pushed(
            the_clone, the_commit, WHERE_THIS_RUNS_BRANCH_IS, WHERE_IT_JOINS
        )

    assert WHERE_THIS_RUNS_BRANCH_IS in str(it_raised.value), (
        f"the refusal does not name the branch there was nothing to do about: {it_raised.value}"
    )
