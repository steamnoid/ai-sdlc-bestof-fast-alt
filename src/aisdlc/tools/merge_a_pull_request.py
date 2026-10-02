"""`github.merge_a_pull_request`: the step after a delivery, and the last one this system takes.

**A merge is the only thing here that changes somebody else's repository without asking them
again.** Everything before it in a delivery is an offer; this is the offer being taken up, and it
is irreversible in a way a closed issue is not.

**A merge is asked about before it is attempted, and the reason is one repeated word.** GitHub
answers *"Pull Request is not mergeable"* for a pull request that conflicts with its base — which
a run can rebase and try again — and for a base branch that is **protected**, which no amount of
rebasing will fix. Classifying the refusal by reading that phrase calls the second one a conflict
and **sends a person after a merge conflict on a branch that is protected on purpose.** So
`mergeable` is read first and is the only thing that may call something a conflict.

**The commit a merge may land is an argument, because the checks were read about a commit.** The
suite was read green for this pull request's head sha a moment earlier, and a head that moved
since — a rebase, an "update branch", a second run pushing the same branch — is a commit nothing
was proved about. **Handing the sha to GitHub is what makes the merge mean *this commit or
nothing***, and it is GitHub that refuses the attempt rather than this system noticing
afterwards.

**`null` is its own refusal, and it is a fact GitHub states rather than a gap in this tool.**
GitHub computes a merge conflict in the background, so a pull request asked about seconds after
it was opened answers `mergeable: null`. `true` would merge whatever happened to be there;
`false` would accuse it of a conflict nobody has established.

**No merge method is chosen here.** Whether a repository merges, squashes or rebases is that
repository's setting, and a system that picked one would silently change how every repository it
delivers to records history — so the body carries the sha and nothing else.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from aisdlc.domain.repository import Repository
from aisdlc.tools.github_client import THE_SETTING_NAMING_THE_CREDENTIAL
from aisdlc.tools.github_create_pull_request import what_github_said
from aisdlc.tools.why_a_pull_request_was_not_merged import (
    GitHubHasNotSaidWhetherItCanBeMergedYetError,
    TheMergeWasRefusedByGitHubError,
    ThePullRequestCouldNotBeReadError,
    ThePullRequestIsInConflictError,
)

WHERE_GITHUB_KEEPS_THE_PULL_REQUEST = "/repos/{owner}/{name}/pulls/{number}"

GITHUB_OKAY = 200
SECONDS_A_READ_MAY_TAKE = 10


class APullRequestToMerge(BaseModel):
    """The pull request to merge, and the one commit a merge is allowed to land.

    **The commit is required and is not a default.** It is the sha the suite was read green on,
    and a merge that may land any commit is a merge that may land one nothing was proved about.
    `number` and not the whole address, because the endpoint is keyed by number and a string
    address would be a link parsed back into one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository: Repository
    number: int
    the_commit_a_merge_may_land: str

    @field_validator("the_commit_a_merge_may_land")
    @classmethod
    def _refuse_a_merge_of_nothing_in_particular(cls, the_commit: str, info: ValidationInfo) -> str:
        """Refuse a blank commit, which is a merge allowed to land anything.

        **Raised where the field is filled rather than at the merge.** A caller that forgot the
        commit should be told before it reaches the network, and the exception says what a blank
        one would have meant rather than only that it is empty.
        """
        if the_commit.strip():
            return the_commit

        raise ValueError(
            "a merge names the commit it may land, because that is the commit the checks were "
            "read about. A blank one is a merge of whatever happens to be there. "
            f"(number={info.data.get('number')})"
        )


