"""The tag, proved against real GitHub — the only test here that files anything.

**Everything else about this rule is proved with a stand-in for GitHub.** The other test
for the tag asserts the payload carries the project's full name and that a label which
cannot be created does not stop the filing. That is the right shape for a unit
test and it is not evidence: a payload can be exactly right and GitHub can still
ignore it, and this repository has a standing complaint about mechanisms nobody has
watched.

**So this files one real issue, reads it back, and closes it.** Read-back rather than "the call
returned 201", because the claim is that the *label is on the issue*, and the only place that claim
can be wrong is GitHub's own record of the issue. A test that trusted the status code would be
testing the mock it already trusts.

**It only runs when a deployment names both a credential and a repository to file against**, and it
skips loudly otherwise. A green run that never called GitHub is a lie, and a test that files into
somebody's repository by default is worse than a lie. **It closes the issue it opened**, so running
it twice does not leave a queue behind — though the first version's own comment called that
"idempotent" before measuring it, which is a word for a property one has to earn.

**The repository is named by the deployment and never hard-coded**, which is this system's rule
about repositories: the same code must be able to file for an arbitrary one.
"""

from __future__ import annotations

import base64
import os

import pytest

from aisdlc.domain.repository import Repository
from aisdlc.tools.github_client import a_github_client, the_credential
from aisdlc.tools.github_create_pull_request import (
    BranchOnRemote,
    a_pull_request_to_open,
    open_a_pull_request,
)
from aisdlc.tools.github_open_an_issue import AnIssueToOpen, open_an_issue
from aisdlc.tools.the_tag_this_system_leaves_on_what_it_writes import (
    the_tag_this_system_leaves,
)

THE_SETTING_NAMING_WHERE_TO_FILE = "AISDLC_THE_REPOSITORY_TO_FILE_AGAINST"


def _the_repository_to_file_against() -> str:
    return os.environ.get(THE_SETTING_NAMING_WHERE_TO_FILE, "")


def _why_this_proves_nothing() -> str | None:
    if not the_credential().strip():
        return "GITHUB_TOKEN is not set, so nothing was filed and the tag was not proven on GitHub"
    if not _the_repository_to_file_against().strip():
        return (
            f"{THE_SETTING_NAMING_WHERE_TO_FILE} is not set, so there is no repository to file "
            "against. It is not defaulted: a test that files into a repository nobody named is a "
            "test that writes to a stranger's board"
        )
    return None


@pytest.mark.skipif(
    bool(_why_this_proves_nothing()),
    reason=(
        "filing for real needs GITHUB_TOKEN and "
        f"{THE_SETTING_NAMING_WHERE_TO_FILE}. Without them the tag is proven only against a "
        "stand-in for GitHub, which is a payload assertion and not evidence."
    ),
)
def test_an_issue_filed_for_real_carries_the_projects_full_name() -> None:
    """File one, read it back, assert the label, close it.

    **The assertion is on GitHub's record of the issue rather than on what we sent it.** Sending
    `labels: [...]` is a request; the label being *on the thing* is a fact. Everything else in this
    repository's suite is about the request.
    """
    the_repository = Repository(
        owner=_the_repository_to_file_against().split("/")[0],
        name=_the_repository_to_file_against().split("/")[1],
    )
    the_client = a_github_client()
    the_tag = the_tag_this_system_leaves()

    opened = open_an_issue(
        AnIssueToOpen(
            repository=the_repository,
            title="Proving this repository's filing tag reaches GitHub",
            body=(
                "Filed by `tests/test_the_tag_reaching_real_github.py`, against real GitHub, to\n"
                "prove that an issue carries the project's full name as a label.\n\n"
                "This issue is closed by the same test that opened it. It exists because every\n"
                "other proof of this rule is a stand-in for GitHub's API, and a payload that is\n"
                "exactly right and a label that is not there look identical from the outside.\n\n"
                "If you are reading this on GitHub: the label bar on the left is the claim."
            ),
        ),
        the_client,
        the_credential(),
    )

    try:
        the_issue_as_github_has_it = the_client.get(
            f"/repos/{the_repository.owner}/{the_repository.name}/issues/{opened.number}"
        )
        assert the_issue_as_github_has_it.status_code == 200, (
            f"issue {opened.number} was filed and then could not be read back: "
            f"{the_issue_as_github_has_it.text}"
        )
        the_labels_on_it = [
            a_label["name"] for a_label in the_issue_as_github_has_it.json().get("labels", [])
        ]

        assert the_tag in the_labels_on_it, (
            f"issue {opened.number} exists on {the_repository.owner}/{the_repository.name} and "
            f"carries {the_labels_on_it}, not {the_tag!r}. The request asked for the label and "
            "GitHub did not put it there, so everything this repository asserts about the tag is "
            "asserted about a payload and not about an issue"
        )
        assert the_tag == f"{the_repository.owner}/{the_repository.name}", (
            f"the tag is {the_tag!r} and the repository's full name is "
            f"{the_repository.owner}/{the_repository.name!r}, so the tag is not the full name"
        )
    finally:
        the_client.patch(
            f"/repos/{the_repository.owner}/{the_repository.name}/issues/{opened.number}",
            json={"state": "closed"},
            headers={"Authorization": f"Bearer {the_credential()}"},
        )


