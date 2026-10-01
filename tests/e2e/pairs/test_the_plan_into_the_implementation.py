"""A real plan, from real requirements, applied to a real checkout — the one pair that writes.

**This is a true seam, and the sibling file's finding is what makes it worth a file of its own.**
`plan_the_change` is handed `Requirements` and `implement_the_plan` is handed the
`ImplementationPlan` that came out of it, so the upstream stage's conclusion *is* the next stage's
input. **A plan the implementer cannot apply is a run that stops at a gate with every record
upstream of it still reading as complete**, and neither isolation file beside this one could have
seen it: the planner there is handed a requirements set written out in the test, and the
implementer there is handed a plan assembled by hand from the checkout. **Each proves one agent,
and the handover between them is what neither measures.**

**The product analyst runs first, and that is scaffolding rather than a third stage under test.**
The planner's input is approved `Requirements`, so a file measuring plan→implement needs them, and
`test_plan_the_change.py` states the case against chaining a real agent into a file whose job is
to isolate one. The answer is what that file is not: this file's job is the handover, and a
stand-in requirements set would leave the planner planning against a document no gate ever
presented — so three real calls happen, in order, and the pair under test is the last two of them.

**Two clones, and that is the whole cost of the first pair's counterpart.** The planner only reads,
so it is given the read-only clone every other stage in this tier reads. **The implementer writes,
so it is given `a_clone_this_run_may_write` and never the shared one** — a change left in the
shared clone would be there for the next module to find, and a test asserting a checkout was left
alone would then pass for the wrong reason. The second copy is also what makes the central
assertion possible at all: *what this run changed* is knowable only as a difference between two
directories, one of which nothing wrote to.

**`what_the_suite_announced` is the production constant, and a refusal is skipped out loud.**
`plan_node` hands the planner `THE_RUNNER_ANNOUNCED_NOTHING_YET`, so that constant is imported
rather than `""` written here, and the test is the production value by construction instead of by
agreement. A plan naming a test in a directory this repository does not collect is refused by
`PlannedTestDirectoryNotCollectedError`, and this file skips with the refusal printed rather than
letting a refusal it did not cause end the module as an error. **A plan that names a test the
suite will not run is a fact about this repository and this deployment's model**, and it is
decided before the handover this file measures even begins — so the honest thing to do about it is
to say it out loud, not to report it as a defect in the thing being measured.

Nothing here runs the suite and nothing here commits: a repository's own code is run in a
container and a change is recorded by a later node, and asserting either from this file would be
asserting that a function does what a different function does.

The provider is a parameter rather than a constant, so proving a second one is a different run and
not a rewritten test. A provider the deployment is not configured for says so out loud.
"""

from __future__ import annotations

from typing import NamedTuple

import pytest

from aisdlc.agents.analyze_the_repository import analyze_the_repository
from aisdlc.agents.implement_the_plan import (
    FileToWrite,
    WhatTheImplementerConcluded,
    implement_the_plan,
    the_paths_the_plan_names,
    the_prompt_to_implement,
)
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.plan_the_change import (
    PlannedTestDirectoryNotCollectedError,
    plan_the_change,
)
from aisdlc.agents.requirements import Requirements
from aisdlc.agents.what_the_planner_concluded import ImplementationPlanAnswer
from aisdlc.domain.commissioned_request import CommissionedRequest
from aisdlc.domain.repository import Repository
from aisdlc.graph.plan_node import THE_RUNNER_ANNOUNCED_NOTHING_YET
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE

pytestmark = pytest.mark.e2e

JUDGEMENTS_EVERY_AGENT_MAKES = (
    "what_it_found",
    "what_it_could_not_settle",
    "what_it_expects_next",
)


def _every_working_tree_file_a_clone_holds(clone: ClonedRepository) -> dict[str, str]:
    """Every file of a clone that belongs to the checkout rather than to a dependency.

    **Spelled out here rather than imported from the tier that compares two clones the same way.**
    That file argues for doing so — a helper that lost a piece would take the assertion meant to
    notice it along — and this is that argument applied twice, because a check on a check is the
    only kind that survives the check being wrong. Somebody else's code and the history are
    skipped by name, read from the module that decides what a model is shown, and a diff
    containing `.git` would be a claim about the repository rather than about this change.
    """
    held: dict[str, str] = {}

    for a_path in clone.path.rglob("*"):
        if not a_path.is_file():
            continue
        its_parts = a_path.relative_to(clone.path).parts
        if any(a_part in DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE for a_part in its_parts):
            continue
        held[str(a_path.relative_to(clone.path))] = a_path.read_text(
            encoding="utf-8", errors="replace"
        )

    return held


