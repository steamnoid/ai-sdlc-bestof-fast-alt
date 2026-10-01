"""The discovery report and the requirements, side by side, with nothing handed between them.

**This is a pair of stages that share a substrate rather than an artifact, and that is the whole
argument for having it in one file.** `discover_the_repository` is handed a clone,
`analyze_the_repository` is handed that same clone, and neither is handed the other's conclusion.
So a run's first real failure — the product analyst answering *what is this project* while the one
sentence describing what somebody actually asked for went straight past it to the planner — left
every artifact in between still carrying the shape of an artifact. **Two files that each proved
one agent would both have stayed green through exactly that**, because a stage reasoning from a
repository instead of from a request is not a failure the other stage's file can see.

**So what is proved here is the seam that is not there.** The analyst's own signature says it is
handed the clone and not the report, and the prompt that node builds is the whole of what the
model was shown — so the check is asked of the prompt, the same way
`test_the_requirements_into_the_qa_plan.py` asks it of a handover that *is* there. **A change that
started passing the report along would still typecheck**, and the requirements would become a
restatement of a summary of what the repository is rather than of what it lacks, and a gate
holding both cards has no way to tell those two apart.

**And a second claim, mechanical, and the one a gate could actually make.** Both artifacts came
out of one clone, so they are about the same repository and a person may hold them side by side;
what the filesystem can then answer is that the requirements are not sentences the report already
contains. **What cannot be answered is whether a requirement names work rather than describing
state**, and that is said in the test rather than approximated — a second model asked to make the
judgement would be a model grading a model, and §0.3 puts reasoning quality in `evals/`, not in a
pytest assertion.

**One clone for both stages, and that is not a shortcut.** Neither writes, so there is nothing to
keep apart; and a comparison between two artifacts is only meaningful when both were produced
from one checkout, which is the fact `test_the_plan_into_the_implementation.py` has to work for
with two.

The provider is a parameter rather than a constant, so proving a second one is a different run
and not a rewritten test. A provider the deployment is not configured for says so out loud.
"""

from __future__ import annotations

from typing import NamedTuple

import pytest

from aisdlc.agents.analyze_the_repository import (
    analyze_the_repository,
    the_prompt_to_analyze_a_repository,
)
from aisdlc.agents.discover_the_repository import discover_the_repository
from aisdlc.agents.discovery_answer import DiscoveryAnswer
from aisdlc.agents.discovery_report import DiscoveryReport
from aisdlc.agents.requirements import Requirements
from aisdlc.agents.requirements_answer import RequirementsAnswer
from aisdlc.domain.commissioned_request import CommissionedRequest
from aisdlc.domain.repository import Repository
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import an_inspection_of

pytestmark = pytest.mark.e2e

JUDGEMENTS_EVERY_AGENT_MAKES = (
    "what_it_found",
    "what_it_could_not_settle",
    "what_it_expects_next",
)

# **The prose of a discovery report, and not `evidence_files`.** A cited path is a file of the
# clone and the inspection shows that file, so a requirement may legitimately be about one of them
# — the run this tier makes asks for a change to the README, and the report quite reasonably cites
# the README. Including the citations here would make every honest answer look like a restatement.
THE_PROSE_A_DISCOVERY_REPORT_SAYS = (
    "languages",
    "frameworks",
    "build_system",
    "ci_system",
    "architecture_summary",
    "key_components",
    "suggested_changes",
)


def _as_one_line(said: str) -> str:
    """The same text with its layout and its capitalisation thrown away.

    **Comparing whole sentences rather than fragments, and that is why the layout goes first.** A
    requirement and a component name that differ only in a line break are the same claim, and a
    check that compared them as two strings would call that a difference and pass a restatement.
    """
    return " ".join(said.split()).casefold()


def _everything_the_report_prose_says(the_report: DiscoveryReport) -> str:
    """Every prose field of a report, as one body of text a requirement could be lifted out of."""
    said = [getattr(the_report, a_field) for a_field in THE_PROSE_A_DISCOVERY_REPORT_SAYS]
    return "\n".join(
        "\n".join(str(one) for one in a_value) if isinstance(a_value, list) else str(a_value)
        for a_value in said
    )


