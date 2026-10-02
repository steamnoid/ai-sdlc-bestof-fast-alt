"""That a conflicting delivery is settled by naming one of two repairs, and not by a coin.

**A pull request that will not merge has exactly two repairs, and offering anything else would be
a choice between an action this run can take and one it cannot.** That is a coin rather than a
decision — and §0.3 is about exactly this: a model asked to choose between an option that works
and one that does not will land on either with no reason to prefer it. Both repairs here are
things a run can do. Rebase the branch and try again; or leave the pull request open with a note
saying why.

**The answer is a name and no prose.** The options are English sentences and they are the only
answers accepted, for the reason this repository has already learned the hard way about prompts:
*a prompt that says do not do X is not a check that X did not happen.* So the answer is a name, an
answer outside the set is refused by name, and **a decision with no reason behind it is refused
too** — a verdict with no grounds is a coin flip written down at the one place a coin flip is
worst.

**And what is known is passed in as the caller's own words, never summarised here.** A decision
made on a summary of a conflict is a decision about the summary. Whoever holds the conflict holds
the facts about it — the tool that refused read them from GitHub — and this cycle only asks the
question and validates the answer.

**Only the conflict a delivery can reach, and that is a decision rather than a narrowness.** A
sibling project carries three: a pull request that will not merge, an opportunity already filed as
somebody else's issue, and two runs having changed one file. **Two of the three do not exist
here** — the duplicate filing is refused by its own rule with nothing routing it, and a branch
that moved under a run has no refusal at all — so a set of three would be two answers with no
caller, which is the shape this repository deleted before.

**A fake model, because this is the contract and not the reasoning.** §0.3 puts reasoning quality
in `evals/` and never in pytest. What pytest owns is that a malformed answer is refused and that
the two names lead to two different places.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from langgraph.types import Command

from aisdlc.agents.pull_request_request import PullRequestRequest
from aisdlc.agents.what_to_do_when_a_pull_request_will_not_merge import (
    AnAnswerThatIsNotADecisionError,
    WhatToDoAroundAConflict,
    WhatToDoWhenThePullRequestWillNotMerge,
)
from aisdlc.domain.commissioned_request import a_request_about
from aisdlc.domain.repository import Repository
from aisdlc.domain.role import Role
from aisdlc.domain.work_item import a_work_item_commissioned_for_an_agent
from aisdlc.graph.agent_state import AgentState
from aisdlc.graph.merge_node import (
    WHERE_THE_CONFLICT_IS_SETTLED,
    merge_the_delivery_in_this_run,
)
from aisdlc.graph.router import THE_RUN_IS_OVER
from aisdlc.graph.settle_a_conflict_node import settle_a_conflict_in_this_run
from aisdlc.graph.suite_node import WHERE_THE_SUITE_IS_ASKED_ABOUT
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.github_create_pull_request import AnOpenedPullRequest
from aisdlc.tools.merge_a_pull_request import (
    APullRequestToMerge,
    ThePullRequestIsInConflictError,
    WhatTheMergeLanded,
)
from aisdlc.tools.our_own_runs import a_delivery_branch_named
from aisdlc.tools.rebase_the_branch_a_run_pushed import WhatTheRebaseLanded
from aisdlc.tools.the_suite_went_green import TheSuiteHasNotFinishedYetError

WHERE_A_RUN_GOES_BACK_TO = WHERE_THE_SUITE_IS_ASKED_ABOUT
WHERE_A_RUN_IS_OVER = THE_RUN_IS_OVER

THE_COMMIT_THE_CHECKS_WERE_READ_ABOUT = "b" * 40
THE_COMMIT_THE_CLONE_STANDS_ON = "a" * 40
THE_BRANCH_THE_DELIVERY_JOINS = "main"
THE_CONFLICT_IN_GITHUBS_WORDS = (
    "GitHub says pull request 10 of paligakrzychu/wellbeing-tracker-public conflicts with the "
    "branch it would join, and it cannot be merged as it stands."
)


class _AModelThatAnswers:
    """A model whose answers are already decided, recording every question it was asked."""

    def __init__(self, what_it_answers: list[object]) -> None:
        self._what_it_answers = what_it_answers
        self.what_it_was_asked: list[str] = []

    def with_structured_output(self, *arguments: object, **keywords: object) -> object:
        """LangChain's entry point, and the answers are decided, so this is already the model."""
        return self

    def invoke(self, the_question: str) -> object:
        self.what_it_was_asked.append(the_question)
        return self._what_it_answers.pop(0)