def _the_text_a_clone_holds_of(clone: ClonedRepository, a_path: str) -> str | None:
    """What one file of a clone held, or `None` because the clone does not hold it at all."""
    where = clone.path / a_path
    if not where.is_file():
        return None
    return where.read_text(encoding="utf-8", errors="replace")


def _paths_where_the_two_clones_disagree(
    what_was_cloned: dict[str, str], what_this_run_left: dict[str, str]
) -> set[str]:
    """The paths a run changed, measured as a difference between two directories.

    **A file that is new counts as changed, and that falls out of the comparison rather than being
    written down.** `tests_to_add` names a test that does not exist yet, so the before has no entry
    for it and the after does — which is a change by definition.
    """
    return {
        a_path
        for a_path, its_text in what_this_run_left.items()
        if what_was_cloned.get(a_path) != its_text
    }


class WhatTheChangeWasBuiltFrom(NamedTuple):
    """The three real answers in the order they were produced, and the checkout that received them.

    **Kept in the order of the run rather than named after the assertion that wants them.** The
    requirements came first and the change came last, and a reader who reads this top to bottom
    learns the order a run is in rather than the order a test file happens to check things in.
    """

    the_requirements: Requirements
    what_the_planning_agent_concluded: ImplementationPlanAnswer
    what_the_implementer_concluded: WhatTheImplementerConcluded
    what_was_cloned: dict[str, str]
    what_this_run_left: dict[str, str]

    @property
    def the_plan(self) -> ImplementationPlan:
        """The plan itself, which is the one thing downstream of here is handed."""
        return self.what_the_planning_agent_concluded.plan


@pytest.fixture(scope="module")
def the_handover(
    the_repository: Repository,
    the_cloned_repository: ClonedRepository,
    a_clone_this_run_may_write: ClonedRepository,
    a_request: CommissionedRequest,
    the_model_for,
    request,
) -> WhatTheChangeWasBuiltFrom:
    """Three real calls in a run's order, and the two clones the change is measured between.

    **The analyst, then the planner, then the implementer, and the plan is what the planner said.**
    `implement_the_plan` takes an `ImplementationPlan` and not the `ImplementationPlanAnswer` the
    planner returned, so passing the whole answer through would measure a handover production does
    not make; the artifact is unwrapped here exactly where the node unwraps it.

    **The planner reads the read-only clone and the implementer writes the writable one**, and both
    directories are read off disk before the write happens — so what the change is compared against
    is the repository as it was cloned, captured by this fixture rather than by a test that runs
    afterwards and might be looking at a tree this run had already touched.

    **A plan the repository cannot run a test from is skipped with the refusal printed.** The
    refusal is raised only after this deployment's correction budget is spent, so it is both slow
    and about something upstream of the handover; reporting it as a failure of the pair would be a
    claim about the wrong thing, and swallowing it would be worse.

    **The provider is `request.param` and the tests parametrise it indirectly**, so a run
    configured for one provider *skips* the others with the reason printed.
    """
    the_model = the_model_for(request.param)

    the_requirements, _ = analyze_the_repository(
        the_cloned_repository, the_repository, a_request, the_model
    )

    try:
        what_the_planning_agent_concluded = plan_the_change(
            the_requirements,
            the_cloned_repository,
            the_repository,
            the_model,
            THE_RUNNER_ANNOUNCED_NOTHING_YET,
        )
    except PlannedTestDirectoryNotCollectedError as refused:
        pytest.skip(
            f"a real planning agent, given real requirements and this repository, would not name a "
            f"test in a directory the suite collects, and this run's correction budget was spent "
            f"before it answered. {str(refused).strip()}\n\nThat is a fact about this repository "
            f"and this deployment's model, and it is decided before the handover this file "
            f"measures begins. Point the tier at a repository whose tests live where a planner "
            f"puts them, and run again."
        )

    what_was_cloned = _every_working_tree_file_a_clone_holds(the_cloned_repository)

    what_the_implementer_concluded = implement_the_plan(
        a_clone_this_run_may_write, what_the_planning_agent_concluded.plan, the_model
    )

    return WhatTheChangeWasBuiltFrom(
        the_requirements=the_requirements,
        what_the_planning_agent_concluded=what_the_planning_agent_concluded,
        what_the_implementer_concluded=what_the_implementer_concluded,
        what_was_cloned=what_was_cloned,
        what_this_run_left=_every_working_tree_file_a_clone_holds(a_clone_this_run_may_write),
    )


