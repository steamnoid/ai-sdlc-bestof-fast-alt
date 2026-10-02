"""The QA analyst as a node: ask the model about the requirements, then build the artifact.

Discovery reads a repository, the product analyst reads a repository, and the QA analyst reads
**the requirements** — §10 gives it `analyze requirements` and the glossary has it converting
`Requirements` into a `QaPlan`. So the input here is an approved artifact rather than a clone,
and the prompt inlines the requirements for the reason every prompt in this system inlines its
subject: the model has no other way to see them.

The correction loop is the shared budget, for the fourth time. Discovery corrects a cited file
that is not in the clone, the planner corrects a path that is not in the clone, the product
analyst corrects an answer that said nothing, and this node corrects an answer that said
nothing. The question behind all four is one question: *may this system go on asking a model
for something it already had?* One number answers it, and a number written per agent would be
four numbers drifting into disagreeing about when to give up.

**No clone is read, and nothing in this cycle asks for one.** §10 also says the QA analyst
identifies missing test coverage, which does need the repository — and that is exactly the kind
of gap a real run is for. The artifact's four collections carry no inventory of existing tests,
so the signature carries no clone; if a real model plans tests for code it has not seen, the
fix is a clone and a test demanding it, not a parameter added on suspicion.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from aisdlc.agents.how_to_name_a_file import the_rule_about_naming_a_file
from aisdlc.agents.qa_plan import EmptyQaPlanError, QaPlan
from aisdlc.agents.qa_plan_answer import QaPlanAnswer
from aisdlc.agents.requirements import Requirements
from aisdlc.llm.asking_a_model_for import ask_a_model_for
from aisdlc.llm.correction_budget import (
    how_a_model_is_told_what_was_wrong,
    may_this_run_keep_asking,
)
from aisdlc.llm.llm_configuration import a_configuration_from_the_environment
from aisdlc.llm.model_factory import a_model_for

THE_FIELDS_THE_ANSWER_MAY_NAME = (
    "test_strategy",
    "scenarios",
    "edge_cases",
    "regression_risks",
)

# **The three judgements, asked in the same question as the scenarios.** One call and one
# answer, so there is no second model call to pay for and no way for a judgement to be written
# about a plan that is not the one beside it. The middle one is the one worth having for this
# agent in particular: a QA analyst is the only one reasoning about what would count as proof,
# so its doubt is the only one that can say *this would be tested, and it would pass anyway*.
THE_JUDGEMENTS_THE_ANSWER_MAY_NAME = (
    "what_it_found",
    "what_it_could_not_settle",
    "what_it_expects_next",
)


def the_prompt_to_analyze_requirements(
    requirements: Requirements,
    what_was_wrong_about_the_last_answer: str | None = None,
) -> str:
    """The question put to the model about one set of approved requirements.

    The requirements are inlined whole, ambiguities included, and that is deliberate: an
    ambiguity the product analyst admitted is an invitation to plan a test for the case it
    leaves open. A prompt showing only the requirements would show the model a cleaner problem
    than the one a person actually approved.
    """
    correction = (
        ""
        if what_was_wrong_about_the_last_answer is None
        else (
            "\nYour last answer was wrong, and this is what was wrong with it:\n"
            f"{what_was_wrong_about_the_last_answer}\n"
        )
    )

    return (
        "You are analysing approved requirements and deciding how they should be tested.\n"
        "Answer from the requirements below and from nothing else.\n"
        "\n"
        f"Name these fields for the plan: "
        f"{', '.join(THE_FIELDS_THE_ANSWER_MAY_NAME)}. Then three sentences of judgement, naming "
        f"{', '.join(THE_JUDGEMENTS_THE_ANSWER_MAY_NAME)}.\n"
        f"{correction}"
        "\n"
        "A scenario is one concrete situation the software is in and what it should do,\n"
        "not a restatement of a requirement. An edge case is a situation the requirements\n"
        "leave open. A regression risk is a way the change could break something that\n"
        "worked before.\n"
        "\n"
        "Say something in at least one field. An answer that is empty in all four is a\n"
        "fault in this run rather than a finding about the requirements, and it is refused.\n"
        "\n"
        "Name no field beyond these four. An answer carrying anything else is refused\n"
        "rather than trimmed, because a conclusion this system did not ask for is one no\n"
        "human was ever shown.\n"
        "\n"
        "You have not been shown this repository. You were handed a decision a person\n"
        "approved, and this stage never reads the code — so anything you say about a file\n"
        "by name is a guess, and a person at a gate cannot tell a guess from a reading.\n"
        "Name no file. Not one, not as an example, not as a placeholder.\n"
        "\n"
        "You do not need a name to be specific. Say \"the file the requirement names\",\n"
        "\"the root of the repository\", \"whatever the first stage cited\" — a scenario\n"
        "written that way holds for every repository, and one written with a name holds for\n"
        "exactly the one you have not seen.\n"
        "\n"
        "The approved requirements:\n"
        f"{requirements.model_dump_json(indent=2)}"
        + the_rule_about_naming_a_file()
    )


def analyze_the_requirements(
    requirements: Requirements, model: BaseChatModel
) -> tuple[QaPlan, QaPlanAnswer]:
    """The QA plan for one set of approved requirements, and the analyst's judgement of it.

    **Two values rather than one, and the note is not in the plan.** The plan is what a
    person approves and has exactly the four collections the glossary gives it; the three
    sentences are what a person and a repair supervisor read afterwards.

    Validated rather than cast, for the reason every node in this system validates: a provider
    that ignores the schema is a real case, and validating is not the same as trusting.

    The empty answer is repaired once rather than merely refused, because a model shown a set
    of requirements and asked for a strategy has usually been asked for more than it could
    summarise, and the refusal is what tells it to say less. A run that exhausts the budget
    raises the last refusal, which is the thing worth showing a person.
    """
    what_was_wrong: str | None = None

    began_at = time.monotonic()
    asked_so_far = 0
    while may_this_run_keep_asking(asked_so_far, began_at):
        asked_so_far += 1
        asking = ask_a_model_for(model, QaPlanAnswer)
        try:
            answer = QaPlanAnswer.model_validate(
                asking.invoke(the_prompt_to_analyze_requirements(requirements, what_was_wrong))
            )
            return QaPlan(
                test_strategy=answer.test_strategy,
                scenarios=answer.scenarios,
                edge_cases=answer.edge_cases,
                regression_risks=answer.regression_risks,
            ), answer
        except (EmptyQaPlanError, ValidationError) as refused:
            what_was_wrong = how_a_model_is_told_what_was_wrong(refused)
            last = refused

    raise last
def the_qa_analyst_using_the_configured_model() -> Callable[
    [Requirements], tuple[QaPlan, QaPlanAnswer]
]:
    """The real `aisdlc-qa-analyze`: the model the environment names, asked about requirements.

    A factory rather than a default argument on `the_lifecycle`, for discovery's reason: the
    graph should not know how a model is obtained — it is handed a function, and this is the
    one that asks the environment. A test hands it a different function and never reads a key.

    **The model is built inside the call rather than at import time**, so the environment is
    read when the node runs. A factory that read it at import would freeze one deployment's
    model name into a process, and a resumed run would keep answering with the model that was
    configured when it started rather than the one configured now.

    `aisdlc-qa-analyze` plans how they should be tested, and this is the only place that
    decision becomes a model call.
    """

    def analysing(
        requirements: Requirements,
    ) -> tuple[QaPlan, QaPlanAnswer]:
        return analyze_the_requirements(
            requirements, a_model_for(a_configuration_from_the_environment())
        )

    return analysing