def _the_state_a_conflict_reaches_the_run_in() -> AgentState:
    """A delivery that got as far as the merge, and nothing has proved the commit after it.

    **`the_commit_anything_proved` is set, because the checks were read about it.** A run that
    reached the merge refused as a conflict has already been told the suite was green for a
    commit, and that commit is the lease a rebase has to be pushed under — so an absent one would
    be a run that was wired wrong rather than a run that hit a conflict.
    """
    return AgentState(
        work_item=_a_work_item_holding_a_delivery(),  # type: ignore[typeddict-item]
        projects_root=Path("a-projects-root-this-run-never-writes-to"),  # type: ignore[typeddict-item]
        clone=_a_clone_of_the_delivery(),  # type: ignore[typeddict-item]
        requested_stage=None,  # type: ignore[typeddict-item]
        requested_agent=None,  # type: ignore[typeddict-item]
        requested_role=None,  # type: ignore[typeddict-item]
        the_commit_anything_proved=THE_COMMIT_THE_CHECKS_WERE_READ_ABOUT,  # type: ignore[typeddict-item]
        opened_pull_request=AnOpenedPullRequest(  # type: ignore[typeddict-item]
            number=10, address="https://example.invalid/p/pull/10"
        ),
        pull_request_request=_the_request_the_delivery_opened_it_with(),  # type: ignore[typeddict-item]
    )


def _the_request_the_delivery_opened_it_with() -> PullRequestRequest:
    """What the delivery recorded when it opened the pull request, where both branches live.

    **The branch is the one the delivery derived, not one written here.** `deliver_node` named it
    and put it in the state, and this repair reads it back rather than deriving a third name — so a
    test cannot pass by agreeing with itself about a branch the run never pushed.
    """
    work_item = _a_work_item_holding_a_delivery()

    return PullRequestRequest(
        repository=work_item.repository,
        work_item_id=work_item.work_item_id,
        branch=a_delivery_branch_named(work_item.work_item_id),
        base=THE_BRANCH_THE_DELIVERY_JOINS,
        title="add a health endpoint",
        body="what changed and what was verified",
    )


def _a_work_item_holding_a_delivery() -> Any:
    return a_work_item_commissioned_for_an_agent(
        work_item_id="a-delivery-github-would-not-merge",
        repository=Repository(owner="paligakrzychu", name="wellbeing-tracker-public"),
        accountable_role=Role.DEV,
        commissioned_by="a person reading a test",
        requested=a_request_about("add a health endpoint", ""),
    )


def _a_clone_of_the_delivery() -> ClonedRepository:
    """A clone standing on `main`, which is the branch the delivery joined and would rejoin.

    **`ref` is the base branch and not a commit.** It is the one fact a rebase needs that lives
    nowhere else in the run's state, and the delivery already read it to build the pull request —
    so it is read here the same way rather than re-derived from a constant that could drift away
    from the branch the pull request actually joins.
    """
    return ClonedRepository(
        path=Path("the-clone"), ref="main", commit=THE_COMMIT_THE_CLONE_STANDS_ON
    )


def _the_rebase_that_records_what_it_was_asked_with() -> tuple[Any, list[str]]:
    """A rebase that answers `WhatTheRebaseLanded` and writes down what it was asked to do."""
    what_it_was_asked_with: list[str] = []

    def rebase(
        the_clone: Path,
        the_commit_the_branch_is_at: str,
        this_runs_branch: str,
        the_branch_it_joins: str,
    ) -> WhatTheRebaseLanded:
        what_it_was_asked_with.append(
            f"{this_runs_branch} onto {the_branch_it_joins} "
            f"under the lease {the_commit_the_branch_is_at}"
        )
        return WhatTheRebaseLanded(commit="e" * 40, what_git_said="forced update")

    return rebase, what_it_was_asked_with


