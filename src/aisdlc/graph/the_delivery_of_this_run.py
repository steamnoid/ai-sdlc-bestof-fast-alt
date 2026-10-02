"""Every collaborator that delivers, named by what it is asked for.

The mirror image of `TheAgentsThisRun`, and separate from it for one reason: **none of these
reasons.** §10 gives the PR agent four responsibilities — prepare the change summary, prepare
the title and body, verify that the required gates passed, create the pull request only after
explicit human approval — and not one of them is a model call. Putting them in the type that
exists to say what a run reasons *with* would put a lie in it, and `aisdlc-pr` is the agent
identifier this run's work item carries through its last three moves.

**No default, and that is the point.** A run built without a delivery is a run that verifies a
change, writes a branch name into a file, and stops — which is what this pipeline did, and
which reads from the outside exactly like success. So a caller has to say how the run delivers
or the graph cannot be assembled at all.

`our_copy` is here rather than read from the environment inside the graph, because
`the_account_we_fork_into` is where the environment is read and the fork tool's own rule is
that every address-shaped decision lives in the tools. It also means the unit tier, which
reads no environment variable, can build a run.
"""

from __future__ import annotations

from pydantic import BaseModel

from aisdlc.domain.repository import Repository
from aisdlc.graph.deliver_node import OpenThePullRequest, PushTheBranch
from aisdlc.graph.suite_node import AskWhetherTheSuiteWentGreen


class TheDeliveryOfThisRun(BaseModel):
    """Whose copy to deliver from, and the three things that land the delivery on a remote.

    **The third one is asked about the remote's own record, and that is a different kind of
    fact from the other two.** `push_the_branch` and `open_the_pull_request` put a delivery on
    GitHub; `ask_whether_the_suite_went_green` reads back what GitHub says about it. A run that
    can do the first two and not the third reports a delivery on the strength of its own
    intention, which is the one claim a delivery must not make about somebody else's repository.
    """

    our_copy: Repository
    push_the_branch: PushTheBranch
    open_the_pull_request: OpenThePullRequest
    ask_whether_the_suite_went_green: AskWhetherTheSuiteWentGreen