def _a_branch_with_one_commit_on_it(
    client, credential: str, repository: Repository, branch: str
) -> None:
    """Push a branch carrying one commit, because a pull request needs a diff to be a pull request.

    **Through GitHub's own git API rather than a local `git push`,** because this test must not
    depend on having the repository checked out, on a remote configured, or on a credential that
    `git` understands — it is about whether the label reaches GitHub, and everything it needs to
    know about the repository it should be able to read over HTTP.

    **One file, one line, on a branch that is deleted afterwards.** The commit does not have to
    mean anything: a pull request's existence needs a difference, not a good one.
    """
    headers = {"Authorization": f"Bearer {credential}"}
    # **A commit SHA, not the name of the branch that points at one.** The repository's default
    # branch reads as `"main"`, and posting that as a `sha` produces a 422 that says "at least 40
    # characters are required" — which is GitHub complaining about the format and not about the
    # fact that the caller sent a name where a hash belongs. The first version of this did exactly
    # that, and the error described a problem the caller did not have.
    the_default_branch = client.get(
        f"/repos/{repository.owner}/{repository.name}", headers=headers
    ).json()["default_branch"]
    the_commit_it_points_at = client.get(
        f"/repos/{repository.owner}/{repository.name}/commits/{the_default_branch}",
        headers=headers,
    ).json()["sha"]
    the_branch_exists = client.post(
        f"/repos/{repository.owner}/{repository.name}/git/refs",
        json={"ref": f"refs/heads/{branch}", "sha": the_commit_it_points_at},
        headers=headers,
    )
    assert the_branch_exists.status_code == 201, (
        f"could not create the branch this proof needs: {the_branch_exists.text}"
    )

    # **Base64, because GitHub's contents API takes the file as encoded bytes.** Plain text is a
    # 422 that says "content is not valid Base64" — which is accurate, unhelpful, and about the
    # caller's encoding rather than about the thing the caller was doing.
    the_file = client.put(
        f"/repos/{repository.owner}/{repository.name}/contents/{branch}-proof.md",
        json={
            "message": "Proving the project's name reaches a pull request",
            "content": base64.b64encode(b"This file exists so a pull request has a diff.\n").decode(
                "ascii"
            ),
            "branch": branch,
        },
        headers=headers,
    )
    assert the_file.status_code == 201, f"could not write the file: {the_file.text}"


