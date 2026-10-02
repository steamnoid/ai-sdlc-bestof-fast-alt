"""`git.rebase_the_branch_a_run_pushed`: the one repair a conflicting delivery can take.

**A pull request GitHub will not merge is a branch that has fallen behind the branch it joins, and
replaying it on top of that branch is the whole of the fix.** `merge_a_pull_request` reads
`mergeable: false` and refuses without asking, because GitHub words a conflict and a protected base
branch alike — so something has to act on the conflict once it has been established. This is that
something, and it is the action behind *"rebase it and try again"*.

**Three `git` calls and a decision between them, and the order is the argument.** The branch it
joins is fetched, the rebase is carried out against what was fetched, and the result is put on the
remote with the **lease** it was fetched under. Fetching before rebasing is not a detail: a rebase
onto a branch this run has not just read is a rebase onto whatever the remote held at some earlier
moment.

**Every address here is a remote's name, and that is the rule the whole module turns on.** `origin`
is the copy this run may write to and the branch it delivered is on it; `upstream` is where the
branch it joins lives. The obvious way to fetch is to compose a URL, and **a URL that needs a
credential is a URL git prints back inside its own error message** — which is where this
repository's error messages come from.

**The branch may be moved only where this run left it, and git is what checks it.** The commit the
branch is expected to be at is handed to git as a lease, which git compares against the branch
inside the same push that would move it.

**A rebase git cannot finish leaves the clone as it found it.** A checkout stopped mid-rebase
carries a `.git/rebase-merge` that refuses the next `git` command this run makes, and the
of a run's state. So the abort belongs to the refusal rather than to a caller's memory of it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from aisdlc.tools.why_a_rebase_did_not_land import (
    TheBranchMovedUnderThisRunError,
    TheRebaseWasNotFinishedError,
)

WHERE_THIS_RUNS_BRANCH_LIVES = "origin"
WHERE_THE_BRANCH_IT_JOINS_LIVES = "upstream"
SECONDS_A_GIT_CALL_MAY_TAKE = 60


class WhatTheRebaseLanded(BaseModel):
    """The commit now on the branch, and what git said when it put it there.

    **Frozen and `extra="forbid"`**, for the reason every answer type in this package is: a fact
    this system did not ask for is one no human was ever shown. The sentence is git's own, carried
    verbatim, because a system that paraphrases a remote's confirmation can be wrong about a
    rebase having happened.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    commit: str
    what_git_said: str


def rebase_the_branch_a_run_pushed(
    the_clone: Path,
    the_commit_this_run_left_the_branch_on: str,
    this_runs_branch: str,
    the_branch_it_joins: str,
) -> WhatTheRebaseLanded:
    """Replay this run's branch on the branch it joins, and land it where this run left it.

    **Fetch, rebase, and refuse a rebase that has nothing to do — in that order.** The fetch is
    what makes the rebase mean *the branch as it is now* rather than as it was at some earlier
    moment; and the refusal is what stops a run walking: a repair that changes nothing leaves the
    pull request in front of the same `mergeable: false`, and the run arrives here again with the
    same facts until the recursion limit stops it.
    """
    _fetch(the_clone, the_branch_it_joins)

    _the_rebase_carried_out(the_clone, this_runs_branch, the_branch_it_joins)
    what_git_said = _the_branch_pushed_back(
        the_clone, this_runs_branch, the_commit_this_run_left_the_branch_on
    )

    return WhatTheRebaseLanded(
        commit=_the_head_of(the_clone, this_runs_branch), what_git_said=what_git_said
    )


def _fetch(the_clone: Path, the_branch_it_joins: str) -> None:
    """Read the branch this run's work joins, from the remote it lives on.

    **The fetch names a remote and not a URL**, and that is the whole reason: a URL needs a
    credential, and a URL needing a credential is a URL git prints back inside its own error
    message.
    """
    _git(
        the_clone,
        "fetch",
        "--quiet",
        WHERE_THE_BRANCH_IT_JOINS_LIVES,
        the_branch_it_joins,
    )


