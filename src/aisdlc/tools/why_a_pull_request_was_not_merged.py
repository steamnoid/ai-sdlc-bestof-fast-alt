"""Why a pull request was not merged, named as a shell so the rule can be demanded.

**Nothing here is raised yet.** This exists so `test_a_merge_lands_one_commit_and_says_so` can
load: a test that demanded a name before any code produced it would fail on `ImportError`, which
says nothing about the merge rule it is about.

**Five refusals and none of them is the others**, and the separations are the whole point:

- **cannot be read** — a 404 is about the push that opened the pull request twenty minutes ago;
- **in conflict** — can be rebased and tried again;
- **not decided yet** — GitHub computes a conflict in the background and answers `null` until it
  has one, and this run may not read `null` as permission;
- **refused by GitHub** — 405, 409 and 410 are three different problems this system will not
  tell apart from the prose;
- **a commit nobody proved** — the commit is required and is not a default.
"""

from __future__ import annotations


class ThePullRequestCouldNotBeReadError(Exception):
    """GitHub would not say what this pull request is, so nothing is known about merging it.

    **Separate from a refusal to merge, because they are different facts about different
    minutes.** A 404 here is about the push that opened the pull request twenty minutes ago, and a
    person told *the merge was refused* would go and look at the merge rather than at the push.
    """


class ThePullRequestIsInConflictError(Exception):
    """GitHub says this pull request cannot be merged because it conflicts with its base.

    **A conflict and not a refusal, and the difference is what can be done about it.** A
    conflicting pull request can be rebased and tried again; a protected base branch cannot be
    merged into at all, and **GitHub words the two the same way**. This is raised from the
    `mergeable` field alone, so the phrase *not mergeable* in a refusal is never read as a
    conflict.
    """


class GitHubHasNotSaidWhetherItCanBeMergedYetError(Exception):
    """GitHub is still deciding, and this run may not guess.

    **`null` is not `true` and is not `false`.** Reading it as mergeable merges an unproved
    commit; reading it as a conflict sends a person after a conflict nobody has established.
    Asking again is the only honest move, and it is a move this tool does not make on the
    caller's behalf.
    """


class TheMergeWasRefusedByGitHubError(Exception):
    """GitHub declined the merge, and what it said is the whole of what a person can act on.

    **Quoted rather than re-interpreted.** A system that paraphrases a remote's confirmation is a
    system that can be wrong about a merge having happened, and the person who has to act on this
    is the one who can read GitHub's reason.
    """


class MergeACommitNobodyProvedError(Exception):
    """The commit a merge was asked to land is not a commit, and the refusal is before any request.

    **The commit is the only thing that makes a merge mean *this commit or nothing*.** The suite
    was read green for a sha a moment earlier; a blank one is a merge allowed to land whatever
    happens to be there, which is the thing the whole tool exists to prevent.
    """
