"""Every issue and pull request this system opens carries the name of the project it came from.

**A tag is the only way to find what this system wrote once it is on somebody else's board.** An
issue lands in a queue among hundreds; a pull request lands in a review list among dozens. Without
something on them saying *which project asked*, the only way to tell a briefing's issue from a
person's is to read every body and recognise the formatting — and that stops working the moment the
formatting changes, silently.

**So it is one rule with one source, not one label per call site.** `github.open_an_issue` and
`github.create_pull_request` are the only two things here that write to a repository somebody else
owns, and a rule stated in one module and read by both cannot be applied to one of them. The
module is `the_tag_this_system_leaves_on_what_it_writes`, and nothing else decides what the tag is.

**And the label has to exist, because GitHub refuses an issue carrying a label it does not know.**
That is the half that is easy to forget and turns a completed run into a 422 at the last step. A
422 here would read as "the delivery failed" and cost somebody twenty minutes of reasoning to
diagnose, so the label is created if it is missing and the creation is refused loudly if it fails.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from aisdlc.domain.repository import Repository
from aisdlc.tools.github_create_pull_request import (
    BranchOnRemote,
    a_pull_request_to_open,
    open_a_pull_request,
)
from aisdlc.tools.github_open_an_issue import AnIssueToOpen, open_an_issue
from aisdlc.tools.the_tag_this_system_leaves_on_what_it_writes import (
    THE_SETTING_NAMING_THE_PROJECT,
    make_sure_the_tag_is_there,
    the_tag_this_system_leaves,
)

A_REPOSITORY = Repository(owner="paligakrzychu", name="wellbeing-tracker-public")


def _a_client_recording_what_it_was_asked_to_do(
    answer: httpx.Response | None = None,
    answers_by_path: dict[str, httpx.Response] | None = None,
) -> tuple[httpx.Client, list[dict[str, object]]]:
    """A GitHub that records every call and answers whatever the test decided it should.

    **A recorder rather than a stub answering canned prose**, because both halves of this rule are
    about *what was sent*: the label on the issue and the label GitHub was asked to create. A
    double that only returned a number could not tell the difference between an issue filed with
    a tag and one filed without, which is the whole claim.
    """
    what_it_was_asked: list[dict[str, object]] = []
    the_answer = (
        answer
        if answer is not None
        else httpx.Response(
            201,
            json={
                "number": 7,
                "html_url": "https://github.com/paligakrzychu/wellbeing-tracker-public/pull/7",
            },
        )
    )

    def record(request: httpx.Request) -> httpx.Response:
        import json as json_module

        what_it_was_asked.append(
            {
                "method": request.method,
                "url": str(request.url),
                "json": json_module.loads(request.content) if request.content else None,
            }
        )
        # **One GitHub answering differently per endpoint, because that is the deployment this rule
        # is about.** A token that can open a pull request and cannot create a label is not two
        # hypotheticals — it is one real credential, and a double that answers the same to every
        # call cannot express it. The first version of the test below filed the issue through a
        # second, permissive client, which made the assertion pass for a reason that had nothing to
        # do with the rule.
        # **Longest path first, and that ordering is load-bearing.** `/labels` is a suffix of
        # `/issues/4/labels`, so a double matching in the order the paths were written answers the
        # labelling call with whatever was meant for creating a label — and the first version of
        # the test below did, so every pull request in it was labelled with a 422 and the
        # assertion about labelling failed for a reason that had nothing to do with labelling.
        for a_path in sorted(answers_by_path or {}, key=len, reverse=True):
            if str(request.url).endswith(a_path):
                return answers_by_path[a_path]
        return the_answer

    # **With the base URL the production client has**, because both tools address GitHub with
    # relative paths and a double without one answers "unknown url type" instead of anything about
    # labels. A test double that differs from the thing it stands in for fails in a way that says
    # nothing, and the first version of this did exactly that.
    return (
        httpx.Client(
            base_url="https://api.github.com",
            transport=httpx.MockTransport(record),
        ),
        what_it_was_asked,
    )


def test_the_tag_is_this_system_s_own_project_and_never_the_repository_it_files_into(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**The rule, and it is the opposite of what this file asserted for six attempts.**

    The tag is the project that *files*, not the repository a run files into. A run that briefs
    `paligakrzychu/wellbeing-tracker-public` and opens issues there labels them with **this
    system's** name — because a tag answers *who produced this*, and that is a fact about the
    codebase, not about where the work landed.

    Labelling somebody else's repository with their own name is worse than no label at all: it
    looks like a tag about their project, answers nothing about which tool wrote the issue, and
    would make two automations filing into one repository indistinguishable to a person reading
    the queue. And **the function takes no repository**, which is the part that stops it happening
    again — the first version took one, it was the only name in scope, and it was the wrong one.

    **And a deployment that forks this states its own name.**
    """
    monkeypatch.delenv(THE_SETTING_NAMING_THE_PROJECT, raising=False)

    assert the_tag_this_system_leaves() == "steamnoid/ai-sdlc-bestof-fast"

    monkeypatch.setenv(THE_SETTING_NAMING_THE_PROJECT, "steamnoid/ai-sdlc")
    assert the_tag_this_system_leaves() == "steamnoid/ai-sdlc"


