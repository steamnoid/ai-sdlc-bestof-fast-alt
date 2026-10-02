"""That a merge lands one commit, and that GitHub says it happened.

**A merge is the only thing this system does that changes somebody else's repository without
asking them again.** Everything before it in a delivery is an offer; this is the offer being
taken up, and it is irreversible in a way a closed issue is not.

**`mergeable` is read first, and it is the only thing that may call something a conflict.**
GitHub answers *"Pull Request is not mergeable"* for a pull request that conflicts with its base
— which a run can rebase and try again — and for a base branch that is **protected**, which no
amount of rebasing will fix. Classifying the refusal by reading that phrase calls the second one
a conflict and **sends a person after a merge conflict on a branch that is protected on purpose.**
So the refusal is read from the field and never from the message, and this test pins that: a
refusal saying "not mergeable" in a protected branch's words must still raise the conflict error,
because `mergeable: false` is the only fact that establishes a conflict at all.

**The commit is an argument, because the checks were read about a commit.** The suite was read
green for this pull request's head sha a moment earlier, and a head that moved since — a rebase,
an "update branch", a second run pushing the same branch — is a commit nothing was proved about.
**Handing the sha to GitHub is what makes the merge mean *this commit or nothing***, and it is
GitHub that refuses the attempt rather than this system noticing afterwards. So one test asserts
on the body that was sent, and a blank sha is refused before any request.

**`null` is its own refusal, and it is a fact GitHub states rather than a gap in this tool.**
GitHub computes a merge conflict in the background, so a pull request asked about seconds after
it was opened answers `mergeable: null`. `true` would merge whatever happened to be there;
`false` would accuse it of a conflict nobody has established.

**No merge method is chosen here.** Whether a repository merges, squashes or rebases is that
repository's setting, and a system that picked one would silently change how every repository it
delivers to records history — so the body carries the sha and nothing else.

**A fake transport, for the same reason the suite's tests use one:** this is a decision about
somebody else's set of statuses, and a test that reached the real one would run when GitHub is up.
"""

from __future__ import annotations

import httpx
import pytest

from aisdlc.domain.repository import Repository
from aisdlc.tools.github_client import GITHUBS_PUBLIC_API
from aisdlc.tools.merge_a_pull_request import APullRequestToMerge, merge_a_pull_request
from aisdlc.tools.why_a_pull_request_was_not_merged import (
    GitHubHasNotSaidWhetherItCanBeMergedYetError,
    MergeACommitNobodyProvedError,
    TheMergeWasRefusedByGitHubError,
    ThePullRequestCouldNotBeReadError,
    ThePullRequestIsInConflictError,
)
from aisdlc.tools.why_the_suite_may_not_be_merged import GitHubWouldNotSayWhatIsBeingMergedError

THE_REPOSITORY = Repository(owner="paligakrzychu", name="wellbeing-tracker-public")
THE_COMMIT_THE_SUITE_WAS_GREEN_ON = "b" * 40
A_CREDENTIAL = "ghp_something"


def _the_merge(wanted_commit: str = THE_COMMIT_THE_SUITE_WAS_GREEN_ON) -> APullRequestToMerge:
    return APullRequestToMerge(
        repository=THE_REPOSITORY, number=10, the_commit_a_merge_may_land=wanted_commit
    )


def _a_client(
    what_it_says_about_mergeability: object,
    what_it_says_when_merged: object = None,
    status_when_merged: int = 200,
    status_when_asked: int = 200,
) -> httpx.Client:
    """The body carries the sha, and nothing that would choose a history style."""

    what_was_sent_to_the_merge: list[dict[str, object]] = []

    def answer(the_request: httpx.Request) -> httpx.Response:
        if the_request.method == "PUT":
            import json

            what_was_sent_to_the_merge.append(json.loads(the_request.content))
            return httpx.Response(
                status_when_merged,
                json={"merged": True, "sha": THE_COMMIT_THE_SUITE_WAS_GREEN_ON}
                if what_it_says_when_merged is None
                else what_it_says_when_merged,
            )
        return httpx.Response(
            status_when_asked, json={"mergeable": what_it_says_about_mergeability}
        )

    the_client = httpx.Client(base_url=GITHUBS_PUBLIC_API, transport=httpx.MockTransport(answer))
    the_client.what_was_sent_to_the_merge = what_was_sent_to_the_merge  # type: ignore[attr-defined]
    return the_client


def test_a_merge_lands_the_commit_the_checks_were_read_about() -> None:
    """The body carries the sha, and nothing else that would choose a history style."""
    the_client = _a_client(what_it_says_about_mergeability=True)

    what_the_merge_landed = merge_a_pull_request(the_client, _the_merge(), A_CREDENTIAL)

    what_was_sent = the_client.what_was_sent_to_the_merge[0]  # type: ignore[attr-defined]
    assert what_was_sent == {"sha": THE_COMMIT_THE_SUITE_WAS_GREEN_ON}, (
        f"the merge was asked for {what_was_sent} and a merge that may land any commit is a merge "
        f"that may land one nothing was proved about. It must also carry no merge method: "
        "whether a repository merges, squashes or rebases is that repository's setting"
    )
    assert what_the_merge_landed.commit == THE_COMMIT_THE_SUITE_WAS_GREEN_ON, (
        f"the run recorded the merge as landing {what_the_merge_landed.commit}"
    )


def test_a_pull_request_that_conflicts_is_refused_as_a_conflict() -> None:
    """`mergeable: false` is the only fact that establishes a conflict."""
    with pytest.raises(ThePullRequestIsInConflictError):
        merge_a_pull_request(
            _a_client(what_it_says_about_mergeability=False), _the_merge(), A_CREDENTIAL
        )


