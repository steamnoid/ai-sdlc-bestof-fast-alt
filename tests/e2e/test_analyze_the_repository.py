"""The product analyst, against a real model and a real repository.

Same chain as discovery and one link different: a real public repository is cloned with
real `git`, and a real model is handed the clone, the repository and **the request a person
typed**. The request is the third input and it is the reason this agent is worth its own
file — §10 gives it `analyze requirements`, and a requirements set that is not about the
request is a plausible set of requirements about the wrong thing.

**Nothing here asserts content.** Real output varies per run, and a test that pinned the
requirements a model chose would fail every time the model was different without ever finding
a defect. What is asserted is the contract: the answer validated into the artifact, the field
the proposal cannot be empty without is filled, and nothing came back as a placeholder.

**The groundedness assertion discovery has is deliberately absent, and the absence is the
finding rather than an oversight.** `Requirements` has three collections and the glossary
names no evidence among them, so a requirement cannot cite a file and this tier has no way to
check that a requirement is about anything that exists. A requirement about a file that is
not in the repository is the same failure `CitedFileNotFoundError` exists for, and it is
unmeasured here because the artifact has no field to measure it in. **That is a decision
recorded in the glossary, and the cycle that reverses it starts by changing the glossary.**

**An empty `ambiguities` is a pass and not a failure.** A repository with nothing ambiguous
about it has nothing to say there, and the model is not to invent a question to fill a list.
A test demanding three filled fields would be demanding the guess the artifact's own
validator refuses.

**What the first real run found here, and what this file therefore does not claim.** A real
model's `ambiguities` were the strongest output in this pipeline so far — they named a
runtime dependency that is not a declared dependency, and an MCP surface with no script that
starts it. The `requirements` came back mixed: some of them are proposals and several are
restatements of what the repository already does. **A restatement is not a proposal, and
nothing in this tier can tell them apart** — deciding whether a sentence proposes something is
a judgement about meaning, and a second model asked to make it would be a model grading a
model. So this file asserts only what is mechanical, and the distinction belongs to an eval
dataset, which is where reasoning quality lives.
"""

from __future__ import annotations

import pytest

from aisdlc.agents.analyze_the_repository import analyze_the_repository
from aisdlc.agents.requirements import Requirements
from aisdlc.agents.requirements_answer import AnAmbiguity, RequirementsAnswer
from aisdlc.domain.commissioned_request import CommissionedRequest
from aisdlc.domain.repository import Repository
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository

pytestmark = pytest.mark.e2e

MUST_BE_FILLED = ("requirements",)
JUDGEMENTS_THE_ANSWER_MAKES = ("what_it_found", "what_it_could_not_settle")


@pytest.fixture(scope="module")
def a_real_proposal(
    the_repository: Repository,
    the_cloned_repository: ClonedRepository,
    a_request: CommissionedRequest,
    the_model_for,
    request,
) -> tuple[Requirements, RequirementsAnswer]:
    """One real analysis, shared by every assertion about it, for the reasons discovery's is.

    **The request comes from the deployment rather than from this file**, because a request
    written into a test is a request about a repository this repository names. A deployment
    with no `E2E_TASK` gets a skip that says which setting would have given it one.
    """
    return analyze_the_repository(
        the_cloned_repository, the_repository, a_request, the_model_for(request.param)
    )