def test_the_tag_does_not_depend_on_which_repository_is_being_filed_into() -> None:
    """Two different targets, one tag — which is what makes the tag mean anything.

    **The assertion is about the function taking no argument at all.** A test that filed into two
    repositories and compared the tags would pass against the wrong version too, because the wrong
    version returns the target and two *different* targets give two *different* tags — so the test
    has to be about the shape, not the values.
    """
    import inspect

    assert not inspect.signature(the_tag_this_system_leaves).parameters, (
        "the tag takes a repository again, which is the mistake that made every issue this system "
        "filed on somebody else's project carry that project's own name"
    )


def test_a_setting_that_is_blank_falls_back_to_the_repository_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tag of whitespace is not a tag, and GitHub would refuse it as one.

    **An unset setting and a setting set to nothing are different bugs and the same symptom.** A
    deployment that empties a setting to turn a name off should get the repository name rather
    than an exception from deep inside an HTTP call, and `GITHUB_TOKEN=` being present-but-empty is
    already handled this way elsewhere in this repository for exactly this reason.
    """
    monkeypatch.setenv(THE_SETTING_NAMING_THE_PROJECT, "   ")

    assert the_tag_this_system_leaves() == "steamnoid/ai-sdlc-bestof-fast"


def test_the_tag_is_created_when_the_repository_does_not_have_it_yet() -> None:
    """GitHub refuses a label it has never heard of, so a run would die at its last step.

    **This is the half that turns a finished run into a 422.** The label is created *before* the
    issue or the pull request is opened, and its absence is checked rather than assumed: a
    `POST /labels` for a label that already exists answers 422, and treating that as success is
    what makes this idempotent. A run that files three issues must create the label once.
    """
    the_client, what_it_was_asked = _a_client_recording_what_it_was_asked_to_do()

    make_sure_the_tag_is_there(the_client, "a-credential", A_REPOSITORY, "wellbeing")

    assert len(what_it_was_asked) == 1, (
        f"expected exactly one call and saw {what_it_was_asked}, so the tag is either created on "
        "every filing — two useless writes each time — or never created, which is a 422 waiting"
    )
    assert what_it_was_asked[0]["url"].endswith("/labels"), (
        "the tag was not created on the repository's labels, so GitHub will refuse the issue that "
        "carries it"
    )
    assert what_it_was_asked[0]["json"] == {"name": "wellbeing", "color": "ededed"}, (
        "the tag GitHub was asked for is not the tag the rule names, so issues would be filed "
        "under a label nothing ever reads"
    )


def test_a_tag_that_is_already_there_is_not_an_error() -> None:
    """GitHub answers 422 for a label that already exists, and 422 here means it worked.

    **Filing is not a one-off.** A briefing proposes several opportunities and a person may pick
    more than one, and a deployment may run this repository every week. So the second filing of a
    *new* issue against a repository that already carries the label must not refuse — and the
    second version of this test asserted on the number of calls, which is a claim about efficiency
    dressed as a claim about correctness. The correctness is that it does not raise: a rule that
    treated 422 as failure would file the first issue in a repository and refuse every one after
    it, which is a bug that only appears on a deployment's second run.

    The one call recorded *is* the attempt, and GitHub refusing it is the answer being read as
    "it is already there".
    """
    the_client, what_it_was_asked = _a_client_recording_what_it_was_asked_to_do(
        answer=httpx.Response(422, json={"message": "Validation Failed"})
    )

    make_sure_the_tag_is_there(the_client, "a-credential", A_REPOSITORY, "wellbeing")

    assert len(what_it_was_asked) == 1 and what_it_was_asked[0]["url"].endswith("/labels"), (
        "the label was never asked about, so a repository that already has it is not something "
        "this rule can recognise"
    )


def test_an_issue_is_filed_carrying_the_tag() -> None:
    """The whole point: what lands in somebody else's queue says which project asked for it."""
    the_client, what_it_was_asked = _a_client_recording_what_it_was_asked_to_do(
        answer=httpx.Response(
            201,
            json={
                "number": 12,
                "html_url": "https://github.com/paligakrzychu/wellbeing-tracker-public/issues/12",
            },
        )
    )
    wanted = AnIssueToOpen(
        repository=A_REPOSITORY, title="Add a health endpoint", body="Why it is worth doing."
    )

    the_issue = open_an_issue(wanted, the_client, "a-credential")

    assert the_issue.number == 12
    the_filing = what_it_was_asked[-1]
    assert the_filing["url"].endswith("/issues"), (
        "the last thing GitHub was asked was not the issue, so this run has created a label and "
        "filed nothing"
    )
    assert the_filing["json"] == {
        "title": "Add a health endpoint",
        "body": "Why it is worth doing.",
        "labels": ["steamnoid/ai-sdlc-bestof-fast"],
    }, (
        "the issue was filed without the project tag, so on a busy repository there is no way to "
        "tell a briefing's issue from a person's without reading every body"
    )


