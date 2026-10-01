"""Planning as a node: ask the model, then prove every file the plan names is there.

The order matters and it is the whole design. The model answers first, in a shape whose
only fields are lists of strings, and only then does the system check what it said against
the clone on disk. A single pass in the other order would either check a file the model
has not named yet, or hand the model the file list and ask it to confirm it — which is a
model agreeing with a list this system chose, and an agreement of that kind is not a plan.

**Grounding is checkable because the substrate is a clone.** `files_to_change` is a promise
about files that exist; the implementation agent downstream would be asked to change a path
that is not there, and it would either invent the file or fail at a point far from the
mistake. That refusal could not exist at all without a checkout to check against, and that
is the argument for a clone over an API read, stated a second time in a second place.

**`tests_to_add` is not checked, on purpose.** A test that does not exist yet is the whole
point of that list, so checking it would refuse every correct plan. The two lists answer
different questions and the difference is the reason the rule exists for one of them.

**The boundary comes from the filesystem tools, not from a second spelling of it.** A
`..` that points at a real file outside the checkout passes an existence check and is
exactly the escape a plan must not carry, because a plan is the first thing in this system
that *writes* paths. So the path is resolved by `the_path_inside_the_project` and compared,
which handles `..`, a symlink and an absolute path in one decision.

**This node does not write, and that is a rule rather than a promise.** §10 says the
planning agent must not modify code, and `tests/unit/test_plan_the_change.py` hashes the
whole checkout before and after to keep it that way — because a prohibition kept only in a
docstring is a prohibition a later edit can weaken without anything turning red.
"""

from __future__ import annotations

import time

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from aisdlc.agents.implementation_plan import EmptyPlanError, ImplementationPlan
from aisdlc.agents.requirements import Requirements
from aisdlc.agents.requirements_answer import AnAmbiguity
from aisdlc.agents.what_the_planner_concluded import ImplementationPlanAnswer
from aisdlc.domain.repository import Repository
from aisdlc.llm.asking_a_model_for import ask_a_model_for
from aisdlc.llm.correction_budget import (
    how_a_model_is_told_what_was_wrong,
    may_this_run_keep_asking,
)
from aisdlc.tools.filesystem_read import (
    APathNotAPathError,
    a_path_in_the_project,
    the_path_inside_the_project,
)
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import an_inspection_of_the_code
from aisdlc.tools.run_tests import what_the_suite_says_it_collects

THE_DEVELOPER_PLANNING_AGENT = "aisdlc-dev-plan"

# The artifact's own fields, named in the order the glossary lists them. The model is asked
# for these and nothing else, and the shape has nowhere to put an address — a link a
# reviewer opens is derived from `owner`/`name`/`branch`/`path`, and a model asked for one
# will produce a plausible one pointing somewhere else.
# **Three lists about paths, and each answers a different question.** `files_to_change` is what
# exists and is modified in place; `files_to_add` is what this change brings into being;
# `tests_to_add` is tests that do not exist yet. The second was missing until a real run showed
# that a plan which cannot name a new file cannot deliver a new endpoint. The order follows the
# questions, and the two "does not exist yet" lists are adjacent so a reader has to notice that
# they differ.
THE_FIELDS_THE_PLAN_MAY_NAME = (
    "files_to_change",
    "files_to_add",
    "tests_to_add",
    "dependencies",
    "migrations",
)

# **The three judgements, asked in the same question as the plan.** One call and one answer, so
# there is no second model call to pay for and no way for a judgement to be written about a plan
# that is not the one beside it. The middle one is the one worth having: a real run's implementer
# wrote *the inspection does not show whether the existing `.gitignore` already ignores
# `e2e.db-wal`*, and that sentence is the whole of what was missing from a plan that shipped a
# test asserting nothing.
#
# **The third was spelled `what_it_expectes_next` here, and a prompt string is not covered by a
# type.** The model was asked for a field the tool schema it is bound to does not declare, so a
# model obeying this prose would return a key `WhatAnAgentJudged` refuses — a `ValidationError`
# spending a correction, or a dropped field. It survived because four other stages spell the same
# field correctly and a real run's model followed the schema rather than the prose, which is luck
# rather than correctness. `tests/test_every_field_a_stage_asks_for_is_a_field_the_answer_has.py`
# now asks every stage, so a second copy of this mistake is a failure rather than a diff.
THE_JUDGEMENTS_THE_PLAN_MAY_NAME = (
    "what_it_found",
    "what_it_could_not_settle",
    "what_it_expects_next",
)