class WhatTheMergeLanded(BaseModel):
    """The commit now in the base branch, and GitHub's own sentence about it.

    **Both halves are GitHub's answer rather than ours.** The commit is the fact a reader will
    look for in the base branch's history, and a system that paraphrases a remote's confirmation
    is a system that can be wrong about a merge having happened.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    commit: str
    what_github_said: str


def merge_a_pull_request(
    client: httpx.Client,
    wanted: APullRequestToMerge,
    credential: str,
) -> WhatTheMergeLanded:
    """Merge it, on the one commit the checks were read about, or say in GitHub's words why not.

    **The credential, then the pull request, then the merge — and that order is the whole
    contract.** Nothing is attempted without a credential; the pull request is asked about before
    anything is pushed at it, because `mergeable` is the only field that tells a conflict from a
    protected branch; and the merge itself carries the commit, so a head that moved under all of
    this is refused by GitHub rather than noticed here afterwards.
    """
    _refuse_a_merge_with_no_credential(credential)

    _refuse_a_pull_request_that_cannot_be_merged(
        _whether_github_says_it_can_be_merged(client, wanted), wanted
    )

    return _the_merge_github_performed(client, wanted, credential)


def _refuse_a_merge_with_no_credential(credential: str) -> None:
    """Refuse by name, before any request, because a 401 explains neither setting nor permission.

    **A merge is somebody else's decision being carried out**, and nobody cannot carry one out.
    """
    if credential.strip():
        return

    raise TheMergeWasRefusedByGitHubError(
        f"{THE_SETTING_NAMING_THE_CREDENTIAL} is not set, so there is no account to merge as. A "
        "merge is somebody else's decision being carried out on their repository, and nobody "
        "cannot carry one out"
    )


def _whether_github_says_it_can_be_merged(
    client: httpx.Client, wanted: APullRequestToMerge
) -> bool | None:
    """The `mergeable` field, verbatim: `True`, `False`, or `None` while GitHub is still deciding.

    **Read as three states and not two, and the third is the one this exists for.** A `200` with
    no field at all, or with a field that is not a boolean, is `None` rather than permission —
    an absent answer is not consent to do something irreversible.
    """
    answer = client.get(
        WHERE_GITHUB_KEEPS_THE_PULL_REQUEST.format(
            owner=wanted.repository.owner,
            name=wanted.repository.name,
            number=wanted.number,
        ),
        timeout=SECONDS_A_READ_MAY_TAKE,
    )

    if answer.status_code != GITHUB_OKAY:
        raise ThePullRequestCouldNotBeReadError(
            f"GitHub answered {answer.status_code} when asked whether pull request "
            f"{wanted.number} of {wanted.repository.address} can be merged, so nothing is known "
            f"about merging it. GitHub said: {what_github_said(answer)}"
        )

    what_github_said_about_it = answer.json().get("mergeable")

    if not isinstance(what_github_said_about_it, bool):
        return None

    return what_github_said_about_it


def _refuse_a_pull_request_that_cannot_be_merged(
    can_it_be_merged: bool | None, wanted: APullRequestToMerge
) -> None:
    """Two refusals from one field, and no merge is attempted in either case.

    **A conflict and an unfinished judgement are different facts with different remedies.** A
    conflict can be rebased and tried again; `null` means GitHub has not decided and the answer
    is to ask again. Neither is a refusal by GitHub, so neither is dressed up as one — and
    neither reaches the merge endpoint, because a merge attempted against either is a merge
    GitHub decides rather than one this system decided.
    """
    if can_it_be_merged is False:
        raise ThePullRequestIsInConflictError(
            f"GitHub says pull request {wanted.number} of {wanted.repository.address} conflicts "
            f"with the branch it would join, and it cannot be merged as it stands. The commit it "
            f"would have landed is {wanted.the_commit_a_merge_may_land}. This is a conflict and "
            "not a refusal: a protected base branch is refused instead, and GitHub words the two "
            "the same way, which is why this is read from the field and not from the message"
        )

    if can_it_be_merged is None:
        raise GitHubHasNotSaidWhetherItCanBeMergedYetError(
            f"GitHub has not finished saying whether pull request {wanted.number} of "
            f"{wanted.repository.address} can be merged. It computes a merge conflict in the "
            "background and answers null until it has one, and this run will not read null as "
            "permission to merge whatever is there or as an accusation that there is a conflict"
        )


def _the_merge_github_performed(
    client: httpx.Client, wanted: APullRequestToMerge, credential: str
) -> WhatTheMergeLanded:
    """Ask for the merge of exactly this commit, and believe GitHub only if it says it merged.

    **The sha in the body is the guarantee and GitHub's `merged` is the confirmation.** A `200`
    that says `merged: false` has merged nothing, and a run reporting a delivery from it would be
    reporting one that did not happen. Everything else is quoted: 405, 409 and 410 are three
    different problems and this system cannot tell them apart from the prose.
    """
    answer = client.put(
        WHERE_GITHUB_KEEPS_THE_PULL_REQUEST.format(
            owner=wanted.repository.owner,
            name=wanted.repository.name,
            number=wanted.number,
        ),
        json={"sha": wanted.the_commit_a_merge_may_land},
        headers={
            "Authorization": f"Bearer {credential}",
            "Accept": "application/vnd.github+json",
        },
        timeout=SECONDS_A_READ_MAY_TAKE,
    )

    what_it_said = what_github_said(answer)
    landed = answer.json().get("merged") if answer.status_code == GITHUB_OKAY else None

    if answer.status_code != GITHUB_OKAY or landed is not True:
        raise TheMergeWasRefusedByGitHubError(
            f"GitHub answered {answer.status_code} and said {landed!r} when asked to merge pull "
            f"request {wanted.number} of {wanted.repository.address} on commit "
            f"{wanted.the_commit_a_merge_may_land}, so the commit about to be merged did not "
            f"land in the base branch. GitHub said: {what_it_said}"
        )

    return WhatTheMergeLanded(
        commit=wanted.the_commit_a_merge_may_land, what_github_said=what_it_said
    )