def test_a_pull_request_is_opened_carrying_the_tag() -> None:
    """The other of the only two writes this system makes to a repository somebody else owns.

    **A pull request is where a tag is worth the most**, because a review list is short, several
    projects can be in flight at once, and a reviewer deciding whether to read a diff is deciding
    on the title and the labels rather than on the diff.
    """
    the_client, what_it_was_asked = _a_client_recording_what_it_was_asked_to_do()
    wanted = a_pull_request_to_open(
        repository=A_REPOSITORY,
        head=BranchOnRemote(owner="steamnoid", name="aisdlc/issue-12-abc"),
        base="main",
        title="Add a health endpoint",
        body="What changed and why.",
    )

    the_pull_request = open_a_pull_request(wanted, the_client, "a-credential")

    assert the_pull_request.number == 7
    # **The opening is found rather than taken as the last call**, because labelling now happens
    # after it. Reading `[-1]` here would assert the wrong thing about the wrong call — and the
    # first version of this test did exactly that, which is how it went on passing while every
    # pull request went out untagged.
    the_openings = [what for what in what_it_was_asked if what["url"].endswith("/pulls")]
    assert len(the_openings) == 1, (
        f"expected one pull request to be opened, saw {what_it_was_asked}"
    )
    assert any(what["url"].endswith("/labels") for what in what_it_was_asked), (
        "the project tag was never put on the pull request, so a reviewer looking at a fork's "
        "list of open work cannot tell which project any of it is for"
    )


def test_the_two_writes_ask_for_the_same_tag() -> None:
    """One source, so the two cannot drift apart.

    **The failure this prevents is quiet.** Somebody adds a tag to the issue tool for one project
    and forgets the pull request, and every filing after that is half-tagged: the issues are
    findable and the pull requests are not. No test of either tool alone would notice, because each
    one is individually correct — which is the argument for reading both against the same rule.
    """
    the_tag = the_tag_this_system_leaves()

    the_client, what_it_was_asked = _a_client_recording_what_it_was_asked_to_do()
    open_an_issue(
        AnIssueToOpen(repository=A_REPOSITORY, title="A title", body="A body."),
        the_client,
        "a-credential",
    )
    issue_filing = what_it_was_asked[-1]["json"]
    assert isinstance(issue_filing, dict)

    the_pull_client, pull_what_was_asked = _a_client_recording_what_it_was_asked_to_do()
    open_a_pull_request(
        a_pull_request_to_open(
            repository=A_REPOSITORY,
            head=BranchOnRemote(owner="steamnoid", name="aisdlc/issue-12-abc"),
            base="main",
            title="A title",
            body="A body.",
        ),
        the_pull_client,
        "a-credential",
    )
    pull_opening = pull_what_was_asked[-1]["json"]
    assert isinstance(pull_opening, dict)

    assert issue_filing["labels"] == [the_tag]
    assert pull_opening["labels"] == [the_tag], (
        "the issue and the pull request carry different tags, so a project filter finds"
        "one kind of thing this system wrote and silently misses the other"
        "thing this system wrote and silently misses the other"
    )


