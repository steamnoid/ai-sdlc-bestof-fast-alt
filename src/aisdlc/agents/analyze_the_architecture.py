"""The architecture analyst as a node: ask the model about the repository, then build the artifact.

§10 gives this agent `analyze architecture`, `identify relevant modules`, `identify
dependencies` — all repository questions, so like discovery and the product analyst it reads
the clone rather than another agent's artifact. The QA analyst is the exception among the four,
because §10 gives it `analyze requirements`.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from aisdlc.agents.architecture_report import (
    ArchitectureReport,
    EmptyArchitectureReportError,
)
from aisdlc.agents.architecture_report_answer import ArchitectureReportAnswer
from aisdlc.agents.how_to_name_a_file import the_rule_about_naming_a_file
from aisdlc.domain.repository import Repository
from aisdlc.llm.asking_a_model_for import ask_a_model_for
from aisdlc.llm.correction_budget import (
    how_a_model_is_told_what_was_wrong,
    may_this_run_keep_asking,
)
from aisdlc.llm.llm_configuration import a_configuration_from_the_environment
from aisdlc.llm.model_factory import a_model_for
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import an_inspection_of_the_code

THE_FIELDS_THE_ANSWER_MAY_NAME = (
    "findings",
    "modules",
    "dependencies",
    "boundaries",
    "risks",
)

# **The three judgements, asked in the same question as the findings.** One call and one
# answer, so there is no second model call to pay for and no way for a judgement to be written
# about a report that is not the one beside it. The middle one is the one worth having for this
# agent in particular: a reader of an architecture report is entitled to treat a *claimed*
# dependency as a declared one, and this is the only agent in a position to say the two differ.
THE_JUDGEMENTS_THE_ANSWER_MAY_NAME = (
    "what_it_found",
    "what_it_could_not_settle",
    "what_it_expects_next",
)


def the_prompt_to_analyze_the_architecture(
    inspection: str,
    repository: Repository,
    what_was_wrong_about_the_last_answer: str | None = None,
) -> str:
    """The question put to the model about one inspected repository."""
    correction = (
        ""
        if what_was_wrong_about_the_last_answer is None
        else (
            "\nYour last answer was wrong, and this is what was wrong with it:\n"
            f"{what_was_wrong_about_the_last_answer}\n"
        )
    )

    return (
        f"You are analysing the architecture of {repository.owner}/{repository.name}.\n"
        "Answer from the inspection below and from nothing else.\n"
        "\n"
        f"Name these fields for the report: "
        f"{', '.join(THE_FIELDS_THE_ANSWER_MAY_NAME)}. Then three sentences of judgement, naming "
        f"{', '.join(THE_JUDGEMENTS_THE_ANSWER_MAY_NAME)}.\n"
        f"{correction}"
        "\n"
        "A finding is something about the shape of this repository that a reader would not\n"
        "see by listing its files. A module is a part with a responsibility of its own. A\n"
        "dependency is something this repository needs in order to run or build. A boundary\n"
        "is a line you would not cross when changing something, and what it separates. A\n"
        "risk is a way the current shape makes a future change harder or wrong.\n"
        "\n"
        "Say something in at least one field. An answer that is empty in all five is a\n"
        "fault in this run rather than a finding about the repository, and it is refused.\n"
        "\n"
        "Name no field beyond these five. An answer carrying anything else is refused\n"
        "rather than trimmed, because a conclusion this system did not ask for is one no\n"
        "human was ever shown.\n"
        "\n"
        f"Inspection of {repository.owner}/{repository.name}:\n"
        f"{inspection}"
        + the_rule_about_naming_a_file()
    )


def analyze_the_architecture(
    clone: ClonedRepository, repository: Repository, model: BaseChatModel
) -> tuple[ArchitectureReport, ArchitectureReportAnswer]:
    """The architecture report for a repository this run cloned.

    Validated rather than cast, for the reason every node in this system validates: a
    provider that ignores the schema is a real case, and validating is not the same as
    trusting.

    The empty answer is repaired once rather than merely refused, because a model shown a
    whole repository and asked for its architecture has usually been asked for more than an
    inspection can support, and the refusal is what tells it to say less. A run that
    exhausts the budget raises the last refusal, which is the thing worth showing a person.

    **The inspection carries the file contents, and it did not until a real run refused this
    stage's own siblings for the opposite.** `an_inspection_of` was built for discovery, whose
    job is a repository's shape — its own note says source files are deliberately absent from
    it, and that is right for a summary. This stage is asked for boundaries and risks, which
    are facts about *what the code does*, and a gate refused a run for reasoning from a
    `Dockerfile` and a `package.json` alone. **The fix had been made for discovery and nobody
    checked the stages after it** — the recurring shape in this repository, and the third time
    in a row here. `tests/test_every_stage_reasoning_about_a_file_is_shown_it.py` now asks
    every stage that reads a repository, so this is a failure rather than a diff.
    """
    inspection = an_inspection_of_the_code(clone)
    what_was_wrong: str | None = None

    began_at = time.monotonic()
    asked_so_far = 0
    while may_this_run_keep_asking(asked_so_far, began_at):
        asked_so_far += 1
        asking = ask_a_model_for(model, ArchitectureReportAnswer)
        try:
            answer = ArchitectureReportAnswer.model_validate(
                asking.invoke(
                    the_prompt_to_analyze_the_architecture(
                        inspection, repository, what_was_wrong
                    )
                )
            )
            return ArchitectureReport(
                findings=answer.findings,
                modules=answer.modules,
                dependencies=answer.dependencies,
                boundaries=answer.boundaries,
                risks=answer.risks,
            ), answer
        except (EmptyArchitectureReportError, ValidationError) as refused:
            what_was_wrong = how_a_model_is_told_what_was_wrong(refused)
            last = refused

    raise last
def the_architecture_analyst_using_the_configured_model() -> Callable[
    [ClonedRepository, Repository], tuple[ArchitectureReport, ArchitectureReportAnswer]
]:
    """The real `aisdlc-arch-analyze`: the model the environment names, asked about a clone.

    A factory rather than a default argument on `the_lifecycle`, for discovery's reason: the
    graph should not know how a model is obtained — it is handed a function, and this is the
    one that asks the environment. A test hands it a different function and never reads a key.

    **The model is built inside the call rather than at import time**, so the environment is
    read when the node runs. A factory that read it at import would freeze one deployment's
    model name into a process, and a resumed run would keep answering with the model that was
    configured when it started rather than the one configured now.

    `aisdlc-arch-analyze` describes how the code is shaped, and this is the only place
    that decision becomes a model call.
    """

    def analysing(
        clone: ClonedRepository, repository: Repository,
    ) -> tuple[ArchitectureReport, ArchitectureReportAnswer]:
        return analyze_the_architecture(
            clone, repository, a_model_for(a_configuration_from_the_environment())
        )

    return analysing