def test_github_still_deciding_is_refused_rather_than_read_either_way() -> None:
    """`null` is not `true` and is not `false`, and guessing it either way is the wrong move."""
    with pytest.raises(GitHubHasNotSaidWhetherItCanBeMergedYetError):
        merge_a_pull_request(
            _a_client(what_it_says_about_mergeability=None), _the_merge(), A_CREDENTIAL
        )


def test_a_200_with_no_field_at_all_is_read_as_not_decided_rather_than_as_permission() -> None:
    """An absent field is not a `true`, and this is the only shape of that mistake."""
    with pytest.raises(GitHubHasNotSaidWhetherItCanBeMergedYetError):
        merge_a_pull_request(
            _a_client(what_it_says_about_mergeability="true"), _the_merge(), A_CREDENTIAL
        )


def test_a_404_is_not_a_refusal_to_merge_but_a_pull_request_that_cannot_be_read() -> None:
    """405, 409 and 410 are three problems this system will not tell apart from the prose."""
    with pytest.raises(ThePullRequestCouldNotBeReadError):
        merge_a_pull_request(
            _a_client(
                what_it_says_about_mergeability=True,
                status_when_asked=404,
            ),
            _the_merge(),
            A_CREDENTIAL,
        )


def test_a_pull_request_that_answers_nothing_about_mergeability_is_never_merged() -> None:
    """The read has to happen before the merge, or there is no fact to merge on.

    **Asserted by counting the requests**, because every other test in this file would pass on a
    tool that merged first and asked afterwards — the failure mode this ordering exists to
    prevent, and the one §37's *"must NOT merge automatically"* is actually about.
    """
    the_client = _a_client(what_it_says_about_mergeability=None)

    with pytest.raises(GitHubHasNotSaidWhetherItCanBeMergedYetError):
        merge_a_pull_request(the_client, _the_merge(), A_CREDENTIAL)

    assert the_client.what_was_sent_to_the_merge == [], (  # type: ignore[attr-defined]
        "a merge was attempted against a pull request GitHub had not said could be merged. The "
        "read is not a courtesy before an irreversible act; it is the only fact the act rests on"
    )


def test_a_merge_github_refused_is_quoted_and_not_re_interpreted() -> None:
    """405, 409 and 410 are three different problems and this system will not tell them apart.

    **The message travels verbatim**, because the person who has to act on this is the one who
    can read GitHub's reason, and a classification invented from the prose is a name nobody
    verified.
    """
    with pytest.raises(TheMergeWasRefusedByGitHubError) as it_raised:
        merge_a_pull_request(
            _a_client(
                what_it_says_about_mergeability=True,
                what_it_says_when_merged={"message": "Base branch was modified."},
                status_when_merged=409,
            ),
            _the_merge(),
            A_CREDENTIAL,
        )

    said_so = str(it_raised.value)
    assert "409" in said_so and "Base branch was modified." in said_so, (
        f"the refusal does not carry GitHub's status and its own sentence, so a reader has "
        f"nothing to act on but this system's paraphrase: {said_so}"
    )


def test_a_merge_github_says_did_not_happen_is_not_reported_as_a_merge() -> None:
    """A 200 that says `merged: false` has merged nothing."""
    with pytest.raises(TheMergeWasRefusedByGitHubError):
        merge_a_pull_request(
            _a_client(
                what_it_says_about_mergeability=True,
                what_it_says_when_merged={"merged": False},
            ),
            _the_merge(),
            A_CREDENTIAL,
        )


def test_a_merge_with_no_credential_is_refused_before_any_request() -> None:
    """A merge is somebody else's decision being carried out, and nobody cannot carry one out.

    **Asserted on the request count**, because a 401 arrives as a sentence naming neither the
    setting nor the permission — the one answer that helps nobody.
    """
    the_client = _a_client(what_it_says_about_mergeability=True)

    with pytest.raises(Exception) as it_raised:
        merge_a_pull_request(the_client, _the_merge(), "   ")

    assert "GITHUB_TOKEN" in str(it_raised.value) or "credential" in str(it_raised.value).lower(), (
        f"the refusal does not name what is missing: {it_raised.value}"
    )


def test_a_merge_of_nothing_in_particular_is_refused_before_it_is_asked_for() -> None:
    """A blank commit is a merge allowed to land whatever happens to be there."""
    with pytest.raises(Exception) as it_raised:
        _the_merge(wanted_commit="   ")

    assert "checks" in str(it_raised.value).lower(), (
        f"the refusal does not say that the commit is the one the checks were read about, which "
        f"is the whole reason it is required: {it_raised.value}"
    )


def test_the_two_github_would_not_say_errors_are_separate_from_the_merge_ones() -> None:
    """The suite's four refusals and the merge's four are different sets and must not be confused.

    **Asserted on the classes rather than on behaviour**, because the confusion this prevents is
    one a reader makes: *"the suite went red"* and *"GitHub would not say"* send a person to two
    different places, and the whole of `the_suite_went_green`'s naming is that they stay apart.
    """
    merge_only = {
        ThePullRequestCouldNotBeReadError,
        ThePullRequestIsInConflictError,
        GitHubHasNotSaidWhetherItCanBeMergedYetError,
        TheMergeWasRefusedByGitHubError,
        MergeACommitNobodyProvedError,
    }
    suite_only = {
        GitHubWouldNotSayWhatIsBeingMergedError,
    }

    assert not (merge_only & suite_only), (
        f"an error is both a merge refusal and a suite refusal: {merge_only & suite_only}"
    )