@pytest.mark.skipif(
    bool(_why_this_proves_nothing()),
    reason=(
        "a pull request has to exist before it can carry a label, and filing for one needs "
        "GITHUB_TOKEN and a repository to file against"
    ),
)
def test_a_pull_request_opened_for_real_carries_the_projects_full_name() -> None:
    """**The half that was broken, proved the way the broken half was found.**

    A pull request is opened through `open_a_pull_request` — the same function the delivery uses —
    and then read back through GitHub's record of it. **This is the test that would have caught the
    bug before it shipped**, and it is here rather than in the unit file because the unit file
    cannot: eleven assertions about the *request* all passed while every pull request arrived
    untagged. GitHub accepts a `labels` field it does not use and says nothing.

    **The branch is deleted and the pull request is closed, and those are not the same thing.** The
    first version of this comment said the pull request was deleted too, which is not a thing that
    can be done: GitHub has no endpoint for deleting a pull request, so "deleted afterwards" was a
    claim about an API that does not exist — the same kind of claim as the `labels` field, and it
    sat here for a day. **The branch is genuinely deleted**, because that one has an endpoint.

    So each run leaves one closed pull request behind, alongside the closed issue from the other
    test. Both are opt-in and both are visible evidence; a deployment running this on every push
    accumulates them, which is a cost to know about rather than a reason not to file.
    """
    the_repository = Repository(
        owner=_the_repository_to_file_against().split("/")[0],
        name=_the_repository_to_file_against().split("/")[1],
    )
    the_client = a_github_client()
    the_headers = {"Authorization": f"Bearer {the_credential()}"}
    the_tag = the_tag_this_system_leaves()
    the_branch = "proof-the-tag-reaches-a-pull-request"

    # **Inside the `try`, and that is the fix for a branch left on somebody's remote.** The first
    # version created the branch before the `try`, so when the next step failed the branch stayed
    # and the next run was refused with "Reference already exists" — an error about a state the
    # test had caused and never cleaned up, which is the worst kind: it reads like the remote
    # misbehaving and it is this file's own tidiness failing.
    try:
        _a_branch_with_one_commit_on_it(the_client, the_credential(), the_repository, the_branch)

        opened = open_a_pull_request(
            a_pull_request_to_open(
                repository=the_repository,
                head=BranchOnRemote(owner=the_repository.owner, name=the_branch),
                base="main",
                title="Proving the project's name reaches a pull request",
                body=(
                    "Opened by `tests/test_the_tag_reaching_real_github.py` to prove that a pull "
                    "request carries the project's full name as a label.\n\n"
                    "Closed and the branch deleted by the same test. This exists because GitHub's "
                    "request carries the project's full name as a label.\n\n"
                    "201 and dropping the labels without a word."
                ),
            ),
            the_client,
            the_credential(),
        )

        the_pull_request_as_github_has_it = the_client.get(
            f"/repos/{the_repository.owner}/{the_repository.name}/issues/{opened.number}",
            headers=the_headers,
        )
        assert the_pull_request_as_github_has_it.status_code == 200, (
            f"pull request {opened.number} was opened and then could not be read back: "
            f"{the_pull_request_as_github_has_it.text}"
        )
        the_labels_on_it = [
            a_label["name"]
            for a_label in the_pull_request_as_github_has_it.json().get("labels", [])
        ]

        assert the_tag in the_labels_on_it, (
            f"pull request {opened.number} exists on "
            f"{the_repository.owner}/{the_repository.name} and carries {the_labels_on_it}, not "
            f"{the_tag!r}. Every assertion this repository makes about a pull request's tag was "
            "about the request, and the request was right"
        )
    finally:
        opened = locals().get("opened")
        if opened is not None:
            the_client.patch(
                f"/repos/{the_repository.owner}/{the_repository.name}/pulls/{opened.number}",
                json={"state": "closed"},
                headers=the_headers,
            )
        the_client.delete(
            f"/repos/{the_repository.owner}/{the_repository.name}/git/refs/heads/{the_branch}",
            headers=the_headers,
        )