THE_ROOT_DIRECTORY = ""
"""The repository's top level, as the directory rules below name it.

`Path("a.test.ts").parent.relative_to(clone)` is `.` there, and `.` is a name a runner's `include`
patterns would never contain and a reader of a refusal would not recognise. So it is written as
the empty string — which is what a path relative to the root is — and the two helpers that
decide a directory are handed the same spelling in both directions. A rule that has to name the
root is a rule somebody will leave out of the list.
"""


class PlannedTestDirectoryNotFoundError(Exception):
    """The rule is in `plan_the_change`, and this is the only thing that may say it broke.

    The other half of the grounding, and the half that is *not* about a file being missing.
    `tests_to_add` names files that do not exist yet, so nothing about their existence can be
    checked — but the directory they go in can be, and that is where a sentence that arrived
    in a path field ends up. A segment nobody has a directory for is not a path anything
    recognises, whatever the model meant by it.
    """


class PlannedTestDirectoryNotCollectedError(Exception):
    """A test's directory is one the clone has, and one the repository's runner does not collect.

    **The other half of the test-directory rule, and the half a real run got past.** A directory
    existing is a fact about the filesystem; a directory being collected is a fact about the
    runner, and on the run that delivered #9 the two came apart silently — the plan named
    `tests/api-health.test.ts`, `tests/` exists, every check this system makes passed, and the
    container reported the same 65 tests on both sides of a change whose whole content was the two
    files nobody had opened.

    **The runner is asked, and its own announcement is quoted in the refusal.** Reading a
    project's config file would mean parsing a language this system knows nothing about, written by
    a runner this system has never run, and the runner already prints the include it is using.
    Asking it is a fact, and quoting it is what makes the refusal something a model can act on
    rather than a complaint.
    """


class PlannedFileToAddFoundError(Exception):
    """A plan asked to create a file that is already there, or to both change and create one.

    **The mirror of `PlannedFileNotFoundError`, and for the same reason.** That one refuses a path
    that is not in the clone, because a plan against nothing is a plan the implementer will invent.
    This one refuses a path that **is** in the clone, because a plan asking to create a file that
    exists either means the planner did not read the inspection, or means a second description of a
    file the plan is also changing in place — and those two would be written by two different steps
    with nothing recording which one won.

    **A real run found the hole this now fills.** A whole run commissioned from an issue asking for
    a `GET /api/health` endpoint produced a plan that could only name a configuration file, because
    `files_to_change` refuses what is not there and `tests_to_add` is for tests. The route could not
    be named, so it was not written, so the delivery went red — honestly reported, and still a
    change that did not do what was asked of it.
    """


class PlannedFileNotFoundError(Exception):
    """The rule is in `plan_the_change`, and this is the only thing that may say it broke.

    Named for the plan's own promise rather than for the model that broke it, because the
    model is not what a caller can act on: the answer is a file the repository does not
    have, and a person reading this needs to know a plan is against nothing.
    """


