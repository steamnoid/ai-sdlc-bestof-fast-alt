"""The QA analyst, against a real model and real approved requirements.

**This is the only stage in the pipeline that is handed an artifact rather than a
repository**, and that fact is the whole reason it needs proving on its own. §10 gives it
`analyze requirements` and the glossary has it converting `Requirements` into a `QaPlan`, so
its input is a document a person already approved. Everything else about the tier is the
chain as in the two files beside it: a real model obtained through the real factory, and
nothing asserted about content.

**The requirements handed in are the ones production gives this stage, built here rather
than produced by the real analyst.** Chaining two real agents in a file whose job is to
isolate one would make this a composition test in the tier that exists to prevent that. So
the input is a stand-in, and it is named as one.

**And the assertion that matters most is about what the stage was not shown.** This stage
never reads the code, and its own prompt says so and tells the model to name no file. The
test holds that: a scenario written about a file this stage was never shown is a guess, and
a person at a gate cannot tell a guess from a reading. **The prompt asking for that is not
what is asserted** — a rule that lives only in a prompt is not a rule, and the sibling
tier's own note about the discovery evidence check is the shape of the mistake. What is
asserted is the output, on a real model that was free to ignore the instruction.

**A scenario is not a restatement of a requirement, and nothing mechanical can tell.** A
real model produced scenarios that restated the requirements they came from, which is a real
failure and a judgement about meaning rather than a shape. So the assertions are the contract
— the artifact, the four collections, no placeholders — and the quality of a scenario is an
eval's business.
"""

from __future__ import annotations

import re

import pytest

from aisdlc.agents.a_value_that_says_something import a_value_that_says_something
from aisdlc.agents.analyze_the_requirements import analyze_the_requirements
from aisdlc.agents.qa_plan import QaPlan
from aisdlc.agents.qa_plan_answer import QaPlanAnswer
from aisdlc.agents.requirements import Requirements
from aisdlc.llm.model_provider import LlmProvider

pytestmark = pytest.mark.e2e

MUST_SAY_SOMETHING = ("test_strategy", "scenarios")
JUDGEMENTS_THE_ANSWER_MAKES = ("what_it_found", "what_it_could_not_settle")

# A path as a model writes one inside a sentence: a slash-separated word ending in something
# that looks like a source file's extension. Matched loosely on purpose — the question is
# whether the stage *named* a file, and a path with no extension is a guess as much as one
# with a wrong suffix.
A_PATH_INSIDE_A_SENTENCE = re.compile(r"[`\"']?([\w./-]+\.[A-Za-z]{1,5})[`\"']?")

# The requirements production hands this stage for the run this repository's real tier makes.
# Stated here rather than produced by the analyst, and the reason is the tier's own: a file
# that isolates one agent must not compose two.
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
            "what_is_undetermined": "Whether the version to name is the one in CI or the newest "
            "released one, and only a person who maintains this repository can say.",
            "who_can_answer_it": "a person",
        }
    ],
)


@pytest.fixture(scope="module")
def a_real_plan(the_model_for, request) -> tuple[QaPlan, QaPlanAnswer]:
    """One real QA plan, shared by every assertion about it."""
    return analyze_the_requirements(THE_APPROVED_REQUIREMENTS, the_model_for(request.param))


@pytest.mark.parametrize("a_real_plan", list(LlmProvider), indirect=True)
def test_a_real_model_plans_something_a_person_could_approve(
    a_real_plan: tuple[QaPlan, QaPlanAnswer], the_placeholders: frozenset[str]
) -> None:
    """The artifact is the artifact type, and it says something a gate can present.

    **`test_strategy` and `scenarios` and not all four collections.** The node's own refusal is
    on an answer empty in all four, so all four being empty cannot reach here — but three
    filled and one empty is a real answer, and a test demanding four would be demanding a
    guess about what a repository worth testing looks like.
    """
    the_plan, the_answer = a_real_plan

    assert isinstance(the_plan, QaPlan), (
        f"the stage answered with {type(the_plan).__name__} rather than the artifact a gate "
        "presents"
    )
    assert isinstance(the_answer, QaPlanAnswer), (
        "the judgement beside the artifact is not the answer type, so the note a person reads "
        "on the card is not the one the model reached"
    )

    for field in MUST_SAY_SOMETHING:
        said = getattr(the_plan, field)
        assert said, (
            f"the QA analyst was asked how approved requirements should be tested and {field} "
            "is empty. That artifact is what the next gate presents, so an empty one is a gate "
            "a person is asked to rule on with nothing in it"
        )

    # **A field is either absent or says something, and the third state is the finding.** A
    # real model returned `test_strategy` as a single space: not absent, and not a strategy.
    # The artifact's own emptiness rule strips whitespace and so says the field said nothing —
    # and the rule that *checks* the plan asks whether any field says something, so a plan
    # whose scenarios were real passed with a strategy that was a space. A person at a gate
    # reading four fields cannot tell that one is blank, because a blank field and a field
    # holding `" "` are the same characters on a card.
    for field in QaPlan.model_fields:
        said = getattr(the_plan, field)
        assert a_value_that_says_something(said) or str(said).strip() == "", (
            f"{field} is {said!r}. That is neither an answer nor an absence: a person reading "
            "this plan cannot tell a field holding whitespace from a field holding a strategy, "
            "so a plan that says nothing in a field has to say nothing in the way this "
            "artifact's own emptiness rule already defines it"
        )
        for one_of_them in said if isinstance(said, list) else [said]:
            assert str(one_of_them).strip().lower() not in the_placeholders, (
                f"{one_of_them!r} in {field} is placeholder text, which means the model returned "
                "a shape rather than a plan"
            )

    for judgement in JUDGEMENTS_THE_ANSWER_MAKES:
        assert getattr(the_answer.judged, judgement).strip(), (
            f"the QA analyst left {judgement} empty. It is the only agent reasoning about what "
            "would count as proof, so its doubt is the only one that can say *this would be "
            "tested and it would pass anyway* — and an empty one reads as a doubt nobody had"
        )


