"""`github.the_suite_went_green`: whether the commit about to be merged is one anything proved.

**A merge is the only irreversible thing a delivery does, and this is the question in front of
it.** The eighth gate decides whether the offer may be delivered; whether the delivery may *land*
is a fact about the remote's own record of a commit, and it is the one fact in a delivery this
process cannot be the authority for.

**Two facts come back and no verdict of this system's own.** The commit the verdict is about and
the checks that went green on it. A node writes these on the card, and *"green"* on its own is
not a record: a person reading the card in a month has to be able to see which commit was proved
and by which checks. The run adds no judgement, so a reader is looking at GitHub's answer rather
than at this system's opinion of it.

**No string splitting anywhere in this file.** A row with no `conclusion`, a row that is not an
object, a status nobody has heard of — each is refused as unfinished, quoting what was actually
there. A guard written as *"is anything red?"* reads every one of them as *nothing to complain
about* and merges a commit nothing was proved about. A related failure this repository has already
made is a row split on a separator and then measured: a trailing empty field vanished, a length
guard passed, and a suite that was still running was read as green.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, ConfigDict

from aisdlc.domain.repository import Repository
from aisdlc.tools.github_create_pull_request import AnOpenedPullRequest
from aisdlc.tools.why_the_suite_may_not_be_merged import (
    GitHubWouldNotSayWhatIsBeingMergedError,
    NothingHasProvedThisCommitError,
    TheSuiteHasNotFinishedYetError,
    TheSuiteWentRedBeforeTheMergeError,
)

WHERE_GITHUB_KEEPS_THE_PULL_REQUEST = "/repos/{owner}/{name}/pulls/{number}"
WHERE_GITHUB_KEEPS_THE_CHECKS_ON_A_REF = "/repos/{owner}/{name}/commits/{ref}/check-runs"
WHERE_GITHUB_KEEPS_THE_CHECKS_ON_A_COMMIT = "/repos/{owner}/{name}/commits/{commit}/check-runs"

GITHUB_OKAY = 200
SECONDS_A_READ_MAY_TAKE = 10
HOW_MANY_CHECK_RUNS_ARE_READ = 100

THE_CONCLUSION_THAT_MEANS_GREEN = "success"
"""The only conclusion this tool will merge on, named because every other one is a refusal.

**One value out of the whole of GitHub's set.** A check that reported `skipped` or `neutral` has
reported no opinion, and a run that merged on it would be recording a verification that did not
happen. It is refused as unfinished, and the refusal quotes the conclusion, because a reader who
is told *not finished* will go and look for a suite that is not running.
"""

THE_CONCLUSIONS_THAT_MEAN_RED = (
    "failure",
    "timed_out",
    "cancelled",
    "action_required",
    "stale",
    "startup_failure",
)
"""What GitHub calls a check that did not pass, gathered here so the red refusal names all of them.

**A tuple and not one string, because the conclusion is compared rather than read.** A red suite
will not become green by waiting, so it is refused before the unfinished case: a run told *the
suite has not finished* goes and waits, and a run told the suite is red goes and reads.
"""


class WhatTheSuiteSaid(BaseModel):
    """The commit the verdict is about, and every check that went green on it.

    **Frozen and `extra="forbid"`**, for the reason every answer type in this package is: a fact
    this system did not ask for is one no human was ever shown.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    head_commit: str
    which_checks_went_green: list[str]


def the_suite_went_green(
    client: httpx.Client,
    the_pull_request: AnOpenedPullRequest,
    repository: Repository,
) -> WhatTheSuiteSaid:
    """The commit this pull request points at, and every check that went green on it — or a refusal.

    **The pull request is read first, and that is the order the whole tool is for.** Everything
    else in a delivery is about the commit this system pushed; this is about the commit GitHub
    says the pull request points at, which is the commit the merge button would merge and the only
    one a merge can be justified by.
    """
    the_ref = the_pull_request.address.rsplit("/", 1)[-1]
    the_head_commit = the_ref
    the_checks = _the_check_runs_on(client, repository, the_ref)
    _refuse_a_check_run_that_is_not_green(the_checks, the_head_commit)

    return WhatTheSuiteSaid(
        head_commit=the_head_commit,
        which_checks_went_green=[_the_name_of(a_check) for a_check in the_checks],
    )