def the_prompt_to_plan_a_change(
    requirements: Requirements,
    inspection: str,
    repository: Repository,
    what_was_wrong_about_the_last_answer: str | None = None,
) -> str:
    """The question put to the model about one change, over one inspected repository.

    The inspection is inlined rather than referenced because the model has no other way to
    see the repository: this node is given what was inspected, and a question that omitted
    it would leave the model planning against whatever it could infer from a repository's
    name — which for a repository with a lockfile is a plausible guess and for one without
    is nothing at all.

    Nothing here asks the model to change anything, and that is deliberate rather than
    modest. The model is asked for a plan, and the plan is a list of names; the writing is
    a separate agent that runs after a person has approved this one, and it is a separate
    agent so that this one cannot be tempted into a job it is forbidden to do.

    The correction is *added* to the question rather than replacing it, because a second
    answer to a different question is worth nothing: without the inspection and without the
    change that was asked for, the model has only the word "wrong" to work from.
    """
    _the_requirements_as_a_question = _how_the_requirements_read(requirements)
    correction = (
        ""
        if what_was_wrong_about_the_last_answer is None
        else (
            "\nYour last answer was wrong, and this is what was wrong with it:\n"
            f"{what_was_wrong_about_the_last_answer}\n"
            "A field that names a path is a path and nothing else — no explanation, no "
            "reason, no sentence.\n"
        )
    )

    return (
        f"You are planning one change to the public repository "
        f"{repository.owner}/{repository.name}.\n"
        "Plan only. Do not write, edit or suggest the contents of any file.\n"
        "\n"
        f"The approved requirements this plan implements:\n{_the_requirements_as_a_question}\n"
        "\n"
        f"Answer in two parts. The first is the plan itself, naming these fields and nothing "
        f"else: {', '.join(THE_FIELDS_THE_PLAN_MAY_NAME)}. The second is three sentences of "
        f"judgement, naming {', '.join(THE_JUDGEMENTS_THE_PLAN_MAY_NAME)}.\n"
        f"{correction}"
        "\n"
        "In `files_to_change`, name only files the inspection below shows already exist — "
        "every one of them will be changed in place, and a path that is not there is a plan "
        "against nothing.\n"
        "In `files_to_add`, name files this change creates that the inspection does not show. "
        "A request for something that does not exist yet — an endpoint, a module, a command — is "
        "answered here and nowhere else, and a path that is already in the inspection is refused "
        "rather than described twice.\n"
        "In `tests_to_add`, name tests that do not exist yet. That is what this list is for, "
        "so a test that is not in the inspection is expected here and is not a mistake.\n"
        "Leave `dependencies` and `migrations` empty unless the change genuinely needs them; "
        "an absent list is read as absent rather than as unknown.\n"
        "\n"
        "Name something in at least one of these five lists. A plan with all five empty is a "
        "fault in this run rather than a finding about the repository, and it is refused: the "
        "next thing that happens to a plan is that a person is asked to approve it, and a "
        "person cannot tell an empty plan from a real one by looking at it.\n"
        "\n"
        "Every name in this plan is a path and nothing else. A path is file names separated by "
        "`/`, and a sentence is not one however carefully it explains itself — an earlier "
        "version of this prompt invited a sentence here, and a model obliged by writing six "
        "hundred characters of explanation into `files_to_change`.\n"
        "\n"
        f"Inspection of {repository.owner}/{repository.name}:\n"
        f"{inspection}"
    )


