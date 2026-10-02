"""A briefing that proposes work somebody has already filed is noise, and it is preventable.

**Filing is the only irreversible thing in this repository's creative mode.** A briefing writes
nothing: it clones, reads and writes a report beside the clone. Filing opens an issue on somebody
 else's board, and an issue is a thing that lands in a queue and stays there. So the cost of being
wrong about duplication is paid by a stranger, in the one place they cannot easily ignore it.

**Two changes, and the second is the one that matters.**

1. **The briefing is shown what is already tracked.** A model told to "propose work" will happily
   propose work that exists; it is a retrieval task and it recalls a different project. Listing
   the open issues turns it into a lookup.

2. **Filing refuses a duplicate anyway.** A prompt is not a check. This repository has a standing
   rule about exactly that, learned the hard way by a model citing a file that did not exist while
   being told to cite real ones. The briefing agent may ignore the list, misread it, or propose
   the same work in different words — and the refusal is what turns that into a question rather
   than an issue.

**The rule is about the work, and not about the string.** Two titles for the same work rarely match
as text, so this compares the words they share rather than testing for equality: a duplicate is a
title whose significant words are already a title's. That is a judgement, and it is stated here
rather than buried, because a filter that silently drops a real issue is worse than a duplicate.

**A repository with no issues is not an error.** Most repositories have none, and the tool
refusing to answer would make the common case the special one.
"""

from __future__ import annotations

import httpx
import pytest

from aisdlc.domain.repository import Repository
from aisdlc.tools.github_list_open_issues import (
    WorkAlreadyTrackedError,
    read_the_open_issues,
    the_issues_listed_as_tracked,
)

A_REPOSITORY = Repository(owner="an", name="owner")


def _a_github_answering(issues: list[dict[str, object]]) -> tuple[httpx.Client, list[str]]:
    what_it_was_asked: list[str] = []

    def record(request: httpx.Request) -> httpx.Response:
        what_it_was_asked.append(str(request.url))
        return httpx.Response(200, json=issues)

    return (
        httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(record)),
        what_it_was_asked,
    )


def _an_issue(number: int, title: str, state: str = "open") -> dict[str, object]:
    return {"number": number, "title": title, "state": state, "html_url": "https://x/1"}


def test_the_open_issues_of_a_repository_are_read_without_a_credential() -> None:
    """A briefing on a public repository must still work on a machine with no token.

    **Issue listing is public where filing is not**, and the two are different endpoints with
    different rules. A briefing is a reading operation all the way through — clone, inspect,
    report — and making it need a credential would mean the read half of creative mode could not
    be tried by anybody who had not configured a way to write to a stranger's repository.
    """
    the_client, what_it_was_asked = _a_github_answering(
        [_an_issue(3, "The session cookie has no expiry"), _an_issue(4, "Add a health endpoint")]
    )

    the_issues = read_the_open_issues(the_client, A_REPOSITORY)

    assert [an_issue.title for an_issue in the_issues] == [
        "The session cookie has no expiry",
        "Add a health endpoint",
    ]
    the_path_asked = httpx.URL(what_it_was_asked[0]).path
    assert len(what_it_was_asked) == 1 and the_path_asked.endswith("/issues"), (
        f"the issues were not read from GitHub's issues endpoint: {what_it_was_asked}"
    )


def test_a_repository_with_no_issues_is_an_empty_list_and_not_an_error() -> None:
    """Most repositories have no issues, so the common case must not be the special one."""
    the_client, _ = _a_github_answering([])

    assert read_the_open_issues(the_client, A_REPOSITORY) == []


def test_a_closed_issue_is_not_work_that_is_still_being_tracked() -> None:
    """Closed work was done, or was rejected — and proposing it again is a different mistake.

    **Only open issues are work in progress.** Somebody closed an issue; re-proposing it asks a
    team to consider something they have already considered and closed, which is worse than a
    duplicate — it is a proposal that ignores a decision somebody made.
    """
    the_client, _ = _a_github_answering(
        [_an_issue(1, "Still open", "open"), _an_issue(2, "Already dealt with", "closed")]
    )

    the_issues = read_the_open_issues(the_client, A_REPOSITORY)

    assert [an_issue.title for an_issue in the_issues] == ["Still open"]


def test_an_issue_a_holder_lost_its_title_is_skipped_rather_than_crashing_the_briefing() -> None:
    """GitHub's issues endpoint returns pull requests too, and some carry no title.

    **A malformed row must not take the briefing down with it.** The endpoint mixes issues and
    pull requests, and a `null` title is possible. A briefing that refused to run because one of
    two hundred rows was odd would be a briefing that never runs.
    """
    the_client, _ = _a_github_answering(
        [_an_issue(1, "A real one"), {"number": 2, "title": None, "state": "open"}]
    )

    the_issues = read_the_open_issues(the_client, A_REPOSITORY)

    assert [an_issue.title for an_issue in the_issues] == ["A real one"]