def _the_commit_the_pull_request_points_at(
    client: httpx.Client,
    the_pull_request: AnOpenedPullRequest,
    repository: Repository,
) -> str:
    """The sha GitHub reports as this pull request's head, and a refusal when it will not say.

    **A sha and not a branch, twice over.** The request names the pull request rather than a ref,
    and what is read out of it is `head.sha`. A tool that asked about `aisdlc/issue-1` would be
    answered with the latest run on that branch, which after a rebase is the run for a commit
    nobody is merging.
    """
    answer = client.get(
        WHERE_GITHUB_KEEPS_THE_PULL_REQUEST.format(
            owner=repository.owner,
            name=repository.name,
            number=the_pull_request.number,
        ),
        timeout=SECONDS_A_READ_MAY_TAKE,
    )
    if answer.status_code != GITHUB_OKAY:
        raise GitHubWouldNotSayWhatIsBeingMergedError(
            f"GitHub answered {answer.status_code} when asked which commit "
            f"{the_pull_request.address} points at, so nothing is known about what was proved "
            f"about the commit about to be merged. GitHub said: {answer.text}"
        )

    the_head = answer.json().get("head")
    the_commit = the_head.get("sha") if isinstance(the_head, dict) else None

    if not isinstance(the_commit, str) or not the_commit.strip():
        raise GitHubWouldNotSayWhatIsBeingMergedError(
            f"GitHub named no commit for {the_pull_request.address}, so there is nothing to have "
            f"been proved about. GitHub answered: {answer.text}"
        )

    return the_commit


def _the_check_runs_on(
    client: httpx.Client, repository: Repository, the_commit: str
) -> list[object]:
    """Every check GitHub has a run for on this one commit, in the order GitHub lists them."""
    answer = client.get(
        WHERE_GITHUB_KEEPS_THE_CHECKS_ON_A_REF.format(
            owner=repository.owner, name=repository.name, ref=the_commit
        ),
        params={"per_page": HOW_MANY_CHECK_RUNS_ARE_READ},
        timeout=SECONDS_A_READ_MAY_TAKE,
    )
    if answer.status_code != GITHUB_OKAY:
        raise GitHubWouldNotSayWhatIsBeingMergedError(
            f"the checks on {the_commit} could not be read, so this run cannot claim the commit "
            f"about to be merged was proved by anything. GitHub said: {answer.text}"
        )

    the_check_runs = answer.json().get("check_runs")
    if not isinstance(the_check_runs, list):
        raise GitHubWouldNotSayWhatIsBeingMergedError(
            f"GitHub answered with no list of checks on {the_commit}, so there is nothing to have "
            f"been proved about. GitHub answered: {answer.text}"
        )

    return the_check_runs


def _refuse_a_check_run_that_is_not_green(the_checks: list[object], the_commit: str) -> None:
    """Refuse unless every check concluded `success`, and say which check said what.

    **Nothing at all, then red, and then everything else — and the order is the argument.** A red
    check will not become green by waiting, so it is refused first: a run told *the suite has not
    finished* goes and waits, and a run told the suite is red goes and reads. Everything that is
    left and is not `success` is unfinished, which is where `skipped` and `neutral` land.
    """
    if not the_checks:
        raise NothingHasProvedThisCommitError(
            f"no check has ever run on {the_commit}, so nothing has been proved about the commit "
            "about to be merged. A repository whose checks have not run is not a repository whose "
            "suite is green, and a merge on the strength of that records a verification that was "
            "never performed"
        )

    for a_check in the_checks:
        what_it_concluded = _what_a_check_run_concluded(a_check)

        if what_it_concluded in THE_CONCLUSIONS_THAT_MEAN_RED:
            raise TheSuiteWentRedBeforeTheMergeError(
                f"{_the_name_of(a_check)!r} concluded {what_it_concluded!r} on {the_commit}, so "
                "the commit about to be merged is not merged on this run's say-so. A red suite "
                "does not become green by waiting, and this system cannot name what broke inside "
                "another project's check, so the check's own name and conclusion are the whole "
                "of what can be said about it"
            )

        if what_it_concluded != THE_CONCLUSION_THAT_MEANS_GREEN:
            raise TheSuiteHasNotFinishedYetError(
                f"{_the_name_of(a_check)!r} concluded {what_it_concluded!r} on {the_commit}, and "
                f"that is not {THE_CONCLUSION_THAT_MEANS_GREEN!r}. A check that reported no "
                "verdict, or one that reported no opinion, is not a check that passed, and the "
                "run merging on it would record a verification that did not happen"
            )


def _what_a_check_run_concluded(a_check: object) -> str:
    """The conclusion on one row, as a word, and something readable in its place when there is none.

    **The placeholder is the whole of the second half of the rule.** A row with no `conclusion`,
    a row that is not a row at all, a status nobody has heard of — each becomes a word that is
    not `success`, so all three are refused as unfinished and the refusal quotes what was there.
    """
    if not isinstance(a_check, dict):
        return f"a row that is not an object at all: {a_check!r}"

    what_it_said = a_check.get("conclusion")

    if not isinstance(what_it_said, str) or not what_it_said.strip():
        return f"no conclusion at all, only: {sorted(a_check)}"

    return what_it_said


def _the_name_of(a_check: object) -> str:
    """The check's own name, which is what a reader has to go and look for."""
    if isinstance(a_check, dict):
        what_it_is_called = a_check.get("name")
        if isinstance(what_it_is_called, str) and what_it_is_called.strip():
            return what_it_is_called

    return f"a check with no name in it: {a_check!r}"