def _the_rebase_carried_out(
    the_clone: Path, this_runs_branch: str, the_branch_it_joins: str
) -> str:
    """Replay the branch, and put the clone back if git stopped.

    **The abort belongs here and not in the caller.** A checkout stopped mid-rebase carries a
    `.git/rebase-merge` that refuses the next `git` command this run makes, and the clone is the
    whole of a run's state — so a tool that left one behind would have destroyed the run rather
    than failed it.
    """
    what_it_said = _git_and_say(
        the_clone, "rebase", f"{WHERE_THE_BRANCH_IT_JOINS_LIVES}/{the_branch_it_joins}"
    )

    if (the_clone / ".git" / "rebase-merge").exists() or (
        the_clone / ".git" / "rebase-apply"
    ).exists():
        _git(the_clone, "rebase", "--abort")
        raise TheRebaseWasNotFinishedError(
            f"git could not replay {this_runs_branch} on {the_branch_it_joins}, and the clone has "
            f"been put back the way this run found it. Git said: {what_it_said}"
        )

    return what_it_said


def _the_branch_pushed_back(
    the_clone: Path, this_runs_branch: str, the_commit_this_run_left_the_branch_on: str
) -> str:
    """Put the branch back with the lease, and report a refusal naming the branch that moved.

    **The lease is the whole of the safety property here.** `create_a_branch_on_a_remote` refuses
    to push a branch that already exists on the remote, because a run must never move a branch
    somebody else is using; a rebase has to do precisely that, so that refusal cannot be relaxed and
    has to be stated precisely instead. Git compares the lease against the branch inside the same
    push that would move it — a read beforehand would leave a window, and what that window admits is
    a commit somebody else pushed in between, destroyed.
    """
    what_it_said = _git_and_say(
        the_clone,
        "push",
        f"--force-with-lease={this_runs_branch}:{the_commit_this_run_left_the_branch_on}",
        WHERE_THIS_RUNS_BRANCH_LIVES,
        f"HEAD:refs/heads/{this_runs_branch}",
    )

    if "stale info" in what_it_said or "rejected" in what_it_said.lower():
        raise TheBranchMovedUnderThisRunError(
            f"{this_runs_branch} on {WHERE_THIS_RUNS_BRANCH_LIVES} is not the commit "
            f"{the_commit_this_run_left_the_branch_on} this run left there, so it will not be "
            f"moved. Git said: {what_it_said}"
        )

    return what_it_said


def _the_head_of(the_clone: Path, a_branch: str) -> str:
    return _git(the_clone, "rev-parse", a_branch).strip()


def _git(the_clone: Path, *words: str) -> str:
    """One `git` that had to work, and its output."""
    return subprocess.run(
        ["git", *words],
        cwd=the_clone,
        check=True,
        capture_output=True,
        text=True,
        timeout=SECONDS_A_GIT_CALL_MAY_TAKE,
    ).stdout


def _git_may_fail(the_clone: Path, *words: str) -> subprocess.CompletedProcess[str]:
    """One `git` whose answer is a status code rather than an error."""
    return subprocess.run(
        ["git", *words],
        cwd=the_clone,
        capture_output=True,
        text=True,
        timeout=SECONDS_A_GIT_CALL_MAY_TAKE,
    )


def _git_and_say(the_clone: Path, *words: str) -> str:
    """One `git` that is allowed to fail, and everything it said either way.

    **Output and not a status code**, because every refusal in this module quotes what git said and
    a message this system composed is a message nobody verified.
    """
    finished = subprocess.run(
        ["git", *words],
        cwd=the_clone,
        capture_output=True,
        text=True,
        timeout=SECONDS_A_GIT_CALL_MAY_TAKE,
    )
    return (finished.stdout + finished.stderr).strip()
