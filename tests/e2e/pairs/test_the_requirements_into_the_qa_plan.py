"""The product analyst's requirements, handed to the QA analyst — the one true seam in this
pipeline.

**Most neighbouring pairs in a run hand nothing over, and that is the finding this directory is
built to measure.** Read the signatures and the shape is plain: `discover_the_repository` gets a
clone, `analyze_the_repository` gets that same clone, `analyze_the_architecture` and
`inspect_for_security_risk` get that clone too, and `plan_the_change` gets *requirements* and
not the security report a person approved four gates earlier. **Four of the seven neighbouring
pairs share a substrate rather than an artifact.** The upstream stage's conclusion is not in the
next stage's input, so the next stage cannot be wrong *about* what the previous one concluded —
and it can be wrong about the same file from a different starting point, which is what a gate
reading both artifacts is for.

This file is the exception, and it is the one pair where the upstream answer is genuinely the
question: the QA analyst is handed approved `Requirements` and nothing else. So what is proved
here is the thing a whole run cannot show — that a **real** `Requirements` produced by a **real**
model is something a **real** QA analyst accepts, and that nothing about the handover is lost on
the way.

**And what is asserted about the handover is that the second stage was not shown the first
stage's *judgement*.** The product analyst returns a `(Requirements, RequirementsAnswer)` pair,
and the QA analyst's signature takes only the `Requirements`. The three sentences of judgement
the analyst reached are a thing a person and the repair supervisor read afterwards; putting them
in front of the next stage would be putting an opinion about the work in front of a stage
reasoning about how to test it, and the report the QA analyst produced would then be a reaction
rather than a plan.

The provider is a parameter rather than a constant, so proving a second one is a different run
and not a rewritten test. A provider the deployment is not configured for says so out loud.
"""

from __future__ import annotations

import pytest

from aisdlc.agents.analyze_the_repository import analyze_the_repository
from aisdlc.agents.analyze_the_requirements import (
    analyze_the_requirements,
    the_prompt_to_analyze_requirements,
)
from aisdlc.agents.requirements import Requirements
from aisdlc.agents.requirements_answer import RequirementsAnswer
from aisdlc.domain.commissioned_request import CommissionedRequest
from aisdlc.domain.repository import Repository
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository

pytestmark = pytest.mark.e2e

THE_JUDGEMENTS_EVERY_AGENT_MAKES = (
    "what_it_found",
    "what_it_could_not_settle",
    "what_it_expects_next",
)


@pytest.fixture(scope="module")
def a_real_handover(
    the_repository: Repository,
    the_cloned_repository: ClonedRepository,
    a_request: CommissionedRequest,
    the_model_for,
    request,
) -> tuple[Requirements, RequirementsAnswer, object]:
    """Both stages, on real models, with the first one's artifact going to the second.

    **Two real calls and one real artifact between them, which is what a pair is.** A pair that
    ran the first stage and then handed the second a stand-in would be two isolation tests
    wearing one name, and the handover would be the part left unmeasured.

    **The QA analyst is the second call and gets the first stage's real `Requirements`**, not
    the first stage's `RequirementsAnswer`. That is the production seam exactly, and the
    assertion below holds the boundary.
    """
    the_model = the_model_for(request.param)

    requirements, what_the_analyst_concluded = analyze_the_repository(
        the_cloned_repository, the_repository, a_request, the_model
    )
    qa_plan, what_the_qa_analyst_concluded = analyze_the_requirements(requirements, the_model)

    return requirements, what_the_analyst_concluded, (qa_plan, what_the_qa_analyst_concluded)