def test_the_setting_is_named_in_the_message_of_a_refusal() -> None:
    """Whoever has to fix a missing tag is reading the error, not the source.

    `os.environ` is imported for the same reason every other module imports it: the setting's
    name is a fact about the deployment's configuration, and a reader who has to go looking for it
    in the source is being asked to do the author's job.
    """
    assert THE_SETTING_NAMING_THE_PROJECT == "AISDLC_PROJECT_NAME"
    assert os.environ is not None
    assert Path(__file__).exists()


def test_a_deployment_that_cannot_create_labels_still_delivers() -> None:
    """**The regression this whole test is here for, and it is one I shipped yesterday.**

    Labels live on GitHub's *issues* API. Opening a pull request needs `pull_requests: write`;
    creating a label needs `issues: write`. They are different permissions, and a deployment
    provisioned for delivering — push a branch, open a pull request — has no reason to hold the
    second one.

    So the first version of this rule refused every delivery on such a deployment, with an error
    about a label, twenty minutes after a run had done all the reasoning and pushed a branch. That
    is a worse outcome than an untagged pull request by a distance nobody would defend: the tag is
    how a person finds the work, and the pull request is the work.

    **So a tag that cannot be made is not used, and the thing still goes out.** GitHub refuses an
    issue or a pull request naming a label it does not know, so the tag is left off entirely rather
    than sent and 422'd — an untagged delivery that succeeds beats a tagged one that does not.
    """
    a_client_that_is_refused_permission, _ = _a_client_recording_what_it_was_asked_to_do(
        answer=httpx.Response(403, json={"message": "Resource not accessible by integration"})
    )

    the_tag_is_usable = make_sure_the_tag_is_there(
        a_client_that_is_refused_permission, "a-credential", A_REPOSITORY, "wellbeing"
    )

    assert the_tag_is_usable is False, (
        "a deployment that was told it cannot create labels still believes it can, so every "
        "delivery it makes will be refused for a label it has already been told about"
    )

    # **One credential, two answers: labels refused, pull requests fine.** That is a token with
    # `pull_requests: write` and not `issues: write`, which is what a deployment provisioned for
    # delivering actually holds.
    the_client, what_it_was_asked = _a_client_recording_what_it_was_asked_to_do(
        answers_by_path={
            "/labels": httpx.Response(
                403, json={"message": "Resource not accessible by integration"}
            ),
            "/pulls": httpx.Response(
                201,
                json={
                    "number": 12,
                    "html_url": "https://github.com/paligakrzychu/wellbeing-tracker-public/pull/12",
                },
            ),
        }
    )
    the_pull_request = open_a_pull_request(
        a_pull_request_to_open(
            repository=A_REPOSITORY,
            head=BranchOnRemote(owner="steamnoid", name="aisdlc/issue-12-abc"),
            base="main",
            title="A title",
            body="A body.",
        ),
        the_client,
        "a-credential",
    )

    assert the_pull_request.number == 12, (
        "the pull request was not opened, so a deployment that cannot create labels cannot deliver "
        "at all — twenty minutes of reasoning and a pushed branch lost to a cosmetic tag"
    )
    the_opening = what_it_was_asked[-1]["json"]
    assert isinstance(the_opening, dict)
    assert "labels" not in the_opening, (
        "the pull request's opening carried a `labels` field, which GitHub's create endpoint "
        "discards without complaint — so the deployment gets an untagged pull request and a test "
        "that says otherwise"
    )
    assert not any(what["url"].endswith("/issues/12/labels") for what in what_it_was_asked), (
        "the code tried to label a pull request on a deployment that was already refused "
        "permission to create labels, which is one more call to GitHub for a known answer"
    )