class WhatTheTwoStagesAnswered(NamedTuple):
    """Both artifacts and both judgements, which is what a pair has to hold to be compared.

    **The two judgements and not only the two artifacts.** Each stage is asked three questions
    about its own work and keeps them beside the document rather than among it, and here they are
    part of what has to be compared: an opinion one model reached is not something the next model
    was shown, and a pair that carried only the artifacts would not be able to say so.
    """

    the_report: DiscoveryReport
    what_discovery_concluded: DiscoveryAnswer
    the_requirements: Requirements
    what_the_analyst_concluded: RequirementsAnswer


@pytest.fixture(scope="module")
def what_the_two_stages_answered(
    the_repository: Repository,
    the_cloned_repository: ClonedRepository,
    a_request: CommissionedRequest,
    the_model_for,
    request,
) -> WhatTheTwoStagesAnswered:
    """Both stages, on real models, on one clone, with nothing passed from the first to the second.

    **Two real calls and no artifact between them, which is what this pair is.** A pair that ran
    discovery and then handed the analyst a stand-in for the report would measure a hand-over that
    production does not have, and would miss the one it does: the request, the clone, and nothing
    the first stage concluded. That is why the second call is given the clone and the request and
    no fourth argument — the production call, unchanged.

    **The read-only clone, and one of them rather than two.** Neither stage writes, so a second
    copy would buy nothing and would make the comparison below a comparison of two different
    checkouts. What it buys is the other half of the argument: both artifacts are claims about one
    repository, and a gate may hold them side by side.

    **The provider is `request.param` and the tests parametrise it indirectly**, so a run
    configured for one provider *skips* the others with the reason printed.
    """
    the_model = the_model_for(request.param)

    the_report, what_discovery_concluded = discover_the_repository(
        the_cloned_repository, the_repository, the_model
    )
    the_requirements, what_the_analyst_concluded = analyze_the_repository(
        the_cloned_repository, the_repository, a_request, the_model
    )

    return WhatTheTwoStagesAnswered(
        the_report=the_report,
        what_discovery_concluded=what_discovery_concluded,
        the_requirements=the_requirements,
        what_the_analyst_concluded=what_the_analyst_concluded,
    )


@pytest.mark.parametrize("what_the_two_stages_answered", list(LlmProvider), indirect=True)
def test_the_analyst_was_asked_about_the_request_and_not_about_the_report(
    what_the_two_stages_answered: WhatTheTwoStagesAnswered,
    the_repository: Repository,
    the_cloned_repository: ClonedRepository,
    a_request: CommissionedRequest,
) -> None:
    """The question the analyst was asked carries the request, and carries no part of the report.

    **Asked of the prompt, because the prompt is the whole of what this stage was given.** The
    signature takes a clone, a repository and a request, and the caller in production passes
    exactly those; a change that added the `DiscoveryReport` to that call would still typecheck,
    and the requirements would then be a reaction to another model's description of the project
    rather than an answer to the question a person asked. The inspection is rebuilt here by
    calling the same function the node calls, so this is the question as it was put and not a
    reconstruction of it.

    **Two lists and not one, and the reason they are not the same kind of claim.** A citation's
    *link* is derived by this system and exists nowhere in a checkout, so its presence in the
    prompt would mean the report had been handed over and nothing else could explain it. The
    summary, the suggestions and the three sentences are model prose, and a `suggested_changes`
    entry is short enough that a reader who trips this should read the quoted string first — a
    false positive here is visible in the failure message rather than silent.

    **The three lists are never all empty, and that is what keeps the check from passing for
    nothing.** `WhatAnAgentJudged` refuses a blank judgement, so the discovery agent's own three
    sentences are real text on every run whether or not the report filled a prose field. A report
    with no citation and no summary would still put three sentences through this loop, which is
    why there is no skip here where the sibling pair has one.
    """
    the_report = what_the_two_stages_answered.the_report
    what_discovery_concluded = what_the_two_stages_answered.what_discovery_concluded

    the_links_the_system_derived = [a_citation.link for a_citation in the_report.evidence_files]
    what_a_model_wrote = [
        *(text for text in [the_report.architecture_summary] if text.strip()),
        *the_report.suggested_changes,
        *(
            getattr(what_discovery_concluded.judged, a_judgement)
            for a_judgement in JUDGEMENTS_EVERY_AGENT_MAKES
        ),
    ]

    what_the_second_stage_was_asked = the_prompt_to_analyze_a_repository(
        an_inspection_of(the_cloned_repository), the_repository, a_request
    )

    assert a_request.title in what_the_second_stage_was_asked, (
        "the product analyst's question does not carry the request it was handed. The analyst is "
        "the first stage that knows what somebody asked for, and a question without the request "
        "is a question about whatever the model could infer from a repository's name — which is "
        "the failure this pair exists to measure, and it would arrive looking like requirements"
    )

    for a_link in the_links_the_system_derived:
        assert a_link not in what_the_second_stage_was_asked, (
            f"a citation's address is in the product analyst's question: {a_link!r}. This system "
            f"derives that link itself and no checkout on disk holds it, so it can only have come "
            f"from the discovery report. The analyst is handed the clone and the request, and a "
            f"question carrying another model's citations makes the requirements a reaction "
            f"rather than an answer"
        )

    for said in what_a_model_wrote:
        assert said not in what_the_second_stage_was_asked, (
            f"the discovery agent's own words are in the product analyst's question: {said!r}. A "
            f"stage that is handed a repository and a request and not a summary of the repository "
            f"is the reason a run can answer the wrong question, and nothing in either artifact "
            f"tells a gate that the answer came from the other model"
        )