@pytest.mark.parametrize("the_handover", list(LlmProvider), indirect=True)
def test_every_path_the_implementer_wrote_was_named_by_the_plan(
    the_handover: WhatTheChangeWasBuiltFrom, the_cloned_repository: ClonedRepository
) -> None:
    """Nothing outside the approved plan was written, and every file to change was a file before.

    **Both edges of the boundary, and they are different faults.** `files_to_change` naming a path
    the repository does not have means the plan is against nothing, and the implementer would
    either invent the file or fail a long way from the mistake. A path the plan did not name being
    written means a person approved one file and something else changed — §36 says an approval
    names an exact artifact, and an approval of a plan naming one file is not an approval of a
    second.

    **Checked on both the answer and the clone, and they are not the same check.** The answer is
    what the agent said it wrote, and a list of paths is a claim; the read-only clone is a
    directory nothing wrote to, and each of the plan's `files_to_change` really being there before
    the run is a fact about a disk. The first assertion is guarded on the second being non-empty —
    every path of an empty answer is a path the plan named, and a check that could not hear about
    an empty answer would pass exactly the case it is here for.
    """
    the_plan = the_handover.the_plan
    the_named_paths = the_paths_the_plan_names(the_plan)
    what_the_implementer_concluded = the_handover.what_the_implementer_concluded

    assert the_named_paths, (
        f"the plan this run applied names no path at all across "
        f"{', '.join(ImplementationPlan.model_fields)}, so there is no boundary for a write to "
        f"cross and every assertion below would be true of an empty pair. `EmptyPlanError` exists "
        f"for a plan that says nothing in any of the five lists, and the node refuses it, so a "
        f"plan reaching here means the refusal is not armed"
    )

    every_write: list[FileToWrite] = what_the_implementer_concluded.files
    assert every_write, (
        f"the implementation agent answered with no file, against a plan naming {the_named_paths}. "
        f"Every assertion about what was written would then hold of nothing having been done, and "
        f"a node that accepted an empty answer would leave the checkout exactly as it was found "
        f"while reporting a change"
    )

    written_outside_the_plan = [
        one_write.path for one_write in every_write if one_write.path not in the_named_paths
    ]
    assert not written_outside_the_plan, (
        f"{written_outside_the_plan} were written and the approved plan names {the_named_paths}. A "
        f"path outside the plan is a change no person approved, and the plan is the artifact the "
        f"gate presented and the `Approval` names with a version"
    )

    not_there_before = [
        a_path
        for a_path in the_plan.files_to_change
        if _the_text_a_clone_holds_of(the_cloned_repository, a_path) is None
    ]
    assert not not_there_before, (
        f"{not_there_before} are named as files to change, and the clone this plan was made from "
        f"does not hold them. `files_to_change` is a promise about files that are there and are "
        f"rewritten in place, so a path that is not there is a plan against nothing — and the "
        f"implementer was handed it as though it were a file to edit"
    )


