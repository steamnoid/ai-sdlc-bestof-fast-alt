"""A delivery built from the environment, which is the one the real run gets.

**The only place the environment is read for a delivery**, and it is here rather than in the
graph for the reason the fork tool reads its own: a node that read a setting would make the
unit tier — which reads none — unable to run at all, and would put an address-shaped decision
in a file whose job is routing.

**Both halves read the environment when they are *called*, not when this factory runs.** A
factory that read the settings at import would freeze one deployment's account into a process,
and a run resumed tomorrow would push to yesterday's fork. The clone collaborator already
works this way for the same reason and says so.

**The account is named once and used twice.** `our_copy` and the push both have to agree about
whose copy of the repository this is; reading it in two places would make a deployment with
two accounts a delivery that pushes to one and opens against the other, which fails at GitHub
with a 422 about a head that is not there.
"""

from __future__ import annotations

from aisdlc.domain.repository import Repository
from aisdlc.graph.deliver_node import OpenThePullRequest, PushTheBranch
from aisdlc.graph.merge_node import MergeAPullRequest
from aisdlc.graph.suite_node import AskWhetherTheSuiteWentGreen
from aisdlc.graph.the_delivery_of_this_run import TheDeliveryOfThisRun
from aisdlc.tools.github_client import a_github_client, the_credential
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.github_create_branch import (
    PushedBranch,
    a_branch_to_push,
    create_a_branch_on_a_remote,
)
from aisdlc.tools.github_create_pull_request import (
    AnOpenedPullRequest,
    PullRequestToOpen,
    open_a_pull_request,
)
from aisdlc.tools.github_fork_repository import the_account_we_fork_into
from aisdlc.tools.merge_a_pull_request import (
    APullRequestToMerge,
    WhatTheMergeLanded,
    merge_a_pull_request,
)
from aisdlc.tools.the_suite_went_green import WhatTheSuiteSaid, the_suite_went_green


def the_delivery_this_system_may_make(repository: Repository) -> TheDeliveryOfThisRun:
    """The delivery for a run working on `repository`, built from this deployment's settings.

    The repository is an argument and the account is read, because the account names *which*
    copy of *that* repository is ours — a run that forked `wellbeing-tracker-public` into one
    account and pushed to another would produce a pull request nobody can merge.
    """
    our_copy = Repository(owner=the_account_we_fork_into(), name=repository.name)

    return TheDeliveryOfThisRun(
        our_copy=our_copy,
        push_the_branch=_a_branch_pusher(our_copy),
        open_the_pull_request=_a_pull_request_opener(),
        ask_whether_the_suite_went_green=_someone_who_asks_github_whether_the_suite_went_green(
            our_copy
        ),
        merge_the_pull_request=_someone_who_merges_the_pull_request(),
    )


def _a_branch_pusher(our_copy: Repository) -> PushTheBranch:
    """Push the branch to our copy of the repository, refusing rather than moving a branch.

    The refusal lives in `create_a_branch_on_a_remote`, which asks the remote before it pushes
    and will not move a branch it did not create. That check is the reason this is a thin
    wrapper and not the whole thing written again here.
    """

    def pushing(clone: ClonedRepository, branch_name: str) -> PushedBranch:
        return create_a_branch_on_a_remote(
            clone, a_branch_to_push(clone, branch_name), our_copy
        )

    return pushing


def _someone_who_asks_github_whether_the_suite_went_green(
    our_copy: Repository,
) -> AskWhetherTheSuiteWentGreen:
    """Ask GitHub about the commit the delivery pushed, with this deployment's own copy first.

    **Which copy is named here and not inside the tool**, because a run that pushed to one fork
    and asked about another fork's pull request would be reading somebody else's checks. The
    address-shaped decision lives in the tools rather than spread through the graph, which is the
    rule every other collaborator here follows.
    """

    def asking(the_pull_request: AnOpenedPullRequest, repository: Repository) -> WhatTheSuiteSaid:
        return the_suite_went_green(
            a_github_client(), the_pull_request, our_copy
        )

    return asking


def _someone_who_merges_the_pull_request() -> MergeAPullRequest:
    """Merge it with this deployment's own credential, read when the call is made.

    **The credential is read here and not carried in the seam**, so a deployment that forgets it
    finds out at the merge with a sentence naming the setting — and not after the merge has
    already been attempted.
    """

    def merging(wanted: APullRequestToMerge) -> WhatTheMergeLanded:
        return merge_a_pull_request(a_github_client(), wanted, the_credential())

    return merging


def _a_pull_request_opener() -> OpenThePullRequest:
    """Open it with this deployment's credential, read when the call is made.

    `open_a_pull_request` refuses an empty credential before it attempts anything, because a
    pull request cannot be opened anonymously — it is somebody's decision to review.
    """

    def opening(wanted: PullRequestToOpen) -> AnOpenedPullRequest:
        return open_a_pull_request(wanted, a_github_client(), the_credential())

    return opening