@pytest.mark.parametrize("what_the_two_stages_answered", list(LlmProvider), indirect=True)
def test_both_artifacts_are_claims_about_this_checkout_and_neither_says_nothing(
    what_the_two_stages_answered: WhatTheTwoStagesAnswered,
    the_cloned_repository: ClonedRepository,
) -> None:
    """The report still cites only files that are there, and the requirements are a proposal.

    **Both halves are restated from the two isolation files, and that is deliberate.** A
    comparison between two artifacts is worth nothing if either is about a different repository or
    says nothing at all, and this tier's finding is that a real model cited a directory that
    resolved to nothing while looking exactly like a link. The node refuses that before the report
    exists; asserting it here is a second, independent check that the refusal is armed, because a
    test that trusted the node would pass on a node whose check had been commented out.

    **And a requirements set that reached here is a real answer.** `analyze_the_repository`
    repairs one answer empty in all three fields and then raises, so a `Requirements` reaching
    this assertion means a real model read a real inspection and said something. What is *not*
    claimed is that it is the right requirements set — that is a judgement about meaning, and this
    file measures the handover and the boundary, not the reasoning.
    """
    the_report = what_the_two_stages_answered.the_report
    the_requirements = what_the_two_stages_answered.the_requirements
    what_the_analyst_concluded = what_the_two_stages_answered.what_the_analyst_concluded

    cited_paths = [a_citation.path for a_citation in the_report.evidence_files]
    assert cited_paths, (
        "the discovery report cites nothing, so 'every cited path is a file of the clone' would be "
        "true of an empty list and this half of the assertion would be about nothing. A report "
        "with no citations is a paragraph rather than an inventory of what it rests on, and its "
        "conclusions are then about a repository no reader can look at"
    )

    not_in_the_clone = [
        a_path for a_path in cited_paths if not (the_cloned_repository.path / a_path).is_file()
    ]
    assert not not_in_the_clone, (
        f"{not_in_the_clone} are cited as evidence in a report produced from a clone that does not "
        f"hold them, so the report on one side of this comparison is a claim about a repository "
        f"that is not on the disk. `CitedFileNotFoundError` exists for this and the node raises "
        f"it; a report reaching here means the check either is not armed or was made a warning"
    )

    assert the_requirements.requirements or the_requirements.acceptance_criteria, (
        "a real repository was inspected and a real request was handed over, and the product "
        "analyst returned requirements and acceptance criteria that are both empty. The third "
        "collection is an admitted ambiguity, and a run that had none is a repository nothing was "
        "doubtful about — so what came back is a document describing doubt rather than a "
        "proposal, and `EmptyRequirementsError` exists because a person cannot tell the two apart"
    )

    for a_judgement in JUDGEMENTS_EVERY_AGENT_MAKES:
        assert getattr(what_the_analyst_concluded.judged, a_judgement).strip(), (
            f"the product analyst left {a_judgement} empty. It is the one agent holding both the "
            f"request and the inspection, so its doubt is the only one in the run that is about "
            f"the work as a whole — and an empty field reads as a doubt nobody had"
        )