@pytest.mark.parametrize("a_real_proposal", list(LlmProvider), indirect=True)
def test_a_real_model_answered_with_something_a_person_could_act_on(
    a_real_proposal: tuple[Requirements, RequirementsAnswer], the_placeholders: frozenset[str]
) -> None:
    """The artifact is the artifact type, and the fields a gate presents are filled.

    **`requirements` and not `acceptance_criteria`**, because the node's own refusal is on an
    empty proposal: a product analyst who said nothing is a fault in the run rather than a
    finding about the repository, and it is repaired once before it is raised. A test demanding
    both fields filled would be demanding a guess about how this repository is built.
    """
    the_requirements, the_answer = a_real_proposal

    assert isinstance(the_requirements, Requirements), (
        f"the stage answered with {type(the_requirements).__name__} rather than the artifact a "
        "gate presents"
    )
    assert isinstance(the_answer, RequirementsAnswer), (
        "the judgement beside the artifact is not the answer type, so the note a person reads "
        "on the card is not the one the model reached"
    )

    for field in MUST_BE_FILLED:
        said = getattr(the_requirements, field)
        assert said, (
            f"the analyst was asked what this repository should become and {field} is empty. "
            "That artifact is what the next gate presents, so an empty one is a gate a person "
            "is asked to rule on with nothing in it"
        )
        for one_of_them in said:
            assert str(one_of_them).strip().lower() not in the_placeholders, (
                f"{one_of_them!r} in {field} is placeholder text, which means the model returned "
                "a shape rather than a proposal"
            )

    for judgement in JUDGEMENTS_THE_ANSWER_MAKES:
        assert getattr(the_answer.judged, judgement).strip(), (
            f"the analyst left {judgement} empty. It is where an analyst's doubt about the work "
            "as a whole goes, and it used to end runs; an empty one reads as a doubt nobody had"
        )


@pytest.mark.parametrize("a_real_proposal", list(LlmProvider), indirect=True)
def test_every_ambiguity_names_who_can_answer_it(
    a_real_proposal: tuple[Requirements, RequirementsAnswer], the_placeholders: frozenset[str]
) -> None:
    """Each ambiguity is a question and an attribution, or it is not one.

    **The attribution is the whole field, and it is why this is asserted rather than counted.**
    An ambiguity that does not say who can settle it cannot be routed: the planner renders it
    into a question for a person, and an unattributed one reads to a person at a gate as a
    doubt the analyst had rather than a decision only they can make. `AnAmbiguity` validates
    both halves, so a reach of this assertion means the model named the question and the
    attribution separately — which is the shape the type exists to hold.
    """
    the_requirements, _ = a_real_proposal

    for an_ambiguity in the_requirements.ambiguities:
        assert isinstance(an_ambiguity, AnAmbiguity), (
            f"an ambiguity arrived as {type(an_ambiguity).__name__} rather than the type that "
            "carries a question and who can answer it, so nothing downstream can route it"
        )
        assert an_ambiguity.what_is_undetermined.strip(), (
            "an ambiguity arrived with no question in it, which is a shape rather than a doubt"
        )
        assert an_ambiguity.who_can_answer_it is not None, (
            "an ambiguity arrived with nobody able to answer it, so the planner cannot tell a "
            "question for a person from a question the implementer settles by opening a file"
        )
        assert an_ambiguity.what_is_undetermined.strip().lower() not in the_placeholders, (
            f"{an_ambiguity.what_is_undetermined!r} is placeholder text, which means the model "
            "returned a shape rather than a question"
        )


@pytest.mark.parametrize("a_real_proposal", list(LlmProvider), indirect=True)
def test_the_requirements_carry_a_verdict_and_not_a_refusal(
    a_real_proposal: tuple[Requirements, RequirementsAnswer],
) -> None:
    """A real analyst, asked about a real repository, reached a verdict.

    **A claim about the stage and not about the model.** Three changes had this analyst refuse
    a run outright on a judgement about whether a question blocked the work, and it refused a
    request naming its own test file because *the inspection does not show what `.gitignore`
    covers* — a true sentence and not a reason, because the implementer opens the file. A run
    that refuses plannable work delivers nothing while every gate passes.

    So the refusal is gone, replaced by the gate this system already had: an ambiguity is
    rendered into the planner's question and the person ruling on the plan reads it there. This
    assertion is what says the replacement produced a proposal rather than a silence — and a
    stage that came back with an empty artifact would fail the assertion above rather than
    this one, which is why this claims something different: that the model was *asked* and
    answered, rather than that it was given a chance to refuse.
    """
    _, the_answer = a_real_proposal

    assert the_answer.judged.what_it_found.strip(), (
        "the analyst reached no verdict about a repository it was shown the whole of. This is "
        "the only stage handed the clone and not another agent's conclusion, so an empty "
        "verdict here is a stage that ran and saw nothing"
    )
