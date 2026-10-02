"""Why a rebase did not land, named as a shell so the rule can be demanded.

**Nothing here is raised yet.** This exists so `test_a_rebase_lands_this_runs_commit` can load: a
test that demanded a name before any code produced it would fail on `ImportError`, which says
nothing about the rebase rule it is about.

**Three refusals and each is a different fact**, which is the reason they are three and not one:

- **the branch moved** — somebody pushed to it between this run reading it and this run moving
  it, and git's lease caught what a read would have destroyed;
- **it could not be finished** — git stopped, and the clone has been put back the way it was;
- **it would change nothing** — the branch is already on top of the branch it joins, and a
  decision taken once about a fact that has not changed is not a decision.
"""

from __future__ import annotations


class TheBranchMovedUnderThisRunError(Exception):
    """The branch on the remote is not the commit this run left there, so it will not be moved.

    **A lease and not a read, and the window is the whole reason.** Git compares the expected
    commit against the branch *inside the same push* that would move it. Reading the branch first
    would leave a space between the read and the push, and what that space admits is a commit
    somebody else pushed in between, destroyed by this run.

    `create_a_branch_on_a_remote` refuses to push a branch that already exists on the remote,
    because a run must never move a branch somebody else is using. A rebase has to do precisely
    that, so that refusal cannot be relaxed — it has to be stated precisely instead, and this is
    the statement.
    """


class TheRebaseWasNotFinishedError(Exception):
    """Git stopped part way, and the clone has been put back the way this run found it.

    **The put-back belongs to the refusal rather than to a caller's memory of it.** A checkout
    stopped mid-rebase carries a `.git/rebase-merge` that refuses the next `git` command this run
    makes, and the clone is the whole of a run's state — so a tool that leaves one behind has
    destroyed the run rather than failed it. Git's own sentence travels in the message because git
    is the only thing here that can say which file it could not merge.
    """


class TheRebaseWouldChangeNothingError(Exception):
    """The branch is already on top of the branch it joins, so there is nothing to replay.

    **This is what stops a run going round.** A merge refused as a conflict sends the run to this
    repair; a rebase that changes nothing leaves the pull request in front of the same
    `mergeable: false`, the run reaches this repair again with the same facts, and it walks to
    the runtime's recursion limit. The refusal is in the tool that knows the fact rather than left
    to a node to notice on a second visit.
    """
