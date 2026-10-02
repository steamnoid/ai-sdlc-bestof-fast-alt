"""The product analyst as a node: ask the model, then build the artifact the gate presents.

The order is discovery's, and for the same reason. The model answers first, in a shape that
cannot carry anything the glossary did not name, and only then does the system build the
artifact. A single type would have to make the artifact's fields optional to accommodate a
model that might fill them differently, and an artifact whose contents may be absent is one
nobody can rely on when they are asked to approve it.

The correction loop is the shared budget rather than a second number. Discovery corrects a
cited file that is not in the clone and the planner corrects a path that is not in the clone;
this node corrects an answer that said nothing, which is a third failure and the same
question — *may this system go on asking a model for something it already had?* One number
answers it for all three, and a number written twice drifts into disagreeing about when to
give up.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from aisdlc.agents.how_to_name_a_file import the_rule_about_naming_a_file
from aisdlc.agents.requirements import EmptyRequirementsError, Requirements
from aisdlc.agents.requirements_answer import RequirementsAnswer
from aisdlc.domain.commissioned_request import CommissionedRequest
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
    "requirements",
    "acceptance_criteria",
    "ambiguities",
)

# **The three judgements, asked in the same question as the requirements.** One call and one
# answer, so there is no second model call to pay for and no way for a judgement to be written
# about requirements that are not the ones beside it. The middle one is the one worth having: it
# is where an analyst's doubt about the *work as a whole* goes, which is a different thing from
# an `AnAmbiguity` and a place a doubt used to end a run.
THE_JUDGEMENTS_THE_ANSWER_MAY_NAME = (
    "what_it_found",
    "what_it_could_not_settle",
    "what_it_expects_next",
)


def the_prompt_to_analyze_a_repository(
    inspection: str,
    repository: Repository,
    request: CommissionedRequest | None,
    what_was_wrong_about_the_last_answer: str | None = None,
) -> str:
    """The question put to the model about one inspected repository.

    The inspection is inlined rather than referenced because the model has no other way to
    see the repository: this node is given what was inspected, and a question that omitted it
    would leave the model proposing improvements to whatever it could infer from a name.

    Nothing depends on the model obeying the paragraph about the three fields, which is the
    point of asking for a closed shape instead: `RequirementsAnswer` has no field a fourth
    conclusion could arrive in, so the sentence is there to save the model from generating
    work that will be refused.
    """
    correction = (
        ""
        if what_was_wrong_about_the_last_answer is None
        else (
            "\nYour last answer was wrong, and this is what was wrong with it:\n"
            f"{what_was_wrong_about_the_last_answer}\n"
        )
    )

    asked_for = _how_the_request_reads(request)
    return (
        f"You are analysing the public repository {repository.owner}/{repository.name}.\n"
        f"{asked_for}"
        "Answer from the request and the inspection below, and from nothing else.\n"
        "\n"
        f"Name these fields for the requirements: "
        f"{', '.join(THE_FIELDS_THE_ANSWER_MAY_NAME)}. Then three sentences of judgement, naming "
        f"{', '.join(THE_JUDGEMENTS_THE_ANSWER_MAY_NAME)}.\n"
        f"{correction}"
        "\n"
        "A requirement says what should be true of the project and nothing about how to\n"
        "build it. An acceptance criterion says how somebody would tell it is true, and\n"
        "must be checkable by observing the project rather than by reading this answer.\n"
        "An ambiguity is a question you cannot answer from the inspection, asked out loud\n"
        "rather than guessed at.\n"
        "\n"
        "Say something in at least one field. An answer that is empty in all three is a\n"
        "fault in this run rather than a finding about the repository, and it is refused.\n"
        "\n"
        "Name no field beyond these three. An answer carrying anything else is refused\n"
        "rather than trimmed, because a conclusion this system did not ask for is one no\n"
        "human was ever shown.\n"
        "\n"
        f"Inspection of {repository.owner}/{repository.name}:\n"
        f"{inspection}"
        + the_rule_about_naming_a_file()
    )


def _how_the_request_reads(request: CommissionedRequest | None) -> str:
    """The request, worded so the model reads it as the question rather than as context.

    **Placed before the inspection and labelled as the thing being asked**, because a model
    shown a repository and a sentence in either order answers the repository. The empty case
    is stated rather than hidden: a work item with no request on it is one this stage cannot
    reason about, and saying so is better than letting the analyst describe a project and
    present the result as requirements for work nobody asked for.
    """
    if request is None:
        return (
            "No request was recorded for this work, so describe what the project is and\n"
            "what it could reasonably be asked for.\n"
            "\n"
        )

    if not request.body:
        return f"The request, in full:\n{request.title}\n\n"

    return (
        f"The request, in full:\n{request.title}\n\n"
        f"{request.body}\n\n"
    )


def analyze_the_repository(
    clone: ClonedRepository,
    repository: Repository,
    request: CommissionedRequest | None,
    model: BaseChatModel,
) -> tuple[Requirements, RequirementsAnswer]:
    """The requirements this run proposes, and the judgement the analyst reached about the work.

    **Two values rather than one, and the note is not among the requirements.** The artefact is
    what a person approves and has exactly the fields the glossary gives it; the judgement is
    what a person and a repair supervisor read afterwards, and putting it in the artefact would
    put three sentences no human ruled on inside a document they are asked to rule on. The
    artefact is built from the answer's three collections and the judgement is carried beside it.

    The requirements are for a repository this run has already cloned.

    The answer is validated rather than cast, because `with_structured_output` is typed to
    hand back either the class or plain data and a provider that ignores the schema is a
    real case rather than a theoretical one. Validating is not trusting: a field of the wrong
    shape is still refused, here and deterministically.

    The empty answer is *repaired* rather than merely refused, because a model that says
    nothing has usually been shown something too large to summarise and not refused the
    chance to say less. One correction is spent on telling it exactly that, and the run
    raises the refusal rather than returning a proposal nobody can approve.

    **The inspection carries the file contents, and a run's policy refused this stage for the
    opposite.** A real run produced requirements stating what `run_command.py` catches and
    where the confinement is enforced, about a file the artifact itself recorded as never
    having been opened — the policy compared the artifact against its own evidence list and
    stopped the run. `an_inspection_of` was built for discovery, whose job is a repository's
    shape, and the fix had been made for discovery without anyone checking the stages after
    it. `tests/test_every_stage_reasoning_about_a_file_is_shown_it.py` now asks every stage
    that reads a repository.
    """
    inspection = an_inspection_of_the_code(clone)
    what_was_wrong: str | None = None

    began_at = time.monotonic()
    asked_so_far = 0
    while may_this_run_keep_asking(asked_so_far, began_at):
        asked_so_far += 1
        asking = ask_a_model_for(model, RequirementsAnswer)
        try:
            answer = RequirementsAnswer.model_validate(
                asking.invoke(
                    the_prompt_to_analyze_a_repository(
                        inspection, repository, request, what_was_wrong
                    )
                )
            )
            return Requirements(
                requirements=answer.requirements,
                acceptance_criteria=answer.acceptance_criteria,
                ambiguities=answer.ambiguities,
            ), answer
        except (EmptyRequirementsError, ValidationError) as refused:
            what_was_wrong = how_a_model_is_told_what_was_wrong(refused)
            last = refused

    raise last


def the_product_analyst_using_the_configured_model() -> Callable[
    [ClonedRepository, Repository, CommissionedRequest | None],
    tuple[Requirements, RequirementsAnswer],
]:
    """The real `aisdlc-po-analyze`: the model the environment names, asked about a clone.

    A factory rather than a default argument on `the_lifecycle`, for discovery's reason: the
    graph should not know how a model is obtained — it is handed a function, and this is the
    one that asks the environment. A test hands it a different function and never reads a key.

    **The model is built inside the call rather than at import time**, so the environment is
    read when the node runs. A factory that read it at import would freeze one deployment's
    model name into a process, and a resumed run would keep answering with the model that was
    configured when it started rather than the one configured now.

    `aisdlc-po-analyze` proposes what should be built, and this is the only place that
    decision becomes a model call.
    """

    def analysing(
        clone: ClonedRepository,
        repository: Repository,
        request: CommissionedRequest | None,
    ) -> tuple[Requirements, RequirementsAnswer]:
        return analyze_the_repository(
            clone,
            repository,
            request,
            a_model_for(a_configuration_from_the_environment()),
        )

    return analysing