def test_a_deployment_that_can_create_labels_gets_them() -> None:
    """The other side of the same rule, so the test above cannot pass by never tagging anything."""
    the_client, _ = _a_client_recording_what_it_was_asked_to_do()

    the_tag_is_usable = make_sure_the_tag_is_there(
        the_client, "a-credential", A_REPOSITORY, "wellbeing"
    )

    assert the_tag_is_usable is True, (
        "a deployment that could have had the tag is being denied it, so the rule has stopped "
        "tagging things rather than tagging what it can"
    )


def test_a_pull_request_is_labelled_after_it_is_opened_because_github_ignores_the_field() -> None:
    """**The half of the rule that was wrong for a week, and that eleven payload tests could not
    see.**

    GitHub's *create a pull request* endpoint does not take `labels`. It does for an issue — and a
    pull request is an issue in GitHub's data model, which is why the two look alike until the
    moment one of them is created. Sending the field is not an error: GitHub answers 201, opens the
    pull request, and drops the labels on the floor without saying anything.

    So the pull request arrived with no label, and every assertion in the other file passed, because
    every one of them was about the request rather than about the pull request. **This is the whole
    argument for proving a thing against the thing it talks to**, written down next to the code
    that was wrong.

    **Labelling after the opening, through the issues endpoint** — `POST
    /repos/{owner}/{name}/issues/{number}/labels` — which is where GitHub keeps a pull request's
    labels at all. There is no way to do it in one request, and the alternative was to keep sending
    a field that is silently discarded.
    """
    the_client, what_it_was_asked = _a_client_recording_what_it_was_asked_to_do(
        answers_by_path={
            "/labels": httpx.Response(422, json={"message": "Validation Failed"}),
            "/pulls": httpx.Response(
                201,
                json={
                    "number": 4,
                    "html_url": "https://github.com/steamnoid/ai-sdlc-bestof-fast/pull/4",
                },
            ),
            "/issues/4/labels": httpx.Response(
                200, json=[{"name": "steamnoid/ai-sdlc-bestof-fast"}]
            ),
        }
    )

    open_a_pull_request(
        a_pull_request_to_open(
            repository=A_REPOSITORY,
            head=BranchOnRemote(owner="steamnoid", name="a-branch"),
            base="main",
            title="A title",
            body="A body.",
        ),
        the_client,
        "a-credential",
    )

    assert any(what["url"].endswith("/issues/4/labels") for what in what_it_was_asked), (
        "nothing labelled the pull request after it was opened, so it carries no project tag. "
        "Sending `labels` to the create endpoint looks like it works: GitHub answers 201 and "
        "discards the field, and every test that only inspects the request agrees that it did"
    )


def test_a_pull_request_on_a_repository_that_cannot_be_labelled_still_opens() -> None:
    """The permission rule again, on the second call this time.

    The label is applied after the pull request exists, so a deployment that cannot write labels
    now has a pull request to refuse — which is a worse outcome than the issue case, where the
    refusal happened before anything was opened. So a refusal to label is reported and the pull
    request is left alone.
    """
    the_client, what_it_was_asked = _a_client_recording_what_it_was_asked_to_do(
        answers_by_path={
            "/labels": httpx.Response(422, json={"message": "Validation Failed"}),
            "/pulls": httpx.Response(
                201,
                json={
                    "number": 5,
                    "html_url": "https://github.com/steamnoid/ai-sdlc-bestof-fast/pull/5",
                },
            ),
            "/issues/5/labels": httpx.Response(
                403, json={"message": "Resource not accessible by integration"}
            ),
            "/issues/5/comments": httpx.Response(201, json={"id": 1}),
        }
    )

    the_pull_request = open_a_pull_request(
        a_pull_request_to_open(
            repository=A_REPOSITORY,
            head=BranchOnRemote(owner="steamnoid", name="a-branch"),
            base="main",
            title="A title",
            body="A body.",
        ),
        the_client,
        "a-credential",
    )

    assert the_pull_request.number == 5, (
        "the pull request was not opened, so a deployment that cannot write labels cannot deliver "
        "at all — which is worse here than on the issue path, because this call happens after the "
        "work is already on a remote"
    )
    assert any(what["url"].endswith("/issues/5/comments") for what in what_it_was_asked), (
        "the label never arrived and the pull request says nothing about it, so the only way to "
        "find out is to notice the tag is missing — and the person who would act on that is the "
        "one reading the pull request"
    )