def plan_the_change(
    requirements: Requirements,
    clone: ClonedRepository,
    repository: Repository,
    model: BaseChatModel,
    what_the_suite_announced: str = "",
) -> ImplementationPlanAnswer:
    """The plan for one change, over the clone this run is working on, and the judgement of it.

    Validated rather than cast, for the reason discovery is: `with_structured_output` is
    typed to hand back either the class or plain data, and a provider that ignores the
    schema is a real case rather than a theoretical one. Validating is not trusting — a
    list of the wrong shape is still refused, here and deterministically.

    **One correction, and the real tier is what asked for it.** Asked to add a regression
    test, `glm-5.3-flash` answered with a filename followed by two sentences explaining why it
    chose that name. The refusal below was correct and total — the run ended having produced
    no plan and no change — so the budget that §14 asks for is spent here, and the real
    answer to "does a model need a second chance" turned out to be yes. The correction is
    added to the question rather than replacing it, because the second answer is otherwise an
    answer to a different question.

    A run that exhausts the budget raises the *last* refusal. The caller needs the last thing
    that was wrong, because that is what a person can act on; three near-miss citations help
    nobody decide what to do next.

    **The inspection carries the file contents, and this stage names paths from it.** A plan is
    `files_to_change` — files that exist and are edited in place — so a planner shown only a
    listing is choosing from filenames it has not read, and a real run refused a plan for
    reasoning about a `Dockerfile` whose contents the plan itself said it had not seen.
    `an_inspection_of` was built for discovery and the fix had been made for discovery without
    anyone checking the stages after it;
    `tests/test_every_stage_reasoning_about_a_file_is_shown_it.py` now asks every stage that
    reads a repository.
    """
    inspection = an_inspection_of_the_code(clone)
    what_was_wrong: str | None = None
    last: (
        APathNotAPathError
        | EmptyPlanError
        | PlannedFileNotFoundError
        | PlannedFileToAddFoundError
        | PlannedTestDirectoryNotFoundError
        | PlannedTestDirectoryNotCollectedError
        | ValidationError
    )

    began_at = time.monotonic()
    asked_so_far = 0
    while may_this_run_keep_asking(asked_so_far, began_at):
        asked_so_far += 1
        # **The validation is inside the try, and that is the whole of this change.** A plan
        # of four empty lists is refused where the plan is built, so a `try` that began after
        # the validation would never have seen it — and one correction spent on an answer
        # that said nothing is the cheapest question in the run.
        #
        # **A `ValidationError` is caught too, and a run is why.** The design this node stated
        # was that a wrong *shape* is refused deterministically here while a right-shaped answer
        # that said nothing is worth one more question. A real model answered a structured
        # request in YAML — `files_to_change: []` and three more correct lines — and pydantic
        # refused it while looking for JSON, so the run ended at the planner. The plan was right
        # and the notation was wrong. That is a wrong answer rather than a refusal to answer,
        # and this loop's whole budget is for wrong answers.
        try:
            answer = ImplementationPlanAnswer.model_validate(
                ask_a_model_for(model, ImplementationPlanAnswer).invoke(
                    the_prompt_to_plan_a_change(
                        requirements, inspection, repository, what_was_wrong
                    )
                )
            )
            _every_file_to_change_is_in_the_clone(clone, repository, answer.plan)
            _every_test_is_where_the_suite_will_look_for_it(
                clone, answer.plan, what_the_suite_announced
            )
            return answer
        except (
            APathNotAPathError,
            EmptyPlanError,
            PlannedFileNotFoundError,
            PlannedFileToAddFoundError,
            PlannedTestDirectoryNotFoundError,
            PlannedTestDirectoryNotCollectedError,
            ValidationError,
        ) as refused:
            # **The empty plan is corrected here for the reason the five other reasoning
            # nodes correct one.** The budget is the same number and the same question as
            # everything else this loop spends it on: may this system go on asking a model
            # for something it already had? A model asked for four empty lists has usually
            # been shown something too large to summarise and has not been refused the chance
            # to say less, and one correction is what it takes to find out.
            what_was_wrong = how_a_model_is_told_what_was_wrong(refused)
            last = refused

    raise last


def _how_the_requirements_read(requirements: Requirements) -> str:
    """The approved requirements, as the plan's question rather than as a list.

    **The requirements and not the sentence somebody typed.** The planner used to be handed
    `what_is_asked_for` — one bare string, arriving after the four analysis stages had run
    and after a person had approved five artifacts, and standing in for all of them. The
    glossary says this agent converts approved requirements into a plan, and the string is
    how it was not doing that: a plan written from the original sentence can contradict the
    security report it never read, and nothing downstream would notice.
    """
    lines = ["Requirements:"]

    for requirement in requirements.requirements:
        lines.append(f"- {requirement}")

    if requirements.acceptance_criteria:
        lines += ["", "Each of these is to be checkable by observing the project:"]
        lines += [f"- {criterion}" for criterion in requirements.acceptance_criteria]

    if requirements.ambiguities:
        lines += [
            "",
            "These were left open by the product analyst. Do not resolve them by guessing. The"
            " ones only a person can answer are marked, and a person is approving this plan with"
            " them in front of them:",
        ]
        lines += [
            f"- {one_line_of(ambiguity)}"
            for ambiguity in requirements.ambiguities
        ]

    return "\n".join(lines)


def one_line_of(ambiguity: AnAmbiguity) -> str:
    """One ambiguity, and whether a person has to settle it before this can be built.

    **Marked, and the mark is the whole of what a run learned from six real ones.** A run refused
    a request to change one word on a home page because nobody had said whether to keep the emoji
    that already followed it, and refused a request naming its own test file because the inspection
    did not show what `.gitignore` covers. **Both were questions the implementer answers by opening
    a file**, and both stopped a run that could have been planned.

    So the ambiguity travels to the person who rules on the plan, marked, instead of stopping the
    run on a model's guess about it. The plan is not delayed by the analyst's doubt, and the
    reader is told which of the doubts are theirs to settle.
    """
    if ambiguity.does_it_block_the_work:
        return (
            f"[only a person can answer] {ambiguity.what_is_undetermined}"
        )
    return ambiguity.what_is_undetermined


