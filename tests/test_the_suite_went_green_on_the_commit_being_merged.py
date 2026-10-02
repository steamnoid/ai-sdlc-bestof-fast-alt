"""That a merge is justified by the checks on the commit GitHub says is being merged.

**A merge is the only irreversible thing a delivery does, and this is the question in front of
it.** The eighth gate decides whether the offer may be delivered; whether the delivery may *land*
is a fact about the remote's own record of a commit, and it is the one fact in a delivery this
process cannot be the authority for.

**The commit is read from the pull request and never named by a caller, and that ordering is the
whole tool.** The head of a pull request moves: a rebase, an "update branch", or a second run
pushing the same branch all change it after this system pushed. A green run from *before* the
rebase describes a commit that is not being merged, and a check-runs request naming a **branch**
answers with the latest run on that branch — which is the run for the wrong commit, and it is
green. So the pull request is asked about first, and the sha it reports is what the checks are
read for. `test_the_checks_are_read_for_the_commit_the_pull_request_points_at` holds a transport
that answers the two requests differently and asserts which sha was asked about.

**An absent verdict is never green, and there is no string splitting in this file.** A row with no
`conclusion`, a row that is not an object, a status nobody has heard of — each is refused as
unfinished, quoting what was actually there. A guard written as *"is anything red?"* reads every
one of them as *nothing to complain about* and merges a commit nothing was proved about. A related
failure this repository has already made is a row split on a separator and then measured: a
trailing empty field vanished, a length guard passed, and a suite still running was read as green.

**Nothing at all, then red, and then everything else — the order is the argument.** A red check
will not become green by waiting, so it is refused first: a run told *the suite has not finished*
goes and waits, and a run told the suite is red goes and reads.

**A fake transport, because a fake GitHub is the only GitHub this can be deterministic about.**
The refusal logic is a decision about somebody else's set of words, and a test that reached the
real one would be a test that runs when GitHub is up. The integration tier is where the URL and
the credential are proved; this is where the verdict is.
"""

from __future__ import annotations

import httpx
import pytest

from aisdlc.domain.repository import Repository
from aisdlc.tools.github_client import GITHUBS_PUBLIC_API
from aisdlc.tools.github_create_pull_request import AnOpenedPullRequest
from aisdlc.tools.the_suite_went_green import the_suite_went_green
from aisdlc.tools.why_the_suite_may_not_be_merged import (
    GitHubWouldNotSayWhatIsBeingMergedError,
    NothingHasProvedThisCommitError,
    TheSuiteHasNotFinishedYetError,
    TheSuiteWentRedBeforeTheMergeError,
)

THE_REPOSITORY = Repository(owner="paligakrzychu", name="wellbeing-tracker-public")
THE_PULL_REQUEST = AnOpenedPullRequest(number=10, address="https://example.invalid/p/pull/10")
THE_HEAD_AFTER_A_REBASE = "b" * 40
THE_HEAD_BEFORE_A_REBASE = "a" * 40


def _a_client_saying(the_head: str, what_the_checks_say: object, status: int = 200) -> httpx.Client:
    """A client that answers the two requests this tool makes, and nothing else.

    **The head and the checks are told separately** because the whole claim is that they are read
    in that order and about different things. A transport that answered one URL for both would
    satisfy a tool that never asked about the pull request at all.

    **`base_url` and not a hand-written host, because this client is shaped like the real one.**
    `a_github_client()` carries `base_url=GITHUBS_PUBLIC_API` and the tools pass relative paths,
    so a fake without a base URL is a client that never exists — and the first version of this
    file had one, and every test in it failed on `unknown url type` rather than on the merge
    rule. A fake that is not the shape of the thing it stands in for measures a configuration
    nobody runs.
    """

    def answer(the_request: httpx.Request) -> httpx.Response:
        if the_request.url.path.endswith(f"/pulls/{THE_PULL_REQUEST.number}"):
            return httpx.Response(status, json={"head": {"sha": the_head}})
        return httpx.Response(status, json=what_the_checks_say)

    return httpx.Client(base_url=GITHUBS_PUBLIC_API, transport=httpx.MockTransport(answer))


