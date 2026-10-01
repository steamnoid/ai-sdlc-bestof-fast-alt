"""The planning agent, against a real model and a real repository.

**This is the first stage of a run that is handed a document rather than a repository, and that
is the whole reason it needs proving on its own.** `aisdlc-dev-plan` converts *approved
requirements* into a plan, so what goes in is an artifact a person has already ruled on and what
comes out is the artifact the next gate presents. A plan that is wrong in a way nobody can see is
delivered as a pull request, because every record between the requirement and the diff still reads
as complete — and unlike a report, a plan is acted on rather than read.

**The requirements handed in are the ones production hands this stage, stated here rather than
produced by the real analyst.** Chaining two real agents in a file whose job is to isolate one
would make this a composition test in the tier that exists to prevent that, and the QA analyst's
file beside this one says the same about its input for the same reason. So the input is a
stand-in, and it is named as one.

**The assertion that matters is about the paths, and it is mechanical because the substrate is a
checkout.** Three lists answer three different questions about where a change lives, and each of
the three has a way to be wrong that only the filesystem can answer: a file to change that is not
there, a file to add that already is, and a test in a directory this repository does not put tests
in. All three are checked here against the clone on disk rather than by waiting for the node to
raise — **a test that trusted `PlannedFileNotFoundError` would pass on a node whose check had
been commented out**, which is the same argument the discovery tier makes about its own evidence.

**Nothing is asserted about which files the plan chose.** Real output varies per run, and a test
that pinned the paths a model picked would fail every time the model was different without ever
finding a defect. What is asserted is that every path it picked is a path of *this* repository,
which is a claim about the answer rather than about the model.

**The provider is a parameter rather than a constant, so proving a second one is a different run
and not a rewritten test.** A provider the deployment is not configured for says so out loud
rather than passing quietly — a green run that never called a model is the failure this tier
exists to prevent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aisdlc.agents.a_value_that_says_something import a_value_that_says_something
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.plan_the_change import plan_the_change
from aisdlc.agents.requirements import Requirements
from aisdlc.agents.what_the_planner_concluded import ImplementationPlanAnswer
from aisdlc.domain.repository import Repository
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.filesystem_read import (
    APathNotAPathError,
    PathOutsideTheProjectError,
    a_path_in_the_project,
    the_path_inside_the_project,
)
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE

pytestmark = pytest.mark.e2e

# **The five lists, restated rather than read off the module that asks the model for them.** The
# planner asks for exactly these, and importing its own constant would make this file agree with
# the code by construction — so a list dropped from the artifact and from the prompt together would
# leave every assertion here green. These are the fields a person is asked to approve, and there
# are five.
THE_FIELDS_THE_GLOSSARY_NAMES = (
    "files_to_change",
    "files_to_add",
    "tests_to_add",
    "dependencies",
    "migrations",
)

JUDGEMENTS_THE_PLAN_MAKES = (
    "what_it_found",
    "what_it_could_not_settle",
    "what_it_expects_next",
)

# The requirements production hands this stage for the run this repository's real tier makes.
# Stated here rather than produced by the analyst, and the reason is the tier's own: a file that
# isolates one agent must not compose two.
THE_APPROVED_REQUIREMENTS = Requirements(
    requirements=[
        "The repository's README must name the Node version this project is developed against, "
        "because a contributor reading it today cannot tell which version to install."
    ],
    acceptance_criteria=[
        "A line in the README names a Node version in the form `Node <major>.<minor>`."
    ],
    ambiguities=[
        {
            "what_is_undetermined": "Whether the version to name is the one the build already "
            "uses or the newest released one, and only a person who maintains this repository can "
            "say which was meant.",
            "who_can_answer_it": "a person",
        }
    ],
)


def _where_this_path_lands(clone: ClonedRepository, a_path: str) -> Path | None:
    """Where a path the plan named really is, or `None` when it does not land inside the clone.

    **The same two tools the node uses, so this is the node's own answer rather than a second
    rule about what a path may be.** A path written as `../secrets` or as an absolute one lands
    outside the checkout and passes an existence check perfectly well, and a plan is the first
    thing in this system that *writes* paths — so the confinement check is a claim about the
    answer, and not only about the writing.

    A refusal is reported as `None` rather than raised, because the question here is whether the
    plan carried such a path and not why the boundary refused it.
    """
    try:
        return the_path_inside_the_project(a_path_in_the_project(clone.path, a_path))
    except (APathNotAPathError, PathOutsideTheProjectError):
        return None


def _the_directories_this_clone_keeps_a_test_in(clone: ClonedRepository) -> set[str]:
    """Every directory of this clone that holds a test of its own, named as a plan names a path.

    **Directly in it and never below it, because `tests/` is the case that proves the rule.** A
    recursive search says yes for every tier this repository has — `tests/` holds none of them and
    holds two directories full of them — so a check that looked below would pass exactly the plan
    a real run once wrote, where a test landed in a directory no test had ever been in and the
    suite passed identically on both sides of the change.

    **Somebody else's code is skipped by name rather than by a second list here.** The same
    directories the inspection skips, read from the module that decides what a model is shown, so
    a repository with a vendored test suite cannot make this file walk somebody else's tests.

    **The top level is one of the candidates, and that is what makes a refusal below about the
    plan rather than about this helper.** A repository that keeps its tests flat puts them beside
    the code — `test_the_thing.py` next to `the_thing.py` — and a helper that walked only
    subdirectories would refuse a root-level test in exactly those repositories. Whether the top
    level of *this* clone holds a test is a fact about the clone and is asked of the clone.
    """
    directories: set[str] = set()

    for a_directory in [clone.path, *clone.path.rglob("*")]:
        if not a_directory.is_dir():
            continue
        its_parts = a_directory.relative_to(clone.path).parts
        if any(a_part in DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE for a_part in its_parts):
            continue
        if any(a_directory.glob("*.test.*")) or any(a_directory.glob("*.spec.*")):
            directories.add(str(a_directory.relative_to(clone.path)))

    return directories


@pytest.fixture(scope="module")
def a_real_plan(
    the_repository: Repository,
    the_cloned_repository: ClonedRepository,
    the_model_for,
    request,
) -> ImplementationPlanAnswer:
    """One real plan, shared by every assertion about it.

    Module scope, because a clone and a model call are the expensive parts and the four assertions
    below are four contracts about *one* plan. Asserting separately about separate runs would
    prove only that the model answers differently each time, which is true and is not what this
    file is for.

    **The read-only clone, because this stage does not write.** The plan names paths and the
    implementer writes them; a planner that edited the checkout would be doing the next agent's
    job, and nothing in a real run would notice.

    **The runner is not asked what it collects**, which is what production hands this stage — an
    empty string rather than a guessed glob. So the question a planned test's directory has to
    answer is asked of the repository instead, and that is the branch the assertions below
    exercise.
    """
    return plan_the_change(
        THE_APPROVED_REQUIREMENTS,
        the_cloned_repository,
        the_repository,
        the_model_for(request.param),
    )


@pytest.mark.parametrize("a_real_plan", list(LlmProvider), indirect=True)
def test_a_real_model_plans_something_a_person_could_approve(
    a_real_plan: ImplementationPlanAnswer, the_placeholders: frozenset[str]
) -> None:
    """The artifact is the artifact type, and it names something to do.

    **A field is either absent or says something, and the third state is refused.** `any()` over a
    raw list is true for a list holding a space, so a plan whose `files_to_change` was `[" "]` is a
    plan that says nothing about which file to change — and it is exactly what the sibling tier
    found a real model answering for a whole artifact.

    **Every field and not the four the emptiness rule looks at.** The plan's own refusal asks
    whether *anything* was named, and a plan with four real paths and a blank one is a real answer
    with a hole in it, which is a card a person rules on. And "names something to do" is checked
    across all five lists, so a field this file forgot to know about could not hide there.
    """
    assert isinstance(a_real_plan, ImplementationPlanAnswer), (
        f"the stage answered with {type(a_real_plan).__name__} rather than the answer type, so "
        "nothing downstream can rely on which fields the plan and its judgement arrived in"
    )

    the_plan = a_real_plan.plan
    assert isinstance(the_plan, ImplementationPlan), (
        f"the answer carries {type(the_plan).__name__} rather than the artifact a gate presents"
    )

    for a_field in THE_FIELDS_THE_GLOSSARY_NAMES:
        said = getattr(the_plan, a_field)
        assert a_value_that_says_something(said) or said == [], (
            f"{a_field} is {said!r}, which is neither an answer nor an absence: a person reading "
            "this plan cannot tell a field holding a space from a field naming a file, so a plan "
            "that says nothing in a field has to say nothing the way an absent list already does"
        )
        for one_of_them in said:
            assert str(one_of_them).strip().lower() not in the_placeholders, (
                f"{one_of_them!r} in {a_field} is placeholder text, which means the model returned "
                "a shape rather than a path"
            )

    assert any(getattr(the_plan, a_field) for a_field in THE_FIELDS_THE_GLOSSARY_NAMES), (
        "the planner was asked to plan one change and named nothing in any of the five lists. That "
        "is a fault in this run rather than a finding about the repository, and the node refuses "
        "it — so a plan reaching this assertion means the refusal is not armed"
    )


@pytest.mark.parametrize("a_real_plan", list(LlmProvider), indirect=True)
def test_every_path_the_plan_names_is_a_path_of_this_repository(
    a_real_plan: ImplementationPlanAnswer, the_cloned_repository: ClonedRepository
) -> None:
    """The grounding assertion: three lists, three promises, and the clone answers all three.

    **Each check is the one a named refusal makes, restated as an assertion about the answer.**
    `PlannedFileNotFoundError` for a file to change that is not there; `PlannedFileToAddFoundError`
    for a file to add that already is, because two descriptions of one file means whichever step
    ran second silently wins; and the test-directory rule for a test this repository does not put
    tests in. Each is checked here against the filesystem rather than by expecting the node to have
    raised, so a node whose check was weakened is caught by this file.

    **The confinement check is the fourth promise and the one a plan cannot break by accident.** A
    path written as `../something` resolves to a real file outside the checkout and would satisfy
    an existence check perfectly well, so `files_to_change` is proved a file *of this clone* rather
    than a file somewhere the path reaches.
    """
    the_plan = a_real_plan.plan

    not_a_file_of_this_clone = [
        a_path
        for a_path in the_plan.files_to_change
        if not (the_cloned_repository.path / a_path).is_file()
    ]
    assert not not_a_file_of_this_clone, (
        f"{not_a_file_of_this_clone} are named as files to change, and the clone this plan was "
        "made from does not hold them. Either the model invented them or it remembered another "
        "repository, and either way the implementation agent would be asked to change a path that "
        "is not there — inventing the file or failing a long way from the mistake"
    )

    already_there = [
        a_path for a_path in the_plan.files_to_add if (the_cloned_repository.path / a_path).exists()
    ]
    assert not already_there, (
        f"{already_there} are named as files this change creates, and they are already files of "
        "this clone. A path that exists is either also in files_to_change — two descriptions of "
        "one file, and whichever step ran second would silently win — or a path the planner did "
        "not read the inspection for"
    )

    the_directories_that_keep_a_test = _the_directories_this_clone_keeps_a_test_in(
        the_cloned_repository
    )
    if not the_directories_that_keep_a_test:
        pytest.skip(
            "this clone holds no directory with a test of its own, so the planner was asked "
            "nothing about where tests go and there is nothing here to check a planned test "
            "against. That is an honest state for a repository with no tests, and this tier does "
            "not judge whether the repository should have any."
        )

    nowhere_a_test_belongs = [
        a_path
        for a_path in the_plan.tests_to_add
        if str((the_cloned_repository.path / a_path).parent.relative_to(the_cloned_repository.path))
        not in the_directories_that_keep_a_test
    ]
    assert not nowhere_a_test_belongs, (
        f"{nowhere_a_test_belongs} are tests this repository does not keep tests in — the "
        "directories holding a test of their own are "
        f"{sorted(the_directories_that_keep_a_test)}. A test beside no other test is one this "
        "suite will not run: the delivery would be a file nobody opened, the suite would pass "
        "identically on both sides of the change, and verification would fail two stages later "
        "about a test that had never been executed"
    )

    every_path_it_named = [
        *the_plan.files_to_change,
        *the_plan.files_to_add,
        *the_plan.tests_to_add,
    ]
    outside_the_checkout = [
        a_path
        for a_path in every_path_it_named
        if _where_this_path_lands(the_cloned_repository, a_path) is None
    ]
    assert not outside_the_checkout, (
        f"{outside_the_checkout} do not land inside the clone this run is working on, so they are "
        "paths this system cannot act on. A plan is the first thing in this system that writes "
        "paths, and an agent reasoning about somebody else's repository has no business writing "
        "outside the checkout it was handed"
    )


@pytest.mark.parametrize("a_real_plan", list(LlmProvider), indirect=True)
def test_the_plan_carries_no_field_but_the_ones_a_person_is_asked_to_approve(
    a_real_plan: ImplementationPlanAnswer,
) -> None:
    """The artifact's own fields are the glossary's, and the judgement is not one of them.

    **Asserted on the fields rather than on a count, and said twice in this tier on purpose.** A
    gate presents this artifact and an `Approval` names it with a version, so a field added here is
    material in front of a decision that was never about it — and a plan carrying the planner's own
    opinion of itself is a document whose version covers text no human ruled on.

    **Five, restated at the top of this file, and this is what holds that restatement honest** —
    read off the artifact this run produced rather than off the class it was declared as, so a
    plan that arrived as something else could not answer for `ImplementationPlan`.
    """
    the_fields_the_plan_carries = set(type(a_real_plan.plan).model_fields)

    assert "judged" not in the_fields_the_plan_carries, (
        "the plan a gate presents now carries the judgement. An Approval names this artifact "
        "with a version, so a document that also carries a model's opinion of its own contents "
        "is a document whose version covers material the decision was not about"
    )

    added = the_fields_the_plan_carries - set(THE_FIELDS_THE_GLOSSARY_NAMES)
    assert not added, (
        f"the plan carries {sorted(added)}. A person is asked to approve exactly the five lists "
        "named at the top of this file, so a field added here is material in front of a gate that "
        "no rule asked for — and every assertion in this file that loops over the fields would "
        "then be checking a field the glossary does not name"
    )


@pytest.mark.parametrize("a_real_plan", list(LlmProvider), indirect=True)
def test_the_plan_says_what_it_found_and_what_it_could_not_settle(
    a_real_plan: ImplementationPlanAnswer, the_placeholders: frozenset[str]
) -> None:
    """Three sentences of judgement, beside the plan rather than inside it.

    **`what_it_could_not_settle` is the one worth having, and a real run is the reason.** A plan
    names paths and no intent, so the sentence that would have caught the implementation agent
    inventing a mechanism nobody specified is the planner's to write — and the run that lost a
    change to a diff of two test files and no route is what it would have said. An empty field
    reads as *the planner had nothing to say*, which is not a thing anybody can check.

    **Placeholder text is refused and silence is not.** The system offers an agent with nothing to
    report two whole sentences to say so, and those are not placeholders — a field carrying "the
    requirements answered every question" is an honest answer, and what is refused here is a field
    carrying the *shape* of an answer.
    """
    for a_judgement in JUDGEMENTS_THE_PLAN_MAKES:
        said = getattr(a_real_plan.judged, a_judgement)
        assert said.strip(), (
            f"the planning agent left {a_judgement} empty. This agent is handed a document rather "
            "than a repository, so its doubt is the only one in the run that is about what the "
            "approved requirements did not settle — and an empty field reads as a doubt nobody "
            "had, which is the one a planner reading the card most needs not to believe"
        )
        assert said.strip().lower() not in the_placeholders, (
            f"{said!r} is placeholder text in {a_judgement}, which means the model returned "
            "a shape rather than a judgement"
        )
