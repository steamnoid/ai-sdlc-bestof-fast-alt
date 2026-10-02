"""The conflict repair, against a real model and a real refusal.

**This is the second agent in this repository whose answer is a destination rather than a
document, and it is the first one whose two answers are operations rather than stages.** The
supervisor sends a run back to an agent; this one sends a run back to the question about its own
suite, or stops it with a reason. **A `Command` naming a node the graph does not contain stops a
run at the last step of a delivery**, which is the worst place a graph fault can surface — a
delivery that verified green, opened a pull request and then died on a node name.

**The assertion is about the outcome and not the verdict.** A real model is free to rebase or to
leave the pull request open, and both are answers this system has somewhere to put — which is the
whole claim this file exists to make. **A test that wanted one of them would be testing the model
rather than the system, and would fail on a good answer.** What is refused is everything else: a
repair that is not one of the two, grounds that are blank or a placeholder, and a destination the
graph does not hold.

**Which of the two it chose is printed**, for the reason the supervisor's file prints its verdict:
the assertions accept either, so a reader of a passing run would otherwise be left not knowing
which happened — and that is the fact worth having when somebody asks whether this repair is doing
anything at all. Pytest captures this and shows it only on failure, so `-s` is how a run says it.

**The conflict is GitHub's own wording, taken from what this system's tool produces.** The refusal
is not invented here because a model asked about a paraphrase is being asked about the paraphrase,
and the whole claim in the unit tier is that the refusal travels whole. A conflict a real run hit
is rare, so the words are the ones the tool would have written rather than words assembled to look
realistic — and that is stated here rather than left for a reader to assume otherwise.

**A real repository, because the pull request and the base branch in the question are real
addresses.** A model can name a repair without a repository, so what this file cannot prove is the
groundedness of its grounds — that they are about *this* pull request and not a sentence about
conflicts in general. The assertion on that is the narrowest thing here and the one worth having.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import pytest

from aisdlc.agents.what_to_do_when_a_pull_request_will_not_merge import (
    AnAnswerThatIsNotADecisionError,
    WhatToDoWhenThePullRequestWillNotMerge,
    the_question_about_a_conflict_in_these_words,
)
from aisdlc.domain.repository import Repository
from aisdlc.graph.settle_a_conflict_node import settle_a_conflict_in_this_run
from aisdlc.llm.model_provider import LlmProvider

pytestmark = pytest.mark.e2e

WHERE_A_REBASED_RUN_GOES = "ask_github_whether_the_suite_went_green"
WHERE_A_RUN_THAT_STOPS_IS_OVER = "write_how_this_run_ended"


class WhatTheRepairChose(NamedTuple):
    """Where the repair sent the run, and the grounds it gave for having chosen it."""

    where_it_sent_the_run: str
    why: str
    the_refusal_it_raised: str | None


def the_conflict_github_would_have_refused_with(repository: Repository) -> str:
    """The sentence this system's own tool writes when GitHub answers `mergeable: false`.

    **Written from the tool's rule rather than copied from a log**, because a log would be a
    conflict one particular run happened to hit and this file needs a conflict to ask about on
    every run. What it has to carry is the three things the question asks: which pull request,
    which repository, and that GitHub will not merge it as it stands.
    """
    return (
        f"GitHub answered mergeable: false for pull request {A_REAL_PULL_REQUEST_NUMBER} of "
        f"{repository.owner}/{repository.name}, and a pull request that conflicts with the branch "
        f"it would join cannot be merged as it stands."
    )


A_REAL_PULL_REQUEST_NUMBER = 1


@pytest.fixture(scope="module")
def a_real_repair(
    the_repository: Repository,
    the_placeholders: frozenset[str],
    the_model_for: Callable[[LlmProvider], object],
    request,
) -> WhatTheRepairChose:
    """One real decision about one real conflict, shared by every assertion about it.

    **One call for the whole module, because a second one would be a different run.** A model
    asked the same question twice can answer two different ways, so asserting the grounds against
    two sets of grounds would be asserting that the model varies — which is true and is not what
    this file is for.

    **The state is one the repair has already been proved to read**, so this file does not
    re-test the reading: a clone on `main`, a delivery whose request named both branches, and the
    commit the checks were read about. What is under test is the model, and a fault in the reading
    would raise before a word was ever asked.
    """
    from aisdlc.agents.pull_request_request import PullRequestRequest
    from aisdlc.domain.commissioned_request import a_request_about
    from aisdlc.domain.role import Role
    from aisdlc.domain.work_item import a_work_item_commissioned_for_an_agent
    from aisdlc.graph.agent_state import AgentState
    from aisdlc.tools.github_clone_repository import ClonedRepository
    from aisdlc.tools.rebase_the_branch_a_run_pushed import WhatTheRebaseLanded

    the_work_item = a_work_item_commissioned_for_an_agent(
        work_item_id="a-delivery-github-would-not-merge",
        repository=the_repository,
        accountable_role=Role.DEV,
        commissioned_by="a person running the real tier",
        requested=a_request_about("add a health endpoint", ""),
    )
    the_pull_request_number = A_REAL_PULL_REQUEST_NUMBER
    the_run = AgentState(
        work_item=the_work_item,
        projects_root=Path("a-projects-root-the-repair-never-writes-to"),
        clone=ClonedRepository(path=Path("the-clone"), ref="main", commit="a" * 40),
        requested_stage=None,
        requested_agent=None,
        requested_role=None,
        the_commit_anything_proved="b" * 40,
        opened_pull_request=None,
        pull_request_request=PullRequestRequest(
            repository=the_repository,
            work_item_id=the_work_item.work_item_id,
            branch=f"aisdlc/issue-{the_pull_request_number}-{the_work_item.work_item_id}",
            base="main",
            title="add a health endpoint",
            body="what changed and what was verified",
        ),
        the_conflict_that_stopped_this_merge=None,
    )

    def a_rebase_that_was_asked_for(
        *arguments: object,
    ) -> WhatTheRebaseLanded:
        """A rebase that reports a landed commit, because the branch under test is never real."""

        return WhatTheRebaseLanded(
            commit="c" * 40, what_git_said="this real tier does not push anywhere"
        )

    try:
        where_it_went = settle_a_conflict_in_this_run(
            the_run,
            the_model_for(request.param),
            a_rebase_that_was_asked_for,
            the_conflict_github_would_have_refused_with(the_repository),
        )
    except AnAnswerThatIsNotADecisionError as no_repair_was_named:
        return WhatTheRepairChose(
            where_it_sent_the_run="", why="", the_refusal_it_raised=str(no_repair_was_named)
        )

    the_grounds = ""
    for what_it_wrote in (where_it_went.update or {}).values():
        the_grounds += f" {what_it_wrote}"

    print(
        f"\nthe real model chose {where_it_went.goto!r} and said: {the_grounds.strip()}\n",
        flush=True,
    )

    return WhatTheRepairChose(
        where_it_sent_the_run=str(where_it_went.goto),
        why=the_grounds.strip(),
        the_refusal_it_raised=None,
    )


def the_nodes_this_graph_registers() -> frozenset[str]:
    """Every node name the built lifecycle holds, asked of the graph rather than of the source.

    **The graph is compiled here and its node list read, because a list of literals typed into
    this file is a second copy of the graph.** A `goto` is a node name, and the only thing that
    settles whether one exists is the graph itself — which is the lesson from every repair that
    broke here while each routing test passed, because a routing test calls a function and reads
    what it returns rather than building the thing.

    **Every collaborator raises**, because nothing here runs a run: the cast is only what the
    compiler needs to have a name to attach.
    """

    def a_collaborator_nobody_asked_for(*_arguments: object, **_keywords: object) -> object:
        """A collaborator that refuses, so this file cannot reach one by accident."""
        raise AssertionError("this file builds the graph and runs nothing in it")

    from aisdlc.domain.repository import Repository
    from aisdlc.graph.lifecycle import the_lifecycle
    from aisdlc.graph.the_agents_this_run import TheAgentsThisRun
    from aisdlc.graph.the_delivery_of_this_run import TheDeliveryOfThisRun

    the_refusing = a_collaborator_nobody_asked_for
    return frozenset(
        the_lifecycle(
            checkpoint_directory=Path("a-directory-nothing-is-written-to"),
            agents=TheAgentsThisRun(
                discover=the_refusing,
                propose_requirements=the_refusing,
                plan_the_tests=the_refusing,
                describe_the_architecture=the_refusing,
                inspect_for_security=the_refusing,
                plan=the_refusing,
                apply_and_verify=the_refusing,
                supervise=the_refusing,
                brief=the_refusing,
                review=the_refusing,
            ),
            delivery=TheDeliveryOfThisRun(
                our_copy=Repository(owner="nobody", name="asked-for-nothing"),
                push_the_branch=the_refusing,
                open_the_pull_request=the_refusing,
                ask_whether_the_suite_went_green=the_refusing,
                merge_the_pull_request=the_refusing,
                rebase_the_branch_a_run_pushed=the_refusing,
            ),
            policy=None,
            plan_the_clone=the_refusing,
        )
        .get_graph()
        .nodes
    )


@pytest.mark.parametrize("a_real_repair", list(LlmProvider), indirect=True)
def test_a_real_model_names_one_of_the_two_repairs_and_says_why(
    a_real_repair: WhatTheRepairChose,
    the_placeholders: frozenset[str],
) -> None:
    """A name from the closed set, and grounds that are not a shape rather than a finding.

    **Neither half is asserted as a verdict.** Both repairs are something a run can do, so which
    one came back is the model's judgement and not this system's claim. What is refused is an
    answer that names neither, grounds that are blank, and grounds that are one of the words this
    tier treats as a placeholder in every other file.

    **A refusal is carried rather than raised**, so that a model which cannot express a decision
    fails the assertion below with a sentence a reader can act on instead of an error in a
    fixture.
    """
    if a_real_repair.the_refusal_it_raised is not None:
        pytest.fail(
            f"the model answered in a way this run cannot act on, and said so itself:\n\n"
            f"{a_real_repair.the_refusal_it_raised}"
        )

    assert a_real_repair.where_it_sent_the_run in {
        WHERE_A_REBASED_RUN_GOES,
        WHERE_A_RUN_THAT_STOPS_IS_OVER,
    }, (
        f"the repair sent the run to {a_real_repair.where_it_sent_the_run!r}, which is neither of "
        f"the two things naming a repair can lead to ({WHERE_A_REBASED_RUN_GOES!r} and "
        f"{WHERE_A_RUN_THAT_STOPS_IS_OVER!r}). Both are nodes the graph holds, so a destination "
        "outside both is a name the graph does not contain"
    )

    assert a_real_repair.why.strip(), (
        "the model named a repair and said nothing for it. A verdict with no grounds is a coin "
        "flip written down at the one place a coin flip is worst"
    )

    said_anything_at_all = a_real_repair.why.strip().lower() not in the_placeholders
    assert said_anything_at_all, (
        f"the grounds are {a_real_repair.why!r}, which is one of the words this tier treats as a "
        f"placeholder in every other file: {sorted(the_placeholders)}"
    )


@pytest.mark.parametrize("a_real_repair", list(LlmProvider), indirect=True)
def test_the_repair_sent_the_run_to_a_node_this_graph_holds(
    a_real_repair: WhatTheRepairChose,
) -> None:
    """A `Command` naming a node the graph does not contain ends a delivery with a graph fault.

    **Read off the compiled graph, so this cannot pass by agreeing with itself.** A list of
    literals typed into this file is a second copy of the graph, and a destination compared
    against it would pass for ever if either side were renamed alone. Every repair that broke in
    this repository broke between two stages that each looked right, and the only thing that
    catches that shape is building the thing and asking what it holds.
    """
    the_nodes = the_nodes_this_graph_registers()

    assert the_nodes, (
        "the graph this file asked for its node names holds none, so every destination would be "
        "contained in it and this assertion could not fail"
    )

    assert a_real_repair.where_it_sent_the_run in the_nodes, (
        f"the repair sent the run to {a_real_repair.where_it_sent_the_run!r} and the graph this "
        f"file compiled holds {sorted(the_nodes)}. A repair that names a node nobody registered "
        "stops a run at the last step of a delivery, which is the worst place a graph fault can "
        "surface: the change verified green and the pull request is open"
    )


@pytest.mark.parametrize("a_real_repair", list(LlmProvider), indirect=True)
def test_the_grounds_are_about_this_pull_request_and_not_about_conflicts(
    a_real_repair: WhatTheRepairChose, the_repository: Repository
) -> None:
    """A sentence about conflicts in general is the answer a model gives when it was not looking.

    **The narrowest assertion here and the one worth having.** Both repairs can be named from
    the set alone, so the only way to know the model read the refusal rather than the shape of
    the question is to look for this pull request, this repository, or the branch it would join.
    **One of the three is enough**, because a model may name any of them and requiring all three
    would be asserting a style rather than a reading.
    """
    if a_real_repair.the_refusal_it_raised is not None:
        pytest.skip(
            "the model answered unusably, so it said nothing about anything: "
            f"{a_real_repair.the_refusal_it_raised}"
        )

    the_grounds = a_real_repair.why.lower()
    something_specific_to_this_conflict = any(
        what_it_named in the_grounds
        for what_it_named in (
            str(A_REAL_PULL_REQUEST_NUMBER),
            the_repository.name.lower(),
            the_repository.owner.lower(),
            "main",
            "protected",
            "behind",
        )
    )

    assert something_specific_to_this_conflict, (
        f"the grounds are {a_real_repair.why!r} and name nothing about pull request "
        f"{A_REAL_PULL_REQUEST_NUMBER} of {the_repository.owner}/{the_repository.name}, nothing "
        "about the branch it would join, and nothing about why GitHub would not merge it. That is "
        "an answer a model produces from the shape of the question alone, which is the one thing "
        "a closed set cannot catch"
    )


def test_both_repairs_lead_somewhere_this_graph_has_a_node_for() -> None:
    """Both names, both destinations, and the destinations read off the graph rather than assumed.

    **This asks nothing of a model and everything of the wiring**, which is why it is here and not
    in the real tier's assertions. The set has two members and each leads to one place; a repair
    added to the set later without a destination is the failure this catches, and it is caught
    without a credential.
    """
    the_nodes = the_nodes_this_graph_registers()

    for a_repair in WhatToDoWhenThePullRequestWillNotMerge:
        where_that_repair_goes = {
            WhatToDoWhenThePullRequestWillNotMerge.REBASE_IT_AND_TRY_AGAIN: (
                WHERE_A_REBASED_RUN_GOES
            ),
            WhatToDoWhenThePullRequestWillNotMerge.LEAVE_IT_OPEN_AND_SAY_WHY: (
                WHERE_A_RUN_THAT_STOPS_IS_OVER
            ),
        }[a_repair]

        assert where_that_repair_goes in the_nodes, (
            f"naming {a_repair.value!r} sends the run to {where_that_repair_goes!r}, which the "
            f"graph does not hold. A repair on offer that leads nowhere is not a choice"
        )


def test_the_question_prints_the_same_two_sentences_the_set_accepts() -> None:
    """What the model is shown and what it may answer are the same list by construction.

    **And that is asserted rather than trusted, because the two were written in one place today
    and nothing would have said so if they drifted.** The set and the printed list are both built
    from the enumeration, so this fails the moment one of them stops being built from it — which
    is a refactor that would look harmless and would quietly make the question unusable.
    """
    the_question = the_question_about_a_conflict_in_these_words("a conflict GitHub described")

    for a_repair in WhatToDoWhenThePullRequestWillNotMerge:
        assert a_repair.value in the_question, (
            f"the question does not print {a_repair.value!r}, so the model is asked to choose "
            "between repairs it cannot read. An answer from outside the set is then a refusal "
            "rather than a mistake, and this repository has already paid for prompts that "
            "described the options instead of printing them"
        )