@pytest.mark.parametrize("a_real_plan", list(LlmProvider), indirect=True)
def test_a_plan_made_without_the_repository_names_no_file_in_it(
    a_real_plan: tuple[QaPlan, QaPlanAnswer],
) -> None:
    """A stage never shown a repository may not write about one by name.

    **The one assertion in this tier that is about a prompt instruction, checked on the
    output.** The prompt tells the model it was not shown this repository and that anything it
    says about a file by name is a guess. A rule that lives only in a prompt is not a rule, so
    the output is what is asserted: the model was free to ignore the instruction and this is
    what the result looks like when it does not.

    **A scenario written that way holds for every repository and one written with a name holds
    for exactly the one nobody here has seen.** That is the whole argument, and it is why the
    path is looked for rather than the wording. Discovery's report is checked the other way
    round — every file it names must exist in the clone — and a QA plan has no such field and
    no clone, so the honest check available is that it names none.

    **Both readings of a dot are excluded**, because `.env` and `.gitignore` are files
    repositories have and are not a statement about this one. A path needs a slash before its
    name to count as a file in a repository, so `web-app/src/lib/auth.js` is a claim and
    `auth.js` is a noun.
    """
    the_plan, _ = a_real_plan

    every_sentence_the_plan_says: list[str] = [str(the_plan.test_strategy)]
    for a_collection in (the_plan.scenarios, the_plan.edge_cases, the_plan.regression_risks):
        every_sentence_the_plan_says.extend(str(one_of_them) for one_of_them in a_collection)

    named_files: list[str] = []
    for a_sentence in every_sentence_the_plan_says:
        for a_candidate in A_PATH_INSIDE_A_SENTENCE.findall(a_sentence):
            if "/" in a_candidate and not a_candidate.startswith(("http", "/api", "node_modules")):
                named_files.append(a_candidate)

    assert not named_files, (
        f"the QA plan names {sorted(set(named_files))}, and this stage was never shown this "
        "repository. It was handed a document a person approved, so a scenario about a file by "
        "name is a guess — and a person at a gate reading a QA plan cannot tell a guess from a "
        "reading. The prompt says so and that is not what makes it true."
    )


@pytest.mark.parametrize("a_real_plan", list(LlmProvider), indirect=True)
def test_the_ambiguity_the_analyst_admitted_reached_the_qa_analyst(
    a_real_plan: tuple[QaPlan, QaPlanAnswer],
) -> None:
    """A QA plan that says nothing about the open question is a plan about a cleaner problem.

    **The requirements go in whole, ambiguities included, and this is why that matters.** A
    product analyst admitted a question it could not answer, a person approved the
    requirements anyway, and the QA analyst is the next stage to reason about what would count
    as proof. An ambiguity the plan never mentions is an ambiguity nobody was ever shown, and
    the gate that would have caught it is looking at a document that does not have it.

    **Not asserted as: the model must use these words.** A QA plan may answer the ambiguity,
    carry it into an edge case, or note it in its judgement, and all three are honest. What is
    asserted is that the plan is not silent about a question its own input raised, and the
    way that is measured is whether the plan says anything at all about *which* case is
    undetermined — the words themselves are the model's to choose.
    """
    the_plan, the_answer = a_real_plan

    what_the_plan_says_about_the_open_question = " ".join(
        [
            str(the_plan.test_strategy),
            " ".join(str(one) for one in the_plan.scenarios),
            " ".join(str(one) for one in the_plan.edge_cases),
            the_answer.judged.what_it_could_not_settle,
        ]
    ).lower()

    the_open_question_is_about = ["version", "node"]
    named_at_all = any(
        word in what_the_plan_says_about_the_open_question for word in the_open_question_is_about
    )

    assert named_at_all, (
        "the requirements this plan was made from carry an admitted ambiguity about which Node "
        "version the README should name, and the plan says nothing about a version anywhere — "
        "not in a scenario, not in an edge case, not in what it could not settle. A QA plan "
        "written from requirements with the open question removed is a plan about a cleaner "
        "problem than the one a person approved, and the gate presents it as though it were "
        "the same one."
    )