def _a_check(named: str, concluded: str | None) -> dict[str, object]:
    """One check run row, shaped the way GitHub sends one."""
    row: dict[str, object] = {"name": named}
    if concluded is not None:
        row["conclusion"] = concluded
    return row


def test_green_checks_name_the_commit_and_which_checks_proved_it() -> None:
    """The record a person reads in a month: which commit, and by what."""
    what_the_suite_said = the_suite_went_green(
        _a_client_saying(
            THE_HEAD_AFTER_A_REBASE,
            {"check_runs": [_a_check("the_gate", "success"), _a_check("lint", "success")]},
        ),
        THE_PULL_REQUEST,
        THE_REPOSITORY,
    )

    assert what_the_suite_said.head_commit == THE_HEAD_AFTER_A_REBASE, (
        "the record does not name the commit the verdict is about, so a reader cannot tell "
        "whether it describes what would be merged today"
    )
    assert what_the_suite_said.which_checks_went_green == ["the_gate", "lint"], (
        f"the record names {what_the_suite_said.which_checks_went_green} rather than the checks "
        "that went green, so 'green' on its own is a claim with nothing behind it"
    )


def test_the_checks_are_read_for_the_commit_the_pull_request_points_at() -> None:
    """The commit is asked for, and the checks are read for the sha GitHub reported.

    **Asserted on which URL was requested and not only on the answer.** A transport that answered
    from the branch instead of the pull request would return the sha before the rebase, and the
    test would still pass on a tool that had asked about the wrong thing — which is the failure
    this whole ordering exists to prevent.
    """
    what_was_asked_for: list[str] = []

    def answer(the_request: httpx.Request) -> httpx.Response:
        what_was_asked_for.append(the_request.url.path)
        if the_request.url.path.endswith(f"/pulls/{THE_PULL_REQUEST.number}"):
            return httpx.Response(200, json={"head": {"sha": THE_HEAD_AFTER_A_REBASE}})
        return httpx.Response(200, json={"check_runs": [_a_check("the_gate", "success")]})

    the_suite_went_green(
        httpx.Client(base_url=GITHUBS_PUBLIC_API, transport=httpx.MockTransport(answer)),
        THE_PULL_REQUEST,
        THE_REPOSITORY,
    )

    assert what_was_asked_for == [
        f"/repos/{THE_REPOSITORY.owner}/{THE_REPOSITORY.name}/pulls/{THE_PULL_REQUEST.number}",
        f"/repos/{THE_REPOSITORY.owner}/{THE_REPOSITORY.name}/commits/"
        f"{THE_HEAD_AFTER_A_REBASE}/check-runs",
    ], (
        f"the tool asked for {what_was_asked_for} and the second request must name the sha GitHub "
        f"reported ({THE_HEAD_AFTER_A_REBASE}), not the branch: a branch answers with the latest "
        "run on it, which after a rebase is the run for a commit nobody is merging"
    )


def test_no_checks_at_all_is_not_a_green_suite() -> None:
    """Nothing was proved, and a merge on the strength of that records a verification that was
    never performed."""
    with pytest.raises(NothingHasProvedThisCommitError) as it_raised:
        the_suite_went_green(
            _a_client_saying(THE_HEAD_AFTER_A_REBASE, {"check_runs": []}),
            THE_PULL_REQUEST,
            THE_REPOSITORY,
        )

    assert THE_HEAD_AFTER_A_REBASE in str(it_raised.value), (
        f"the refusal does not name the commit nothing was proved about: {it_raised.value}"
    )


def test_a_red_check_is_refused_and_named_by_its_own_name_and_conclusion() -> None:
    """This system cannot parse another project's check output, so the check names itself."""
    with pytest.raises(TheSuiteWentRedBeforeTheMergeError) as it_raised:
        the_suite_went_green(
            _a_client_saying(
                THE_HEAD_AFTER_A_REBASE,
                {
                    "check_runs": [
                        _a_check("the_gate", "success"),
                        _a_check("the build", "timed_out"),
                    ]
                },
            ),
            THE_PULL_REQUEST,
            THE_REPOSITORY,
        )

    said_so = str(it_raised.value)
    assert "the build" in said_so and "timed_out" in said_so, (
        f"the refusal does not carry the check's own name and GitHub's own conclusion, and the "
        f"person who has to act on this is the one who can read the check: {said_so}"
    )