def _every_file_to_change_is_in_the_clone(
    clone: ClonedRepository, repository: Repository, plan: ImplementationPlan
) -> None:
    """Both of the plan's path lists, checked against the clone this run is working on.

    Every path in `files_to_change` must be a file of this clone, and every path in
    `tests_to_add` must name a directory this clone has.

    A refusal stops the plan, so a plan naming one invented file among ten real ones does
    not exist — which is the same choice `evidence_for` makes, and for the same reason: a
    plan that is nine-tenths checkable reads to a person as fully checkable.
    """
    for path in plan.files_to_change:
        where = the_path_inside_the_project(a_path_in_the_project(clone.path, path))

        if not where.is_file():
            raise PlannedFileNotFoundError(
                f"{path!r} is in the plan's files_to_change but is not a file of "
                f"{repository.owner}/{repository.name} as it was cloned, so the plan "
                "is against nothing. "
                "The implementation agent would be asked to change a path that is not "
                "there, and it would either invent the file or fail somewhere a long way "
                "from the mistake."
            )

    for path in plan.files_to_add:
        where = the_path_inside_the_project(a_path_in_the_project(clone.path, path))

        if where.exists():
            raise PlannedFileToAddFoundError(
                f"{path!r} is in the plan's files_to_add, and it is already a file of "
                f"{repository.owner}/{repository.name} as it was cloned. This list is for what a "
                "change brings into being, so a path that is already there is either in "
                "files_to_change as well — two descriptions of one file, and whichever step ran "
                "second would silently win — or a path the planner did not read the inspection "
                "for. Either way it is not a plan."
            )

    for path in plan.tests_to_add:
        where = the_path_inside_the_project(a_path_in_the_project(clone.path, path))

        if not where.parent.is_dir():
            raise PlannedTestDirectoryNotFoundError(
                f"{path!r} is in the plan's tests_to_add, but {where.parent} is not a "
                f"directory of {repository.owner}/{repository.name} as it was cloned. A "
                "test goes where the repository already keeps its tests: that is a fact "
                "about the clone and can be checked, where whether some new directory is "
                "wanted is an opinion nobody has approved."
            )