def test_naming_the_rebase_rebases_the_branch_and_puts_the_run_back_to_the_suite_question() -> None:
    """The repair named is the repair taken, and asking again is the only way to learn it worked.

    **The four arguments are named in the assertion, because each one is a fact taken from
    somewhere else.** The branch is what the delivery was cut onto, the branch it joins is the
    clone's own `ref`, and the lease is the commit the checks were read about — a rebase handed a
    blank lease would push over anything.
    """
    rebase, what_it_was_asked_with = _the_rebase_that_records_what_it_was_asked_with()
    the_model = _AModelThatAnswers(
        [
            {
                "the_repair": (
                    WhatToDoWhenThePullRequestWillNotMerge.REBASE_IT_AND_TRY_AGAIN.value
                ),
                "why": "the branch has fallen behind and replaying it is the whole of the fix",
            }
        ]
    )

    where_it_went = settle_a_conflict_in_this_run(
        _the_state_a_conflict_reaches_the_run_in(),
        the_model,  # type: ignore[arg-type]
        rebase,
        THE_CONFLICT_IN_GITHUBS_WORDS,
    )

    assert len(what_it_was_asked_with) == 1, (
        f"the run chose the rebase and rebased {len(what_it_was_asked_with)} times, which is "
        "either nothing or a loop"
    )
    assert (
        f"under the lease {THE_COMMIT_THE_CHECKS_WERE_READ_ABOUT}" in (what_it_was_asked_with[0])
    ), (
        f"the rebase was asked for {what_it_was_asked_with[0]!r} without the commit the branch is "
        "expected to be at. A lease of nothing moves whatever is there"
    )
    assert f"onto {THE_BRANCH_THE_DELIVERY_JOINS}" in what_it_was_asked_with[0], (
        f"the rebase was asked for {what_it_was_asked_with[0]!r} and not onto the branch the "
        "delivery joined. Rebasing onto anything else is a delivery that ignored its own base"
    )

    assert where_it_went.goto == WHERE_A_RUN_GOES_BACK_TO, (
        f"the run rebased and then went to {where_it_went.goto!r} rather than back to the suite "
        "question. A rebase changes what GitHub can say about the pull request, so asking again "
        "is the only move that learns whether it worked"
    )


def test_leaving_it_open_leaves_it_open_and_says_why_on_the_card() -> None:
    """The other name leads somewhere else, and a run that stops says so rather than going quiet."""

    def rebase(*arguments: object) -> WhatTheRebaseLanded:
        raise AssertionError("the run chose to leave it open and rebased anyway")

    the_model = _AModelThatAnswers(
        [
            {
                "the_repair": (
                    WhatToDoWhenThePullRequestWillNotMerge.LEAVE_IT_OPEN_AND_SAY_WHY.value
                ),
                "why": "the base branch is protected on purpose, so a rebase would land nowhere",
            }
        ]
    )

    where_it_went = settle_a_conflict_in_this_run(
        _the_state_a_conflict_reaches_the_run_in(),
        the_model,  # type: ignore[arg-type]
        rebase,  # type: ignore[arg-type]
        THE_CONFLICT_IN_GITHUBS_WORDS,
    )

    assert where_it_went.goto == WHERE_A_RUN_IS_OVER, (
        f"the run chose to leave the pull request open and went to {where_it_went.goto!r}"
    )
    assert where_it_went.update, (
        "a run that stops because it chose to stop wrote nothing to the card. A run that returns "
        "quietly reads as a run that finished, and this one did not finish"
    )
    what_it_said = "".join(str(each) for each in where_it_went.update.values())
    assert "protected" in what_it_said, (
        f"the card says {what_it_said!r} and not the reason the run itself gave. The only place "
        "a person reads why a delivery stopped is the note this run leaves"
    )


def test_the_grounds_are_left_on_the_card_which_ever_repair_was_named() -> None:
    """A model gave a reason. A run that discards it has made a decision and hidden its grounds.

    **Found by a real model and not by any unit test.** Asked which repair to take, the model
    named the rebase and said why — and the run rebased and wrote nothing down. The grounds were
    on the card for *one* of the two repairs and for neither of the other half of the behaviour:
    `_a_rebase_is_taken` returned a bare `goto`, so the branch where the run **does something** was
    the branch that kept no record of why it did it.

    **A decision nobody can explain third is not a decision that happened.** Every other verdict in
    this package carries its grounds for the same reason `ApprovalDecision.reason` is required — a
    reason is the only thing a reader has when the run is rebase'd twice on a branch that is still
    behind — and this one was the only verdict whose grounds were dropped on the way past.
    """
    the_model = _AModelThatAnswers(
        [
            {
                "the_repair": (
                    WhatToDoWhenThePullRequestWillNotMerge.REBASE_IT_AND_TRY_AGAIN.value
                ),
                "why": "the branch has fallen behind and replaying it is the whole of the fix",
            }
        ]
    )

    where_it_went = settle_a_conflict_in_this_run(
        _the_state_a_conflict_reaches_the_run_in(),
        the_model,  # type: ignore[arg-type]
        lambda *arguments: WhatTheRebaseLanded(commit="e" * 40, what_git_said="forced update"),
        THE_CONFLICT_IN_GITHUBS_WORDS,
    )

    assert where_it_went.update, (
        "the run rebased and wrote nothing to the card. The model named a repair and said why, and "
        "a run that discards the grounds of a decision it acted on leaves a person reading a "
        "rebase with nothing to read"
    )
    what_it_said = "".join(str(each) for each in where_it_went.update.values())
    assert "fallen behind" in what_it_said, (
        f"the card says {what_it_said!r} and not the grounds the model itself gave. The only place "
        "a person reads why a delivery stopped is the note this run leaves, and a paraphrase "
        "written here would be a reason nobody gave"
    )