@pytest.mark.parametrize("what_the_two_stages_answered", list(LlmProvider), indirect=True)
def test_the_requirements_are_not_sentences_the_report_already_says(
    what_the_two_stages_answered: WhatTheTwoStagesAnswered,
) -> None:
    """The requirements are not sentences the report already says, in either direction.

    **This is the only claim about the two artifacts' content that can be made without a second
    model, and its weakness is the first thing to say about it.** A requirement that restates the
    report in *other words* passes this check, because a check that read meaning would have to ask
    a model to judge another model's sentence — which is a model grading a model, and §0.3 puts
    reasoning quality in `evals/` and never in pytest. So the claim here is the one a gate could
    make while holding both cards: neither document contains the other's text.

    **Both directions, because a restatement can go either way.** A report's summary copied into
    a requirement is the failure this is here for; a requirement copied into the summary is the
    same failure arriving from the other side, and a one-directional check would hear only the
    first of them.

    **Two skips and both are guards against a vacuous pass, and they are about the two ends of
    the comparison.** A report with no summary has no text for a requirement to restate, and a
    requirements set with no requirement has nothing that could be one — so "neither contains the
    other" would be true of a pair with a hole in the middle. Either end empty and this tier skips
    with the reason rather than reporting a boundary it never approached. **`Requirements` allows
    either shape** — a proposal of criteria and no requirement is legitimate, and so is a proposal
    of one requirement and no criteria — which is exactly why the check is written out rather than
    assumed.
    """
    the_report = what_the_two_stages_answered.the_report
    the_requirements = what_the_two_stages_answered.the_requirements

    if not the_report.architecture_summary.strip():
        pytest.skip(
            "this run's discovery report left its architecture summary empty, so there is no text "
            "for a requirement to restate. The report cites files, and `DiscoveryReport` refuses "
            "one that says nothing at all — so this is a run that described a repository by its "
            "inventory alone, and whether the requirements restate it is a question about a text "
            "this run did not produce"
        )

    if not the_requirements.requirements:
        pytest.skip(
            "this run's product analyst returned acceptance criteria and no requirement, which "
            "`Requirements` allows and this tier does not judge. The comparison below is between "
            "a requirement and a sentence of the report, so there is nothing on one side of it to "
            "compare"
        )

    the_report_says = _as_one_line(_everything_the_report_prose_says(the_report))
    the_summary_says = _as_one_line(the_report.architecture_summary)
    assert the_report_says and the_summary_says in the_report_says, (
        "the report's prose is empty, so the check below would compare every requirement against "
        "nothing and find nothing wrong with any of them. A report that filled an inventory "
        "field and stopped is what this is for"
    )

    for a_requirement in the_requirements.requirements:
        as_one_line = _as_one_line(a_requirement)

        assert as_one_line not in the_report_says, (
            f"this requirement is a sentence of the discovery report: {a_requirement!r}. The "
            f"analyst was handed the clone and the request rather than a summary of the "
            f"repository, and when the two documents say the same thing the run has produced a "
            f"description of the project twice — and a gate reading the second card has no way "
            f"to know the first one wrote it"
        )
        assert the_summary_says not in as_one_line, (
            f"this requirement carries the discovery report's architecture summary inside it: "
            f"{a_requirement!r}. That is the same restatement arriving the other way round, and "
            f"it is the harder of the two to notice, because the summary is a paragraph and the "
            f"requirement reads like one more line of it"
        )