@pytest.mark.parametrize("the_handover", list(LlmProvider), indirect=True)
def test_the_writable_clone_holds_exactly_what_the_implementer_proposed(
    the_handover: WhatTheChangeWasBuiltFrom, a_clone_this_run_may_write: ClonedRepository
) -> None:
    """Every file is on disk, holding the complete text the answer proposed for it.

    **The disk and not the answer, because a list of files is a claim and a file is a fact.** The
    implementer is asked for the whole text each file should end up holding rather than a diff, so
    "the file now holds what was proposed" is the whole contract of this stage in one comparison —
    and it is the one comparison an answer that was well formed and never applied cannot pass.

    **Every path the plan named, and not the ones the answer listed.** A plan naming three files
    with two of them written is a repository that is not the one the plan describes, and every
    record between the approved plan and the pull request still reads as complete.

    **The writable clone, because that is the only directory anything wrote to.** The read-only
    one is a record of the repository before, and reading the after out of it would find a tree
    this run never touched.
    """
    the_plan = the_handover.the_plan
    every_write: list[FileToWrite] = the_handover.what_the_implementer_concluded.files

    assert every_write, (
        "the implementation agent answered with no file, so there is nothing to compare and this "
        "assertion would be about an empty answer rather than about a change on a disk"
    )

    for one_write in every_write:
        where = a_clone_this_run_may_write.path / one_write.path
        assert where.is_file(), (
            f"{one_write.path!r} is in the answer and is not a file of the clone afterwards, so "
            f"the change was reported and never written. The plan is {the_handover.the_plan!r}"
        )
        assert where.read_text(encoding="utf-8") == one_write.content, (
            f"{one_write.path!r} does not hold the text that was proposed for it. The stage is "
            f"asked for the whole text of a file rather than a diff, so a file differing from the "
            f"answer is one written from something else — and the delivery would carry a diff "
            f"nobody read"
        )
        assert one_write.content.strip(), (
            f"{one_write.path!r} was written empty. A file holding nothing is not a change to it, "
            f"and a repository where a file has been emptied is a regression nobody asked for"
        )

    for a_path in the_paths_the_plan_names(the_plan):
        assert (a_clone_this_run_may_write.path / a_path).is_file(), (
            f"{a_path!r} is named by the approved plan and is not a file of the clone afterwards. "
            f"A plan that is not fully applied is not a plan that was applied, and reporting it as "
            f"applied is the one thing a traceability chain must never do"
        )


@pytest.mark.parametrize("the_handover", list(LlmProvider), indirect=True)
def test_nothing_outside_the_plan_reached_the_disk_and_something_reached_it(
    the_handover: WhatTheChangeWasBuiltFrom,
) -> None:
    """The two clones differ in exactly paths the plan accounts for, and they differ at all.

    **Measured as a difference between two directories rather than read out of the answer, and
    that is what makes it a check rather than a restatement.** The before is read off the read-only
    clone, which nothing wrote to, and the after off the writable one, which the implementer did;
    so a write somewhere and silence about it in the answer is a difference this way of asking
    hears, and it is the one failure a list of paths cannot report.

    **Two assertions and not one equality, and the reason is what production guarantees.** The
    refusal for a change that changes nothing fires when *every* file the plan named already held
    the text proposed for it, so one file echoed exactly is not a fault and not refused. Asserting
    set equality would therefore fail on an implementer who was thorough and reproduced a file
    correctly — punishing the model for being right. What is guaranteed, and what is asserted, is
    that nothing outside the plan moved and that something did.
    """
    the_named_paths = set(the_paths_the_plan_names(the_handover.the_plan))
    assert the_named_paths, (
        f"the plan names no path across "
        f"{', '.join(ImplementationPlan.model_fields)}, so 'nothing outside the plan' would be "
        f"true of every path this run could have written. `EmptyPlanError` exists and the node "
        f"raises it, so a plan reaching here means the refusal is not armed"
    )

    what_changed = _paths_where_the_two_clones_disagree(
        the_handover.what_was_cloned, the_handover.what_this_run_left
    )

    assert what_changed, (
        "the two clones are byte for byte the same after a run that planned a change and had an "
        "agent apply it, so this run is indistinguishable from one that did nothing — and a pull "
        "request whose diff is empty is the one thing this pipeline must never produce. "
        "`AWriteThatChangesNothingError` is refused at the writing, where the fact is still "
        "knowable, and a change reaching this assertion means that refusal is not armed"
    )

    outside_the_plan = sorted(what_changed - the_named_paths)
    assert not outside_the_plan, (
        f"{outside_the_plan} differ between the two clones and the approved plan accounts for "
        f"{sorted(the_named_paths)}. A path outside the plan is a change no person approved — the "
        f"plan names one set of paths and an approval of it is not an approval of a second — and a "
        f"gate that read only the plan's diff would not see this one at all"
    )


