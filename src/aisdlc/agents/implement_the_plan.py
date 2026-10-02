"""§10's implementation agent, writing the files an approved plan named.

**The plan is the boundary of what may change, and both edges of it are checked.** §36 says
a human approves an exact artifact, and an approval of a plan naming one file says nothing
about a second file the agent found interesting. So a file the plan did not name is
refused, and — the edge that is easy to forget — a file the plan *did* name and the agent
did not write is refused too. Half an applied plan, reported as done, is the failure a
traceability chain exists to prevent: everything upstream of it still looks complete.

**Both lists are inside that boundary, and the real tier is what proved it.** The plan
carries `files_to_change` *and* `tests_to_add`, and an earlier version of this module read
only the first. The real run asked to add a regression test, the plan named the new file in
`tests_to_add`, and the implementation wrote only the files that already existed — so the
run reported a plan, a verification and a clean suite, and delivered a change to nothing.
A field a plan carries and no agent acts on is worse than a field the plan never had, because
a plan that names a test is a promise to a human that the test will exist.

**Both refusals happen before anything is written**, so a run that stops leaves the
checkout in the state the plan found it in rather than in a mixture. A test asserts that
directly, because a check that runs after the loop would pass every test in the file while
leaving a repository nobody's plan described.

**The path guard here is repeated on purpose, and it has no test.** Every path in
`files_to_change` was proved to be a file of this clone when the plan was made —
`plan_the_change` resolves each one and refuses an escape — so `the_path_inside_the_project`
cannot fire from this call site, and removing it changes nothing that a test can see. A
mutation confirms it. It is kept so the write does not depend on the plan having been
checked, on the day someone hands a plan to this function that did not come from
`plan_the_change`; a guard that cannot fire is still a guard, and the honest way to have one
is to say here that it is unreachable rather than to let a reader assume it was reached.

**What is checked, and is checked with teeth, is membership of the plan.** That is the
stronger property, it is reachable, and it has a test for each of its two edges.

**The model is asked once, for every file, and it may name a path.** Asking per file would
be tidier per prompt and would leave this module unable to enforce the rule that matters:
if the model only ever returns content, "the agent wrote a file nobody approved" becomes
unrepresentable, and an untestable rule is not a rule. The pairing of a path to its content
is therefore the model's to get right, and the refusals below are what catches it getting
that wrong.
"""

from __future__ import annotations

import time

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, ValidationError

from aisdlc.agents.how_to_name_a_file import the_rule_about_naming_a_file
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.what_an_agent_judged import WhatAnAgentJudged
from aisdlc.llm.asking_a_model_for import ask_a_model_for
from aisdlc.llm.correction_budget import (
    how_a_model_is_told_what_was_wrong,
    may_this_run_keep_asking,
)
from aisdlc.tools.filesystem_read import (
    a_path_in_the_project,
    read_file_in_the_project,
    the_path_inside_the_project,
)
from aisdlc.tools.github_clone_repository import ClonedRepository

THE_DEVELOPER_IMPLEMENTATION_AGENT = "aisdlc-dev-impl"


class FileOutsideThePlanError(Exception):
    """The rule is in `implement_the_plan`, and this is the only thing that may say it broke.

    Named after the plan rather than after the agent, because the plan is the thing whose
    boundary was crossed: an approval of an artifact naming one file is not an approval of
    a second one, and a person reading this needs to know a change left the artifact they
    ruled on.
    """


class PlannedFileNotWrittenError(Exception):
    """The rule is in `implement_the_plan`, and this is the only thing that may say it broke.

    The other edge of the same boundary, and the one that is easy to leave unchecked. A plan
    naming three files with two of them written is a repository that is not the one the plan
    describes, and every record downstream of it would still look complete.
    """


class FileWrittenTwiceError(Exception):
    """The rule is in `implement_the_plan`, and this is the only thing that may say it broke.

    Its own error rather than the boundary one above it, because the faults are different:
    this is not a change nobody approved, it is one path answered twice, where the second
    answer would silently win.
    """


class FileToWrite(BaseModel):
    """One file as it should end up, and where it goes.

    Two required fields and nothing else, so a model cannot answer with a link, a branch or
    a repository and have any of it taken seriously. The content is the whole text, not a
    patch: a diff format is a second grammar to get wrong, and a failed patch is a
    half-applied change to somebody's repository.
    """

    path: str
    content: str