def test_a_check_with_no_verdict_yet_is_refused_as_unfinished_not_as_green() -> None:
    """An absent verdict is not a green one, and that is the whole of the rule."""
    with pytest.raises(TheSuiteHasNotFinishedYetError):
        the_suite_went_green(
            _a_client_saying(
                THE_HEAD_AFTER_A_REBASE,
                {"check_runs": [_a_check("the_gate", None)]},
            ),
            THE_PULL_REQUEST,
            THE_REPOSITORY,
        )


@pytest.mark.parametrize("a_conclusion_that_reported_no_opinion", ["skipped", "neutral"])
def test_a_check_that_reported_no_opinion_is_refused_as_unfinished(
    a_conclusion_that_reported_no_opinion: str,
) -> None:
    """A check with no opinion is not a check that passed, and a merge on it invents a verdict."""
    with pytest.raises(TheSuiteHasNotFinishedYetError) as it_raised:
        the_suite_went_green(
            _a_client_saying(
                THE_HEAD_AFTER_A_REBASE,
                {"check_runs": [_a_check("optional", a_conclusion_that_reported_no_opinion)]},
            ),
            THE_PULL_REQUEST,
            THE_REPOSITORY,
        )

    assert a_conclusion_that_reported_no_opinion in str(it_raised.value), (
        f"the refusal does not quote the conclusion it refused, so a reader cannot tell a suite "
        f"still running from a check that deliberately stood aside: {it_raised.value}"
    )


def test_a_row_that_is_not_an_object_is_refused_rather_than_skipped() -> None:
    """A guard written as *is anything red?* reads this as nothing to complain about."""
    with pytest.raises(TheSuiteHasNotFinishedYetError):
        the_suite_went_green(
            _a_client_saying(THE_HEAD_AFTER_A_REBASE, {"check_runs": ["a string, not a row"]}),
            THE_PULL_REQUEST,
            THE_REPOSITORY,
        )


def test_github_will_not_say_which_commit_is_being_merged_is_a_fourth_refusal() -> None:
    """Separate from the unfinished case, because it sends a reader to a different place.

    A 404 about a repository this system pushed to twenty minutes ago is a fact about the push.
    A person told *the suite has not finished* will go and wait for a suite nobody is running.
    """
    with pytest.raises(GitHubWouldNotSayWhatIsBeingMergedError) as it_raised:
        the_suite_went_green(
            _a_client_saying(THE_HEAD_AFTER_A_REBASE, {"check_runs": []}, status=404),
            THE_PULL_REQUEST,
            THE_REPOSITORY,
        )

    assert "404" in str(it_raised.value), (
        f"the refusal does not carry GitHub's own status, so a reader cannot tell a missing "
        f"repository from a permission problem: {it_raised.value}"
    )


def test_github_answering_with_no_list_of_checks_is_refused() -> None:
    """An answer with no list is not a list of nothing, and the two are read differently."""
    with pytest.raises(GitHubWouldNotSayWhatIsBeingMergedError):
        the_suite_went_green(
            _a_client_saying(THE_HEAD_AFTER_A_REBASE, {"message": "Not Found"}),
            THE_PULL_REQUEST,
            THE_REPOSITORY,
        )


def test_github_naming_no_commit_for_the_pull_request_is_refused() -> None:
    """There is nothing to have been proved about, and a sha is the only thing that says what."""
    with pytest.raises(GitHubWouldNotSayWhatIsBeingMergedError):
        the_suite_went_green(
            _a_client_saying("", {"check_runs": [_a_check("the_gate", "success")]}),
            THE_PULL_REQUEST,
            THE_REPOSITORY,
        )