def test_the_conflict_reaches_the_model_in_the_words_github_used() -> None:
    """A decision made on a summary of a conflict is a decision about the summary."""
    the_model = _AModelThatAnswers(
        [
            {
                "the_repair": (
                    WhatToDoWhenThePullRequestWillNotMerge.LEAVE_IT_OPEN_AND_SAY_WHY.value
                ),
                "why": "somebody else has to settle this",
            }
        ]
    )

    settle_a_conflict_in_this_run(
        _the_state_a_conflict_reaches_the_run_in(),
        the_model,  # type: ignore[arg-type]
        lambda *arguments: WhatTheRebaseLanded(commit="e" * 40, what_git_said="forced update"),
        THE_CONFLICT_IN_GITHUBS_WORDS,
    )

    assert THE_CONFLICT_IN_GITHUBS_WORDS in the_model.what_it_was_asked[0], (
        f"the model was asked {the_model.what_it_was_asked[0]!r} and not the refusal GitHub's own "
        "tool produced, so the decision is made about something this run rewrote"
    )
    assert "10" in the_model.what_it_was_asked[0], (
        "the question does not say which pull request conflicts, so a model reasoning about two "
        "repositories at once has nothing to reason about"
    )


def test_a_decision_with_no_reason_behind_it_is_refused() -> None:
    """A verdict with no grounds is a coin flip written down at the worst possible place."""
    the_model = _AModelThatAnswers(
        [
            {
                "the_repair": (
                    WhatToDoWhenThePullRequestWillNotMerge.REBASE_IT_AND_TRY_AGAIN.value
                ),
                "why": "",
            }
        ]
    )

    with pytest.raises(AnAnswerThatIsNotADecisionError) as it_raised:
        settle_a_conflict_in_this_run(
            _the_state_a_conflict_reaches_the_run_in(),
            the_model,  # type: ignore[arg-type]
            lambda *arguments: WhatTheRebaseLanded(commit="e" * 40, what_git_said="forced update"),
            THE_CONFLICT_IN_GITHUBS_WORDS,
        )

    assert "why" in str(it_raised.value), (
        f"the refusal does not name the field that was empty, so a reader has to guess which of "
        f"the two rules fired: {it_raised.value}"
    )


def test_a_repair_outside_the_set_is_refused_by_name() -> None:
    """An answer that is not one of the two has said nothing, and a run may not act on nothing."""
    the_model = _AModelThatAnswers(
        [{"the_repair": "close it and open a new one", "why": "that is the third thing"}]
    )

    with pytest.raises(AnAnswerThatIsNotADecisionError) as it_raised:
        settle_a_conflict_in_this_run(
            _the_state_a_conflict_reaches_the_run_in(),
            the_model,  # type: ignore[arg-type]
            lambda *arguments: WhatTheRebaseLanded(commit="e" * 40, what_git_said="forced update"),
            THE_CONFLICT_IN_GITHUBS_WORDS,
        )

    assert "close it and open a new one" in str(it_raised.value), (
        f"the refusal does not repeat the answer it refused, so the person reading it has to go "
        f"and find what the model said: {it_raised.value}"
    )


def test_the_two_repairs_are_named_sentences_and_nothing_else() -> None:
    """Both are things a run can do, which is the whole reason this is a choice and not a coin."""
    what_there_is = [a_repair.value for a_repair in WhatToDoWhenThePullRequestWillNotMerge]

    assert set(what_there_is) == {
        "rebase it and try again",
        "leave it open and say why",
    }, (
        f"the repairs on offer are {what_there_is}, and a repair a run cannot take is a coin "
        "rather than a decision — so the set is exactly what this run can do about a conflict"
    )


