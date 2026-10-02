"""Why the commit about to be merged may not be merged yet: the four refusals, named.

**Nothing here is raised yet.** This exists so the test named in the file this shell sits
beside can load: a test that demanded a name before any code produced it would
fail on `ImportError`, which says nothing about the merge rule it is about.
can load: a test that demanded a name before any code produced it would fail on `ImportError`,
which says nothing about the merge rule it is about. A shell that raises nothing is the honest
shape — and it is the same shape `ARepairThatOnlyAGateMayDecideError` took when the repair route
was first refused.

**Four refusals and each is a different fact**, which is why there are four and not one:

- **no checks at all** — nothing was verified, and a merge on the strength of that records a
  verification that was never performed;
- **red** — the suite did not pass, and it will not pass by waiting;
- **no verdict yet** — the answer is not in yet, or is in a shape nobody has heard of;
- **GitHub would not say** — a different place to look entirely.
"""

from __future__ import annotations


class NothingHasProvedThisCommitError(Exception):
    """Nothing was asked to prove anything about the commit about to be merged.

    **A repository with no check runs is not a repository whose suite is green**, and this is a
    worse claim than a red suite rather than a better one: a red suite is at least visible to
    whoever reads the checks.
    """


class TheSuiteWentRedBeforeTheMergeError(Exception):
    """A check on the commit about to be merged concluded that it did not pass.

    **Carries the check's own name and GitHub's own conclusion**, because this system cannot
    parse another project's check output to name what broke. A summary a scraper invented is a
    name nobody verified, and the person who has to act on this is the one who can read the check.
    """


class TheSuiteHasNotFinishedYetError(Exception):
    """A check on the commit about to be merged has no verdict yet, or has no readable one.

    **An absent verdict is not a green one, and that is the whole of the rule.** A row GitHub
    answered with no `conclusion`, a row that is not an object, a status nobody has heard of — a
    guard written as *is anything red?* reads every one of them as *nothing to complain about* and
    merges a commit nothing was proved about. The refusal quotes what was there, so a reader can
    tell a suite still running from a row this system cannot read.
    """


class GitHubWouldNotSayWhatIsBeingMergedError(Exception):
    """GitHub would not say which commit this pull request points at, or what its checks are.

    **Separate from the unfinished case, and the difference is what a reader does next.** A 404
    about a repository this system pushed to twenty minutes ago is a fact about the push, and a
    person told *the suite has not finished* will go and wait for a suite nobody is running.
    """
