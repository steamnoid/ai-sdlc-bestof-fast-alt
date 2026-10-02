"""The node that takes the offer up, on the one commit anything proved.

**A merge is the only thing this system does to somebody else's repository without asking them
again, and it happens here.** Everything before it in a delivery is an offer that a person ruled
on; this is the offer being taken up, and it is irreversible in a way a closed issue is not.

**The commit comes from the state rather than from a re-read of GitHub**, because the node before
this one was asked which commit GitHub says the pull request points at and refused to go on
unless something had proved it. Reading it again here would be a second opinion about which
commit is being merged, taken after the fact — and the whole safety property is that there is one
answer to that question and it came from the checks.

**It is a node and not part of the suite node, and the reason is the same as everywhere else in
this graph:** the suite node already returned. It cannot be something a node that has handed
control is also going to do.

**One refusal is caught here and the rest are not.** A conflict is a fact this run can act on
— there are two repairs and one of them is a rebase — so swallowing it to log it would put the
one thing that matters in the place nobody reads. The other four are facts only a person can

**And this node names its own destination, because the edge out of it is gone.** Returning a
`goto` while an edge also left the node would mean both fired: the run would reach the repair
*and* mark the work item delivered in the same step, recording a merge that never happened.
"""

from __future__ import annotations

from collections.abc import Callable

from langgraph.types import Command

from aisdlc.graph.agent_state import AgentState
from aisdlc.tools.merge_a_pull_request import (
    APullRequestToMerge,
    WhatTheMergeLanded,
)
from aisdlc.tools.why_a_pull_request_was_not_merged import (
    ThePullRequestIsInConflictError,
)

WHERE_THE_DELIVERY_IS_MERGED = "merge_the_delivery_in_this_run"
WHERE_THE_CONFLICT_IS_SETTLED = "settle_the_conflict_in_this_run"
"""Where a merge GitHub refuses as a conflict is handed on.

**Declared here and not in the repair, and the reason is the direction of the dependency.**
The merge hands a conflict to the repair and the repair imports nothing from the merge except
the one refusal both of them share — so a name the merge reads had to live on this side of that
line. Declaring it in the repair would mean importing the repair to learn where the conflict
goes, which closes a loop Python resolves by refusing to import anything at all.
"""

MergeAPullRequest = Callable[[APullRequestToMerge], WhatTheMergeLanded]
"""What the delivery is asked for the merge, and the one fact it is asked with.

**The request and nothing else**, so a merge cannot be asked for without naming the commit the
checks were read about — which is the thing that makes the merge mean *this commit or nothing*.
"""


def merge_the_delivery_in_this_run(
    state: AgentState, merge_the_pull_request: MergeAPullRequest
) -> Command:
    """Merge the pull request this run opened, on the commit GitHub says proved it.

    **One refusal is handed on and the rest keep propagating, and the narrow clause is the
    declaration.** A node that caught everything would be the place a run goes when anything goes
    wrong — a work item nobody commissioned, a graph wired out of order, a check that has not
    finished — and each of those would arrive here as a conflict to repair.

    **GitHub's own words travel with it.** The only thing this system knows about a conflict is
    what GitHub said, and a node handed *there was a conflict* has been handed a decision somebody
    else's sentence already made.
    """
    try:
        what_the_merge_landed = merge_the_pull_request(_the_merge_this_run_is_asking_for(state))
    except ThePullRequestIsInConflictError as it_is_in_conflict:
        return Command(
            goto=WHERE_THE_CONFLICT_IS_SETTLED,
            update={"the_conflict_that_stopped_this_merge": str(it_is_in_conflict)},
        )

    return Command(
        goto="mark_the_work_item_delivered",
        update={"the_commit_that_landed": what_the_merge_landed.commit},
    )


def _the_merge_this_run_is_asking_for(state: AgentState) -> APullRequestToMerge:
    """The pull request, and the commit, both read from what this run already established.

    **The commit and not a blank one, and that is not defensive.** The node before this one
    refused to hand on unless something had proved a commit, so a run reaching here with nothing
    proved was wired wrong — and a merge asking GitHub for a blank sha would be a merge allowed
    to land whatever happens to be there.
    """
    the_commit = state.get("the_commit_anything_proved")
    the_pull_request = state.get("opened_pull_request")

    if not the_commit:
        raise NothingWasProvedAboutAnyCommitError

    if the_pull_request is None:
        raise TheRunOpenedNoPullRequestToBeMergedError

    return APullRequestToMerge(
        repository=state["work_item"].repository,
        number=the_pull_request.number,
        the_commit_a_merge_may_land=the_commit,
    )


class NothingWasProvedAboutAnyCommitError(Exception):
    """The graph reached the merge with nothing proved about any commit, which is a wiring fault.

    **The delivery node writes both facts and the suite node checks one of them**, so a run
    arriving here without either was wired wrong rather than unlucky. It is raised here rather
    than being handed to GitHub as a blank sha, because a blank sha is a merge of whatever
    happens to be there.
    """


class TheRunOpenedNoPullRequestToBeMergedError(Exception):
    """The graph reached the merge with no pull request in its state, which the delivery made."""