def test_a_decision_keeps_the_reason_it_was_given() -> None:
    """The grounds are a field of the answer and not a message this module composed.

    **And the set is refused from being widened afterwards**, because `extra="forbid"` is what
    makes "and a reason" the only shape; a model that returned three fields would be read as an
    artifact with two, which is a fact this system did not ask for.
    """
    the_decision = WhatToDoAroundAConflict(
        the_repair=WhatToDoWhenThePullRequestWillNotMerge.LEAVE_IT_OPEN_AND_SAY_WHY,
        why="the base branch is protected on purpose",
    )

    assert the_decision.why == "the base branch is protected on purpose"
    assert the_decision.the_repair is (
        WhatToDoWhenThePullRequestWillNotMerge.LEAVE_IT_OPEN_AND_SAY_WHY
    ), "the answer kept a string where the set had a name, so nothing downstream can be exhaustive"


def test_a_merge_refused_as_a_conflict_reaches_the_node_that_can_settle_it() -> None:
    """The conflict, carrying GitHub's own words, arrives where a repair can be chosen.

    **The words travel rather than a paraphrase of them.** The one thing this repository knows
    about a conflict is what GitHub said about it, and a node handed "there was a conflict" has
    been handed a decision already made by the sentence someone else wrote.
    """
    the_refusal = ThePullRequestIsInConflictError(
        "GitHub says pull request 10 conflicts with main and cannot be merged as it stands."
    )

    def a_merge_that_is_refused_as_a_conflict(the_pull_request: APullRequestToMerge) -> Any:
        raise the_refusal

    where_it_went = merge_the_delivery_in_this_run(
        _the_state_a_conflict_reaches_the_run_in(), a_merge_that_is_refused_as_a_conflict
    )

    assert where_it_went.goto == WHERE_THE_CONFLICT_IS_SETTLED, (
        f"the merge was refused as a conflict and the run went to {where_it_went.goto!r}. The only "
        "node that can choose between the two repairs is not that one, so a conflict still ends "
        "the run with a stack trace instead of with a decision"
    )
    assert where_it_went.update, (
        "the conflict was handed on with nothing carried. The refusal's own sentence is the only "
        "evidence a model has about what to repair, and dropping it leaves the model guessing"
    )
    what_it_carries = "".join(str(each) for each in where_it_went.update.values())
    assert "conflicts with main" in what_it_carries, (
        f"the conflict reached the repair carrying {what_it_carries!r} rather than what GitHub "
        "said, so the decision is being made about a restatement"
    )


def test_a_merge_refused_for_anything_else_is_not_caught() -> None:
    """One refusal is handed on and the rest keep propagating, and a blanket `except` loses that.

    **The narrow clause is the declaration, and the type checker reads it.** A merge node that
    caught everything would turn this into the place every delivery trouble goes — a work item
    nobody commissioned, a graph wired out of order, a check that has not finished — and each of
    those would arrive here as a conflict to repair.
    """

    def a_merge_refused_because_the_checks_had_not_finished(the_pull_request: Any) -> Any:
        raise TheSuiteHasNotFinishedYetError("the_gate is still queued")

    with pytest.raises(TheSuiteHasNotFinishedYetError):
        merge_the_delivery_in_this_run(
            _the_state_a_conflict_reaches_the_run_in(),
            a_merge_refused_because_the_checks_had_not_finished,
        )


def test_a_merge_that_landed_names_where_the_run_goes_on() -> None:
    """With the edge gone the ordinary path has to name its own destination, or it has none.

    **A node that hands back nothing is a node the graph cannot leave.** Removing the edge out of
    the merge is what keeps an edge from firing alongside this `goto` and delivering a pull
    request that was never merged — and the price of removing it is that the destination has to
    be named here.
    """
    where_it_went = merge_the_delivery_in_this_run(
        _the_state_a_conflict_reaches_the_run_in(),
        lambda the_pull_request: WhatTheMergeLanded(
            commit="f" * 40, what_github_said="Pull Request successfully merged"
        ),
    )

    assert where_it_went.goto == "mark_the_work_item_delivered", (
        f"the merge landed and the run went to {where_it_went.goto!r} rather than on to mark the "
        "work item delivered"
    )
    assert where_it_went.update == {"the_commit_that_landed": "f" * 40}, (
        f"the merge landed and the state carries {where_it_went.update!r}, and the commit that "
        "landed is the one fact the record of the run is built from"
    )