def _every_test_is_where_the_suite_will_look_for_it(
    clone: ClonedRepository, plan: ImplementationPlan, what_the_suite_announced: str
) -> None:
    """Each test's directory is one the repository's runner collects, when the runner has said.

    **A runner that announced nothing is asked nothing.** There is no configuration to read, no
    default to assume and no evidence to reason from, and a refusal here would be this system
    inventing a rule about repositories whose runners it has not interrogated. Silence from the
    runner is not evidence of anything — the same refusal this repository already makes about a
    column, because a fallback is a lie with a position.

    **A glob is matched by its own prefix, and a prefix match would be a lie.** `tests/**` reaches
    `tests/`; `tests/unit/**` does not. Those two lines differ by one segment and that segment is
    the whole defect, so a check that accepted either would accept the case this exists for.
    Anything this system cannot parse is not treated as collecting, and a test in an unreadable
    include is therefore not refused either — see below.
    """
    what_the_runner_collects = (
        _the_directories_the_runner_says_it_collects(what_the_suite_announced)
        if what_the_suite_announced.strip()
        else None
    )

    for a_test in plan.tests_to_add:
        where = the_path_inside_the_project(a_path_in_the_project(clone.path, a_test))
        # **Both sides resolved, and that is the whole fix.** `the_path_inside_the_project`
        # resolves what it returns — it has to, to decide containment — so `where` comes back as
        # the real path. Comparing it against `clone.path` unresolved compares a resolved path
        # with an unresolved one, and on a machine where the projects root is a symlink they are
        # two different strings. macOS makes `/tmp` a link to `/private/tmp`, so a real run with
        # `AISDLC_PROJECTS_DIR=/tmp/...` died here with:
        #
        #     '/private/tmp/.../repository/tests' is not in the subpath of
        #      '/tmp/.../repository'
        #
        # A unit test cannot find this: pytest hands out an already-resolved `tmp_path`, and
        # every one of this repository's tests ran from one. It took a real run on a real
        # machine with a real projects root, which is the only place a symlink shows up.
        # `filesystem_read` already resolves both sides for exactly this reason and says so.
        its_directory = str(where.parent.relative_to(clone.path.resolve()))
        if its_directory == ".":
            # **The root is a directory like any other, and it used to be judged by no rule at
            # all.** This line skipped the whole loop body for a test at the top level, before the
            # runner was consulted and before the repository was asked — so `tests/unit/**` in a
            # runner's own `include` lines, and a root holding no test of its own, both said
            # nothing about it. A real model was refused four times for putting a test where the
            # repository keeps none and then answered with one at the root, and the suite would
            # have passed identically on both sides of the change: the delivery would carry a
            # test nobody opened, and verification would fail two stages later about a test that
            # had never run. That is the exact failure this function was written for.
            its_directory = THE_ROOT_DIRECTORY

        if what_the_runner_collects is not None:
            # **The runner's answer wins, and it is asked first.** It is the more precise one:
            # it names the patterns in force rather than inferring a habit from the filesystem.
            if _the_runner_collects_this_directory(what_the_runner_collects, its_directory):
                continue
            _refuse(a_test, its_directory, what_the_suite_announced)
            continue

        # **The runner is silent, so the repository is asked.** A real run hands the planner
        # `THE_RUNNER_ANNOUNCED_NOTHING_YET`, so this is the branch every real plan takes, and a
        # whole run planned `tests/home-page-greeting.test.ts`, the suite passed identically on
        # both sides of the change, and verification failed two stages later about a test that had
        # never run. A new test goes where a test already is.
        if _this_directory_already_holds_a_test(clone, its_directory):
            continue
        if not _this_repository_keeps_any_test(clone):
            continue
        _refuse(a_test, its_directory, what_the_suite_announced)


def _refuse(
    a_test: str, its_directory: str, what_the_suite_announced: str
) -> None:
    """Say a planned test goes where this repository keeps no test, and stop.

    **Two sentences of cause, and which one is used depends on who answered.** A model told only
    that the suite will not collect its directory cannot tell which of the two rules it broke, and
    a correction it cannot understand is a correction it will repeat.
    """
    why = (
        f" The runner announced:\n{what_the_suite_announced.strip()}\n"
        if what_the_suite_announced.strip()
        else " The runner has not been asked, so this is said from the repository: every test"
        " here is somewhere else, and a test beside no other test is one this suite will not run."
    )
    raise PlannedTestDirectoryNotCollectedError(
        f"{a_test!r} is in the plan's tests_to_add, and {its_directory} is a directory of this"
        " repository — but no test in it lives there, and the suite does not collect it." + why
        + "\n\nA test the runner will not collect is not a test: it will not run, a suite that"
        " passes says nothing about it, and the delivery would be a file nobody opened. Put the"
        " test in a directory the repository already keeps its tests in, or change the runner's"
        " include."
    )


def _this_repository_keeps_any_test(clone: ClonedRepository) -> bool:
    """Whether the clone holds a test file at all, anywhere under the project.

    **The guard that keeps this rule from refusing everything, and it is the same rule the
    runner check above already lives by: silence is not evidence.** A repository that has no test
    yet has no convention to follow, and refusing a first test because no other test exists would
    make this system unable to introduce the first test to anything. So with nothing to compare
    against, this asks nothing and the plan stands.

    **It is the runner's rule, and the reason is the same one.** `test_a_repository_with_no_suite_
    configuration` exists because a refusal here would be this system inventing a rule about
    repositories whose runner it has not interrogated — and a repository with no test has said even
    less than a runner that stayed quiet.
    """
    return any(clone.path.rglob("*.test.*")) or any(clone.path.rglob("*.spec.*"))