@pytest.mark.parametrize("a_real_handover", list(LlmProvider), indirect=True)
def test_a_real_requirements_is_something_a_real_qa_analyst_accepted(
    a_real_handover: tuple[Requirements, RequirementsAnswer, object],
) -> None:
    """The QA plan exists, so the upstream artifact was accepted rather than refused.

    **A reach of this assertion is the whole claim, and it is a claim about a shape rather than
    about content.** `analyze_the_requirements` raises on an answer empty in all four fields and
    repairs one empty answer before raising, so a `QaPlan` reaching here means a real model read
    a real `Requirements` and produced something. What is *not* claimed is that the plan is good
    — that is a judgement about meaning, and a second model asked to make it would be a model
    grading a model.
    """
    _, _, (the_qa_plan, what_the_qa_analyst_concluded) = a_real_handover

    assert the_qa_plan.test_strategy or the_qa_plan.scenarios, (
        "a real QA analyst was handed a real set of requirements and returned a plan empty in "
        "both fields a person reads. The handover was accepted, and what came back is not a "
        "plan — which is a different failure from a handover that was refused, and the second is "
        "the one this file is here to catch"
    )

    for a_judgement in THE_JUDGEMENTS_EVERY_AGENT_MAKES:
        assert getattr(what_the_qa_analyst_concluded.judged, a_judgement).strip(), (
            f"the QA analyst left {a_judgement} empty on a real handover. It is the only agent "
            "reasoning about what would count as proof, and an empty one reads as a doubt nobody "
            "had"
        )


@pytest.mark.parametrize("a_real_handover", list(LlmProvider), indirect=True)
def test_the_handover_carried_the_requirements_and_not_the_judgement_about_them(
    a_real_handover: tuple[Requirements, RequirementsAnswer, object],
) -> None:
    """The second stage's question carries the requirements and carries no judgement.

    **Asked of the prompt, because the prompt is the whole of what this stage was given.** The
    signature takes a `Requirements` and the caller in production passes exactly that; a future
    change that passed the `RequirementsAnswer` too would still typecheck, and a QA plan
    written in reaction to another model's opinion is a plan nobody approved. The question is
    what the model was shown, so the question is what has to be read.

    **Asserted on both halves rather than on the first.** A check that the requirements are in
    the prompt is satisfied by a prompt that carries the requirements *and* the analyst's three
    sentences, which is the case this excludes.
    """
    requirements, what_the_analyst_concluded, _ = a_real_handover

    what_the_second_stage_was_asked = the_prompt_to_analyze_requirements(requirements)

    assert any(
        a_requirement in what_the_second_stage_was_asked
        for a_requirement in requirements.requirements
    ), (
        "the QA analyst's question does not carry the requirements it was handed, so the "
        "handover did not happen and the plan is about whatever the model inferred"
    )

    for a_judgement in THE_JUDGEMENTS_EVERY_AGENT_MAKES:
        said = getattr(what_the_analyst_concluded.judged, a_judgement)
        assert said not in what_the_second_stage_was_asked, (
            f"the product analyst's {a_judgement} is in the QA analyst's question. That stage is "
            "asked how approved requirements should be tested, and a question carrying another "
            "model's opinion of the work makes the plan a reaction rather than a plan — and a "
            "gate cannot see the difference, because both arrive as a QaPlan"
        )


@pytest.mark.parametrize("a_real_handover", list(LlmProvider), indirect=True)
def test_every_ambiguity_the_analyst_left_open_reached_the_question(
    a_real_handover: tuple[Requirements, RequirementsAnswer, object],
) -> None:
    """An admitted ambiguity is in the second stage's question, and its attribution is too.

    **This is the part of a handover a whole run cannot check, and it is the part that decides
    whether the plan is about the work a person approved.** The product analyst's `ambiguities`
    are the questions it could not answer, marked with who can answer them, and a person
    approved the requirements *with those questions still open*. So a question that omits them
    is a question about a cleaner problem than the one that was approved — and the gate
    presenting the plan has no way to tell, because both plans look like plans.

    **The attribution is checked, not just the question.** An ambiguity arriving without the
    person who can settle it is a doubt a planner cannot route, and the whole reason the field
    carries one is that the question is rendered into the planner's own prompt marked where
    only a person can answer.
    """
    requirements, _, _ = a_real_handover

    if not requirements.ambiguities:
        pytest.skip(
            "this run's analyst left no ambiguity open, so there was nothing to hand over. That "
            "is an honest answer for a repository with nothing doubtful about it and the type's "
            "own rule says an invented question is a guess."
        )

    what_the_second_stage_was_asked = the_prompt_to_analyze_requirements(requirements)

    for an_ambiguity in requirements.ambiguities:
        assert an_ambiguity.what_is_undetermined in what_the_second_stage_was_asked, (
            f"this ambiguity is in the requirements and not in the QA analyst's question: "
            f"{an_ambiguity.what_is_undetermined!r}. A person approved these requirements with it "
            "open, so a plan made without it is a plan about a cleaner problem than the one "
            "that was approved — and the gate cannot see the difference"
        )