@pytest.mark.parametrize("the_handover", list(LlmProvider), indirect=True)
def test_the_implementer_says_what_it_found_and_what_it_could_not_settle(
    the_handover: WhatTheChangeWasBuiltFrom, the_placeholders: frozenset[str]
) -> None:
    """The three sentences of judgement are filled, and none of them is a shape rather than one.

    **The middle one is the reason this stage is asked for them in the same call as the files.** A
    plan is a list of paths with no intent, so the sentence that catches an implementer inventing a
    mechanism nobody specified is the implementer's to write — and it is asked in one call with the
    files so there is no second call to pay for and no way to judge a change that is not the one
    beside the judgement. A model with nothing to report has words to reach for rather than a
    blank, because a blank field reads as *the implementer had nothing to say*, which is
    indistinguishable from nobody having asked.

    **Placeholders are refused and silence is not.** The system offers an agent with nothing to
    report two whole sentences to say so, and those are honest answers; what is refused is a field
    carrying the *shape* of an answer.
    """
    what_the_implementer_concluded = the_handover.what_the_implementer_concluded

    assert what_the_implementer_concluded.files, (
        "the implementation agent answered with no file, so the three sentences beside it were "
        "written about no change at all — and a note about nothing is a note that reads as though "
        "there had been a change to have an opinion about"
    )

    for a_judgement in JUDGEMENTS_EVERY_AGENT_MAKES:
        said = getattr(what_the_implementer_concluded.judged, a_judgement)
        assert said.strip(), (
            f"the implementation agent left {a_judgement} empty. It is the only agent that sees "
            f"the whole text of every file it is changing, so its doubt is the last place a "
            f"mechanism nobody specified can still be named — and an empty field reads as a doubt "
            f"nobody had"
        )
        assert said.strip().lower() not in the_placeholders, (
            f"{said!r} is placeholder text in {a_judgement}, which means the model returned a "
            f"shape rather than a judgement"
        )


@pytest.mark.parametrize("the_handover", list(LlmProvider), indirect=True)
def test_the_implementer_was_shown_the_plan_and_not_the_planners_opinion(
    the_handover: WhatTheChangeWasBuiltFrom, the_cloned_repository: ClonedRepository
) -> None:
    """The implementer's question carries the plan, and none of the planner's opinion about it.

    **Asked of the prompt, because the prompt is the whole of what this stage was given.** The
    signature takes a plan, and the caller in production passes exactly that; a change that also
    passed the `ImplementationPlanAnswer` would still typecheck, and a change written in reaction
    to another model's account of the plan is a change nobody approved.

    **Built from the read-only clone, and that is not a second prompt.** `the_prompt_to_implement`
    inlines the current text of every file in `files_to_change`, so the directory it is asked about
    decides what the model saw. The writable clone now holds the change this run made, and reading
    the before out of the directory nothing wrote to is the only way to reconstruct the question
    as it was actually put.

    **Asserted on both halves, for the reason the sibling pair does.** A check that the paths are
    in the prompt is satisfied by a prompt that carries the paths *and* the planner's three
    sentences, which is exactly the case this excludes.
    """
    the_plan = the_handover.the_plan
    what_the_planning_agent_concluded = the_handover.what_the_planning_agent_concluded
    the_named_paths = the_paths_the_plan_names(the_plan)

    assert the_named_paths, (
        "the plan names no path, so there is nothing for the implementer's question to carry and "
        "the positive half of this assertion would be about an empty list"
    )

    what_the_second_stage_was_asked = the_prompt_to_implement(the_plan, the_cloned_repository)

    for a_path in the_named_paths:
        assert a_path in what_the_second_stage_was_asked, (
            f"{a_path!r} is named by the approved plan and is not in the implementer's question, "
            f"so the plan's boundary was never shown to the stage it bounds. A model asked to "
            f"write files it cannot see names the ones it expects rather than the ones it was "
            f"approved for"
        )

    for a_judgement in JUDGEMENTS_EVERY_AGENT_MAKES:
        said = getattr(what_the_planning_agent_concluded.judged, a_judgement)
        assert said not in what_the_second_stage_was_asked, (
            f"the planning agent's {a_judgement} is in the implementer's question: {said!r}. The "
            f"plan is a list of paths with no intent, and putting another model's account of it in "
            f"front of the writer makes the change a reaction rather than an application — and a "
            f"gate cannot see the difference, because both arrive as a written file"
        )