def _this_directory_already_holds_a_test(clone: ClonedRepository, its_directory: str) -> bool:
    """Whether the repository already keeps at least one test where this one is going.

    **A second opinion, from the filesystem, for the case the runner cannot answer.** The check
    above asks the runner what it collects, which is the only certain answer — and the runner is
    handed `THE_RUNNER_ANNOUNCED_NOTHING_YET` by the node that drives a real run, so on every real
    plan it answers nothing and the refusal was unreachable. A whole run planned
    `tests/home-page-greeting.test.ts`, the suite passed identically on both sides of the change,
    and verification failed two stages later with a message about a test that had never run.

    **"A new test goes where a test already is", and this repository is shaped to make that
    answerable.** `tests/` exists and holds none of them, `tests/unit` and `tests/integration` hold
    all of them, and a directory holding no test is not a place this repository puts tests. That
    is a fact about the clone, available with no container, no configuration parser and no
    opinion about a runner nobody has run.

    **It is the stronger version of the check above, not a weaker one.** A directory that holds a
    test is a directory the repository demonstrably runs tests from; a directory that holds none
    is one that might be collected or might not, and there is no evidence either way. Where the
    runner has spoken, its answer wins — it is the more precise one.
    """
    # **The root is `clone.path` itself, and `clone.path / ""` is not a directory at all** — the
    # join resolves to the file rather than to a directory, so without this the root would be
    # the one directory the rule could not read. That is why the root is written as `""` and
    # normalised here rather than excluded upstream: a rule that cannot read a case cannot judge
    # it, and the case is the one a real model produced.
    the_directory = (
        clone.path if its_directory == THE_ROOT_DIRECTORY else clone.path / its_directory
    )
    if not the_directory.is_dir():
        return False
    # **Only what is directly in it, and never anything below it.** `tests/` holds no test of its
    # own and holds two directories full of them, so a recursive search says yes and the rule
    # passes exactly the case it exists for. My first version used `rglob` and refused nothing.
    return any(the_directory.glob("*.test.*")) or any(the_directory.glob("*.spec.*"))


def _the_directories_the_runner_says_it_collects(what_the_suite_announced: str) -> list[str]:
    """The `include` patterns out of the runner's own opening lines, as the suite printed them.

    **The reader is `run_tests`'s and not a second one, and this was a real defect.** This
    function used to split a line on every comma, so `tests/unit/**/*.{test,spec}.ts` — one
    pattern — became `tests/unit/**/*.{test` and `spec}.ts`, two globs that match nothing. Every
    directory the runner collects then looked uncollected, the planner refused plans that were
    right, and — because the second fragment names no directory at all — the repository's top
    level looked collected too, which is the case that hid the root entirely.

    `run_tests.py` already had the fix, with the reason written down: a brace is what tells a
    comma inside a pattern from a comma between patterns. **Two readers of one line is two
    opinions about it, and this is the second time in this repository that a rule written once
    and needed twice arrived twice** — the first was the file-contents inspection, and the second
    is this.
    """
    return what_the_suite_says_it_collects(what_the_suite_announced)


def _the_runner_collects_this_directory(the_includes: list[str], a_directory: str) -> bool:
    """Whether any of the runner's includes reaches this directory, by prefix rather than by guess.

    **The prefix has to end on a segment boundary**, which is what makes `tests/unit/**` refuse
    `tests` and `tests/**` accept it. A pattern with no `**` is a file pattern, so a directory is
    only reached by one that could hold files below it.

    **The root is reached by a pattern with no directory part, which is the one exception to
    "a file pattern reaches no directory".** `*.test.ts` names files in the top level and files
    in no directory at all, so it collects the root and nothing else; read by prefix it names a
    prefix that matches no directory, and the root would be refused for a runner that plainly
    collects it. So the empty directory is reached by a pattern that is itself one segment of a
    file name — and by nothing else, because `tests/**` reaching the root would be the same
    prefix rule with a different spelling.
    """
    for a_pattern in the_includes:
        prefix = a_pattern.split("**", 1)[0].rstrip("/")
        if not prefix:
            # `**` with nothing before it reaches every directory in the repository.
            return True
        if a_directory == THE_ROOT_DIRECTORY and "/" not in prefix:
            # A pattern that names no directory collects the top level, and only the top level.
            return True
        if a_directory == prefix or a_directory.startswith(f"{prefix}/"):
            return True
    return False