class WhatTheImplementerConcluded(BaseModel):
    """The model's answer: every file of the plan, and the implementer's judgement of them.

    **A wrapper rather than a bare `list[FileToWrite]`** because the model is asked for a class
    it can be validated against, and a list is not one.

    **The three judgements are required, and `what_it_could_not_settle` is the one worth
    having.** The plan is a list of paths with no intent, and a real run showed what that costs:
    the implementer read only `files_to_change`, invented a mechanism nobody had specified, and
    the suite reported green twice over a diff of two test files and no route. The sentence that
    would have caught it is the implementer's to write, and it is asked in the same call as the
    files — so there is no second model call to pay for, and no way to judge a change that is not
    the one beside the judgement. A model with nothing to report has words to reach for rather
    than a blank, because a blank field reads as *the implementer had nothing to say* and that is
    indistinguishable from *nobody asked*.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    files: list[FileToWrite] = []
    judged: WhatAnAgentJudged


def the_paths_the_plan_names(plan: ImplementationPlan) -> list[str]:
    """Every path the approved plan accounts for, in the order the artifact lists them.

    **All three, and the middle one exists because a real run could not finish a change.**
    `files_to_change` names files that are there, `files_to_add` names what the change brings into
    being, and `tests_to_add` names tests that do not exist yet. A rule over one list is a rule
    over part of a plan, and the part that was missing produced a red delivery: an issue asked for
    an endpoint, the route could not be named anywhere, and `FileOutsideThePlanError` then refused
    the implementer for writing the file the request was about.

    **One place, so a reader is not left comparing three lists** to work out what may change.
    """
    return [*plan.files_to_change, *plan.files_to_add, *plan.tests_to_add]


def _no_correction_on_the_first_question(what_was_wrong: str | None) -> str:
    """Nothing at all on the first question, because there is nothing to correct yet.

    The wording of a correction is one rule for six agents and lives in
    `aisdlc.llm.correction_budget`. This is only the absence of one, which is this node's own
    business: a first question that carried "your last answer was refused" would be telling a
    model about a conversation that had not happened.
    """
    if what_was_wrong is None:
        return ""

    return f"\n\n{what_was_wrong}"


def the_prompt_to_implement(
    plan: ImplementationPlan,
    clone: ClonedRepository,
    what_was_wrong: str | None = None,
) -> str:
    """The question put to the model: what should each of these files contain now?

    Every file's current text is inlined, and that is the load-bearing part of the prompt.
    A model asked to change a file it cannot see writes from imagination, and the shape of
    the mistake is a plausible file that is missing whatever was already there — which for
    a `.gitignore` means a truncated list of rules and a silent regression for whoever
    relied on the ones that vanished.

    The text is read through `read_file_in_the_project` rather than `Path.read_text`, so
    the same boundary every other reader of this clone goes through is the one in force,
    and a plan that somehow carried a path out of the checkout fails here rather than being
    read.
    """
    what_there_is_now = "\n\n".join(
        f"--- {path} ---\n"
        f"{read_file_in_the_project(a_path_in_the_project(clone.path, path)).text}"
        for path in plan.files_to_change
    )

    return (
        f"You are implementing one approved plan for the public repository "
        f"{clone.path.name}.\n"
        "Write the files the plan names, and nothing else.\n"
        "\n"
        "Answer with `files`: for every file the plan names, its path and the **complete "
        "text that file should end up holding**. The whole text, not a diff and not an "
        "addition — a file that loses what was already in it is a regression nobody asked "
        "for.\n"
        f"Do not write any path the plan does not name. The plan was approved by a person, "
        f"and it accounts for exactly these paths:\n"
        f"{', '.join(the_paths_the_plan_names(plan))}\n"
        "\n"
        "Each file below is shown with the text it holds right now:\n\n"
        f"{what_there_is_now}"
        + _no_correction_on_the_first_question(what_was_wrong)
        + the_rule_about_naming_a_file()
    )



def implement_the_plan(
    clone: ClonedRepository,
    plan: ImplementationPlan,
    model: BaseChatModel,
) -> WhatTheImplementerConcluded:
    """The files the plan named, written with the content the model proposed.

    Validated rather than cast, for the reason every node in this system does it: a provider
    that ignores the schema is a real case rather than a theoretical one, and a file written
    from a mis-parsed answer is somebody's repository changed on a guess.

    **A wrong shape is corrected once, on the budget every other reasoning node spends, and
    nothing else here is.** This node asked once and refused the reply, which was defensible
    until a run refused one: the same model, the same mistake, a correct plan for a file written
    as YAML, and three minutes spent before the run ended. The planner was corrected for exactly
    this in the cycle before and `implement_the_plan` was named in that commit as the one place
    left uncorrected, on the grounds that no run had failed there. One has.

    **The other three refusals stay refusals, and four tests say why.** A file the plan did not
    name is a change nobody approved and asking again is asking a model to try again at
    something it was not approved to do; a path written twice means a choice was available and
    nothing recorded it; a plan half applied is a repository that is not the one the plan
    describes. A model that misread the notation has done the work and spelled it wrong, which
    is a different event from a model that declined to do the work, and only the first one is
    worth a second question.

    **Nothing is written until an answer has been accepted**, and that is why the correction
    costs nothing to undo: a refused answer had a whole list of files in it, and a run that wrote
    them before refusing would leave the first attempt behind when it asked again.
    """
    what_was_wrong: str | None = None
    last: ValidationError

    began_at = time.monotonic()
    asked_so_far = 0
    while may_this_run_keep_asking(asked_so_far, began_at):
        asked_so_far += 1
        try:
            answer = WhatTheImplementerConcluded.model_validate(
                ask_a_model_for(model, WhatTheImplementerConcluded).invoke(
                    the_prompt_to_implement(plan, clone, what_was_wrong)
                )
            )
            _every_written_file_was_named_by_the_plan(plan, answer.files)
            _every_file_the_plan_named_was_written(plan, answer.files)
            break
        except ValidationError as refused:
            what_was_wrong = how_a_model_is_told_what_was_wrong(refused)
            last = refused
    else:
        raise last

    moved = _which_files_the_answer_actually_moved(clone, answer.files)
    if not moved:
        raise AWriteThatChangesNothingError([write.path for write in answer.files])

    for write in answer.files:
        where = the_path_inside_the_project(a_path_in_the_project(clone.path, write.path))
        where.parent.mkdir(parents=True, exist_ok=True)
        where.write_text(write.content)

    return answer


def _which_files_the_answer_actually_moved(
    clone: ClonedRepository, files: list[FileToWrite]
) -> list[str]:
    """The paths whose content differs from what the clone already held.

    **Compared before anything is written, so a refusal leaves the checkout as it was found.** A
    run that rewrote four files and then refused would have changed a repository it declined to
    deliver from, and a person going to look at the clone afterwards would be reading a tree the
    run had touched. A file that was not there counts as moved, because a new file is a change by
    definition and `tests_to_add` exists for it.
    """
    moved: list[str] = []
    for write in files:
        where = the_path_inside_the_project(a_path_in_the_project(clone.path, write.path))
        if not where.is_file() or where.read_text(encoding="utf-8") != write.content:
            moved.append(write.path)
    return moved


class AWriteThatChangesNothingError(Exception):
    """Every file the plan named already had the content the model proposed for it.

    **A real run died on this, seven minutes in, and it died in the wrong place.** An implementer
    asked to add ignore rules wrote a file byte-identical to the one already in the clone, `git
    add` staged nothing, `git commit` answered *nothing to commit, working tree clean*, and the
    run raised `TheChangeWasNotCommittedError` — which says the change is not recorded, when the
    truth is that there was no change to record. This refusal is at the writing, where the fact
    is still knowable, and it says the fact.

    **About the run and not about the file.** A plan naming four files where one was already
    right changed three, and refusing it would punish an implementer for being thorough. Nothing
    was committed only when *every* file already had the content proposed.
    """

    def __init__(self, the_paths: list[str]) -> None:
        """Name every path, because "nothing changed" is a claim somebody has to check."""
        self.the_paths = the_paths
        super().__init__(
            f"Every file this plan named already had exactly the content proposed for it: "
            f"{', '.join(the_paths)}. The suite was run and a change was verified, and there is "
            f"no difference between this run and one that did nothing -- a pull request whose "
            f"diff is empty is the one thing this pipeline must never produce. Either the plan "
            f"asks for something the repository already has, or the model rewrote a file without "
            f"changing it."
        )


def _every_written_file_was_named_by_the_plan(
    plan: ImplementationPlan, written: list[FileToWrite]
) -> None:
    """No path outside the plan may be written.

    Two ways a path is refused, and they are different faults: one is a change nobody
    approved, the other is a path written twice in one answer — where the second would
    silently win and the repository would end up holding whichever answer came last, with
    nothing recording that a choice was available.
    """
    named = the_paths_the_plan_names(plan)
    seen: list[str] = []

    for write in written:
        if write.path not in named:
            raise FileOutsideThePlanError(
                f"{write.path!r} is not a file the approved plan named, so it was not "
                f"written. The plan names {named}, and a person approved that plan rather "
                "than this change."
            )

        if write.path in seen:
            raise FileWrittenTwiceError(
                f"{write.path!r} was written twice in one answer. Two contents for one path "
                "means the agent did not know which one it meant, and letting the second "
                "win would be a coin toss on somebody's repository that nothing records."
            )

        seen.append(write.path)


def _every_file_the_plan_named_was_written(
    plan: ImplementationPlan, written: list[FileToWrite]
) -> None:
    """Every file the plan named must be accounted for, written or explicitly refused.

    A run that carried on with a file missing would verify a repository that is not the one
    the plan describes, while every record between the requirement and the pull request
    still read as complete.
    """
    written_paths = [write.path for write in written]
    missing = [
        path for path in the_paths_the_plan_names(plan) if path not in written_paths
    ]

    if missing:
        raise PlannedFileNotWrittenError(
            f"The plan names {missing} and the answer did not write them, so the checkout "
            "was left alone rather than half-changed. A plan that is not fully applied is "
            "not a plan that was applied, and reporting it as applied is the one thing a "
            "traceability chain must never do."
        )