def test_no_edge_leaves_the_merge_node() -> None:
    """An edge would fire alongside the `goto`, and the run would deliver a pull request.

    **That is a delivery nobody merged, marked delivered, and the record would say otherwise.**

    **Found here by reading for one shape rather than by running into it again.** The delivery
    node lost its edge for exactly this reason — `deliver_this_run` returns a `Command(goto=...)`
    when a suite went red, and an edge fired alongside it, sending the run to the supervisor and
    down the ordinary path in the same step.

    **Parsed and not imported**, because a double could answer either way: the claim is about the
    edge the production graph builds, and a test that walks a substituted graph would only prove
    the substitute was walked.
    """
    import ast

    the_lifecycle = Path(__file__).parent.parent / "src" / "aisdlc" / "graph" / "lifecycle.py"
    what_leaves_the_merge: list[str] = []

    for a_node in ast.walk(ast.parse(the_lifecycle.read_text())):
        if not isinstance(a_node, ast.Call) or getattr(a_node.func, "attr", "") != "add_edge":
            continue
        the_arguments = [ast.unparse(one) for one in a_node.args]
        if the_arguments and the_arguments[0] in (
            "WHERE_THE_DELIVERY_IS_MERGED",
            '"merge_the_delivery_in_this_run"',
        ):
            what_leaves_the_merge.append(" -> ".join(the_arguments))

    assert not what_leaves_the_merge, (
        f"{what_leaves_the_merge} leaves the merge node. That node now names its own destination, "
        "so an edge fires alongside the goto and the run marks a pull request delivered that was "
        "never merged. This is the defect the delivery node's own edge was removed for"
    )


def test_the_node_asks_a_question_it_did_not_write() -> None:
    """A sentence written inside a node is a sentence no agent owns and `evals/` cannot grade.

    **Parsed and not imported, because a double could answer either way.** The claim is about the
    text the production code hands the model, and substituting the question would only prove the
    substitute was used — which is the same mistake `test_every_stage_reasoning_about_a_file_is_
    shown_it.py` already records about an inspection.

    **The argument to `invoke` has to be a name**, so the node reaches a question somebody else
    wrote. A literal there would be a prompt living in `graph/`, and the question builder sits
    beside the answer it produces for exactly that reason.
    """
    import ast

    the_node = (
        Path(__file__).parent.parent / "src" / "aisdlc" / "graph" / "settle_a_conflict_node.py"
    )
    what_was_handed_to_the_model: list[str] = []

    for a_node in ast.walk(ast.parse(the_node.read_text())):
        if not isinstance(a_node, ast.Call) or getattr(a_node.func, "attr", "") != "invoke":
            continue
        for an_argument in a_node.args:
            if isinstance(an_argument, ast.Constant) and isinstance(an_argument.value, str):
                what_was_handed_to_the_model.append(an_argument.value)

    assert not what_was_handed_to_the_model, (
        f"the node hands the model {what_was_handed_to_the_model!r} written where it stands. A "
        "prompt in graph/ belongs to no agent, so nothing in evals/ can grade it and no glossary "
        "entry can name it"
    )


def test_a_command_is_what_comes_back_and_a_destination_is_not_optional() -> None:
    """A node that handed back nothing would leave the graph with no edge to take.

    **Asserted through the node rather than by reading it**, because `Command` with no `goto` is a
    legal object and the graph only complains at run time — which is where this repository found
    out that a run could walk to the recursion limit instead of stopping.
    """
    the_model = _AModelThatAnswers(
        [
            {
                "the_repair": (
                    WhatToDoWhenThePullRequestWillNotMerge.LEAVE_IT_OPEN_AND_SAY_WHY.value
                ),
                "why": "the base branch is protected on purpose",
            }
        ]
    )

    where_it_went = settle_a_conflict_in_this_run(
        _the_state_a_conflict_reaches_the_run_in(),
        the_model,  # type: ignore[arg-type]
        lambda *arguments: WhatTheRebaseLanded(commit="e" * 40, what_git_said="forced update"),
        THE_CONFLICT_IN_GITHUBS_WORDS,
    )

    assert isinstance(where_it_went, Command)
    assert where_it_went.goto, "the node returned a Command with no destination and no state change"