def test_work_already_tracked_is_refused_before_anything_is_filed() -> None:
    """The backstop, and the reason the list in the prompt is not enough on its own.

    **This is the enforcement the prompt cannot be.** A model told the open issues will still
    occasionally propose one of them — a different wording, a partial overlap, a good idea it had
    on its own. And the consequence of that is an issue on somebody else's board, which is the one
    thing in creative mode that cannot be undone.
    """
    already_filed = read_the_open_issues(*_issues_about_session_cookies())

    with pytest.raises(WorkAlreadyTrackedError) as the_refusal:
        the_issues_listed_as_tracked(
            "Add an expiry to the session cookie",
            already_filed,
        )

    assert "session cookie" in str(the_refusal.value), (
        "the refusal does not name the work that is already tracked, so a reader has to go and "
        "find which existing issue it collided with"
    )


def _issues_about_session_cookies() -> tuple[httpx.Client, Repository]:
    the_client, _ = _a_github_answering([_an_issue(7, "The session cookie has no expiry")])
    return the_client, A_REPOSITORY


def test_different_work_is_filed_even_when_issues_exist() -> None:
    """Otherwise the backstop stops every briefing on any repository with a backlog."""
    already_filed = read_the_open_issues(*_issues_about_session_cookies())

    the_issues_listed_as_tracked("Rate-limit the public search endpoint", already_filed)


def test_two_titles_that_share_a_word_are_not_the_same_work() -> None:
    """The comparison is about the work, and "the" is not a claim about anything.

    **A one-word overlap would refuse half of every backlog.** An issue titled "Add a test" and an
    opportunity "Add a health endpoint" share `Add` and nothing else, and refusing the second
    because of the first would make creative mode useless on any real repository. So the words
    compared are the ones that carry meaning, and the few that appear in almost every title are
    dropped first.
    """
    already_filed = read_the_open_issues(*_issues_about_session_cookies())

    the_issues_listed_as_tracked("Add a health endpoint", already_filed)


def test_an_issue_with_no_body_is_still_a_duplicate() -> None:
    """Title only is the common shape of a filed issue, so the title is what there is."""
    already_filed = read_the_open_issues(*_issues_about_session_cookies())

    with pytest.raises(WorkAlreadyTrackedError):
        the_issues_listed_as_tracked("Add an expiry to the session cookie", already_filed)


def test_filing_refuses_a_duplicate_before_anything_is_opened() -> None:
    """The backstop in the place it has to be: before the issue exists.

    **An issue that is opened and then found to be a duplicate has already landed.** Closing it
    again is a thing a person has to do on somebody else's board, and the person who has to do it
    is the one whose queue got longer. So the refusal is in `filing_what_the_briefing_found`,
    ahead of `open_the_issue`, rather than in the prompt that asked the model nicely.
    """
    import pytest as _pytest

    from aisdlc.agents.what_an_agent_judged import WhatAnAgentJudged
    from aisdlc.creative.an_opportunity import AnOpportunity
    from aisdlc.creative.filing_what_the_briefing_found import filing_what_the_briefing_found
    from aisdlc.creative.the_opportunities_this_repository_offers import (
        TheOpportunitiesThisRepositoryOffers,
    )

    what_was_opened: list[AnOpportunity] = []

    def opening(an_opportunity: AnOpportunity, _repository: Repository) -> object:
        what_was_opened.append(an_opportunity)
        raise AssertionError("an issue was opened for work that is already tracked")

    the_report = TheOpportunitiesThisRepositoryOffers(
        about=A_REPOSITORY,
        what_this_repository_is="a repository",
        opportunities=[],
        what_the_briefing_could_not_settle=[],
        agent_judgement=WhatAnAgentJudged(
            what_it_found="one thing",
            what_it_could_not_settle="one thing",
            what_it_expects_next="one thing",
        ),
    )
    an_about_being_filed = AnOpportunity(
        what_could_be_done="Add an expiry to the session cookie",
        why_it_is_worth_doing="A browser keeps the cookie for the process lifetime",
        how_it_would_be_known_to_have_worked="a test asserts the cookie carries an expiry",
        the_files_that_show_this=["src/auth.ts"],
        the_discipline_that_owns_it="DEV",
        the_risk_of_it="Touches every signed-in request",
    )

    with _pytest.raises(WorkAlreadyTrackedError):
        filing_what_the_briefing_found(
            the_report,
            [an_about_being_filed],
            opening,
            what_was_already_tracked=read_the_open_issues(*_issues_about_session_cookies()),
        )

    assert what_was_opened == [], (
        "an issue was opened for work that is already tracked, and it has to be closed by a person "
        "on a board that is not ours"
    )
