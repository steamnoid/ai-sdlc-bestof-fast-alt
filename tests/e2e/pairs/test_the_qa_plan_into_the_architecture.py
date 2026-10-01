"""The QA plan a person approved, and the architecture report the next gate presented.

**The seam this pair measures is not there, and the two signatures are the whole
argument.** `analyze_the_requirements(requirements, model)` is handed approved
`Requirements` — the one true handover in this pipeline, and the one
`test_the_requirements_into_the_qa_plan.py` owns. `analyze_the_architecture(clone,
repository, model)` is handed a clone and a repository and no `QaPlan` at all. The node
agrees: `analyze_the_architecture_in_this_run` reads `state["clone"]` and
`state["work_item"].repository`, while `state["qa_plan"]` sits in that same state and the
only thing in the graph that reads it afterwards is `record_what_this_run_has`, which
writes it to a file.

**So a person approved a QA plan, and the report the very next gate showed them could not
have been informed by it.** The architect is asked for "a risk is a way the current shape
makes a future change harder or wrong", and a QA plan is an account of what would count as
proof that it did not. A report written without the plan cannot be argued with it, nothing
in the graph compares the two, and a person holding both cards has no way to tell a report
that answered the plan from one that never saw it — both arrive as an `ArchitectureReport`.

**Three real calls, and the product analyst is scaffolding rather than a third stage under
test.** The QA analyst is handed approved `Requirements` and nothing else, so a file
measuring QA→architecture needs real ones. A stand-in would leave the plan being about a
document no gate ever presented, which is the same argument
`test_the_plan_into_the_implementation.py` makes about the planner. The pair under test is
the QA plan's and the architecture report's; the requirements are how they are obtained.

**And what a gate cannot compare here is said before the tests rather than inside one.**
`ArchitectureReport` carries findings, modules, dependencies, boundaries and risks, and no
field about the suite; the architect is handed `an_inspection_of`, which carries the
top-level listing, the manifests, the README and the CI configuration and no source file at
all. So a claim in `boundaries` or in `risks` about what the suite's coverage is has
nothing behind it in the artifact and nothing behind it in the substrate — and whether a
given sentence is *about* test coverage is a judgement about meaning, which a second model
asked to make it would be a model grading a model, and §0.3 puts in `evals/`. **No weak
check is written here to stand in for it.** What is asserted instead is the strongest
mechanical thing available: the architect's substrate is a strict prefix of the one the
security analyst is given, so this file *knows* no code and no test was in front of that
report; and neither card repeats a sentence of the other, which is the only comparison of
the two that survives without asking a model to grade one.

**One clone, and neither stage writes.** `the_cloned_repository` is the read-only fixture
every other stage in this tier is handed, and the plan→implementation pair is the one that
needs a second copy — because what a run changed is only knowable as a difference between
two directories. A comparison between two artifacts is worth nothing unless both came out
of one checkout, and a second copy here would make it a comparison of two repositories.

The provider is a parameter rather than a constant, so proving a second one is a different
run and not a rewritten test. A provider the deployment is not configured for says so out
loud.
"""

from __future__ import annotations

from typing import NamedTuple

import pytest

from aisdlc.agents.a_value_that_says_something import a_value_that_says_something
from aisdlc.agents.analyze_the_architecture import (
    analyze_the_architecture,
    the_prompt_to_analyze_the_architecture,
)
from aisdlc.agents.analyze_the_repository import analyze_the_repository
from aisdlc.agents.analyze_the_requirements import analyze_the_requirements
from aisdlc.agents.architecture_report import ArchitectureReport
from aisdlc.agents.architecture_report_answer import ArchitectureReportAnswer
from aisdlc.agents.qa_plan import QaPlan
from aisdlc.agents.qa_plan_answer import QaPlanAnswer
from aisdlc.domain.commissioned_request import CommissionedRequest
from aisdlc.domain.repository import Repository
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import an_inspection_of, an_inspection_of_the_code

pytestmark = pytest.mark.e2e

JUDGEMENTS_EVERY_AGENT_MAKES = (
    "what_it_found",
    "what_it_could_not_settle",
    "what_it_expects_next",
)


def _as_one_line(said: str) -> str:
    """The same text with its layout and its capitalisation thrown away.

    **Comparing whole sentences rather than fragments, and that is why the layout goes
    first.** A scenario and a risk that differ only in a line break or a capital are the same
    claim, and a check that read them as two strings would call that a difference and pass a
    restatement — which is the one failure this half of the file exists to hear about.
    """
    return " ".join(said.split()).casefold()


def _every_string_the_qa_plan_says(the_plan: QaPlan) -> list[str]:
    """Every string a QA plan carries, in the order the artifact's own fields are declared.

    **Read off `QaPlan.model_fields` rather than restated field by field.** A field added to
    the artifact is then checked here without this file being edited, and an entry this file
    forgot to name could not go on to be a sentence that slipped past it. `test_strategy` is
    one string and the other three are lists of them, so both shapes are walked the same way.
    """
    said: list[str] = []

    for a_field in QaPlan.model_fields:
        what_it_holds = getattr(the_plan, a_field)
        if isinstance(what_it_holds, list):
            said.extend(str(one_of_them) for one_of_them in what_it_holds)
        elif what_it_holds.strip():
            said.append(what_it_holds)

    return said


def _every_string_the_architecture_report_says(the_report: ArchitectureReport) -> list[str]:
    """Every string an architecture report carries, in the order the glossary lists them.

    **All five collections and not only the two a coverage claim would arrive in.** A check
    pinned to `boundaries` and `risks` would be about an empty list on any run where the
    architect filled the other three and invented no boundary, and an assertion over nothing
    is the one kind this tier is not allowed to produce.
    """
    said: list[str] = []
    for a_collection in the_report.everything_it_says():
        said.extend(str(one_of_them) for one_of_them in a_collection)
    return said


def _what_the_two_cards_say_in_common(
    the_plan: QaPlan, the_report: ArchitectureReport
) -> list[tuple[str, str]]:
    """Every sentence of one card that appears word for word in the other, and which is whose.

    **Both directions, because a restatement can go either way.** A QA scenario copied into a
    risk is the failure this is here for; an architectural risk copied into a scenario is the
    same failure arriving from the other side, and a one-directional check would hear only
    the first of them. Each match is returned with the name of the collection it was found
    in, so a failure says which document repeated which rather than only that something
    matched.
    """
    said_by_the_plan = [
        (_as_one_line(one_of_them), one_of_them)
        for one_of_them in _every_string_the_qa_plan_says(the_plan)
    ]
    said_by_the_report = [
        (_as_one_line(one_of_them), one_of_them)
        for one_of_them in _every_string_the_architecture_report_says(the_report)
    ]

    in_common: list[tuple[str, str]] = []
    for the_plan_says, as_written_by_the_plan in said_by_the_plan:
        if the_plan_says and any(the_plan_says in said for _, said in said_by_the_report):
            in_common.append((f"the QA plan's {as_written_by_the_plan!r}", as_written_by_the_plan))
    for the_report_says, as_written_by_the_report in said_by_the_report:
        if the_report_says and any(the_report_says in said for _, said in said_by_the_plan):
            in_common.append(
                (
                    f"the architecture report's {as_written_by_the_report!r}",
                    as_written_by_the_report,
                )
            )

    return in_common


class WhatTheTwoStagesAnswered(NamedTuple):
    """The plan and the report, in the order this run produced them, and the checkout under both.

    **Kept in the order of the run, and the checkout comes with them because it is the thing
    the two are comparable *about*.** Two artifacts from two different directories would make
    every assertion below true for the wrong reason, and the sibling file that needs two
    clones is the one that proves the point by having to diff them.
    """

    the_qa_plan: QaPlan
    what_the_qa_analyst_concluded: QaPlanAnswer
    the_architecture_report: ArchitectureReport
    what_the_architect_concluded: ArchitectureReportAnswer


@pytest.fixture(scope="module")
def what_the_two_stages_answered(
    the_repository: Repository,
    the_cloned_repository: ClonedRepository,
    a_request: CommissionedRequest,
    the_model_for,
    request,
) -> WhatTheTwoStagesAnswered:
    """Three real calls in a run's order, and the two cards the gates between them showed.

    **The analyst, then the QA analyst, then the architect, and each of the three is the
    production call.** `analyze_the_repository` is handed the clone, that repository, the
    request and the model; `analyze_the_requirements` is handed the requirements the analyst
    concluded and the model; `analyze_the_architecture` is handed the clone, the repository
    and the model, and the plan is not among the three. Nothing here reaches around a seam.

    **Both answers are kept, and not only the two artifacts.** Each stage is asked three
    questions about its own work and keeps them beside the document rather than among it,
    and they are part of what has to be compared: an opinion one model reached is not
    something the next model was shown, and a pair carrying only the artifacts could not say
    so.

    **The read-only clone, and one of them rather than two.** Neither stage writes, and
    `test_the_plan_into_the_implementation.py` gives the reason the writing stage needs a
    copy of its own: what a run changed is only knowable as a difference, and nothing changed
    here.

    **The provider is `request.param` and the tests parametrise it indirectly**, so a run
    configured for one provider *skips* the others with the reason printed.
    """
    the_model = the_model_for(request.param)

    the_requirements, _ = analyze_the_repository(
        the_cloned_repository, the_repository, a_request, the_model
    )
    the_qa_plan, what_the_qa_analyst_concluded = analyze_the_requirements(
        the_requirements, the_model
    )
    the_architecture_report, what_the_architect_concluded = analyze_the_architecture(
        the_cloned_repository, the_repository, the_model
    )

    return WhatTheTwoStagesAnswered(
        the_qa_plan=the_qa_plan,
        what_the_qa_analyst_concluded=what_the_qa_analyst_concluded,
        the_architecture_report=the_architecture_report,
        what_the_architect_concluded=what_the_architect_concluded,
    )


@pytest.mark.parametrize("what_the_two_stages_answered", list(LlmProvider), indirect=True)
def test_the_architect_was_asked_about_the_repository_and_not_about_the_qa_plan(
    what_the_two_stages_answered: WhatTheTwoStagesAnswered,
    the_cloned_repository: ClonedRepository,
    the_repository: Repository,
) -> None:
    """The question carries the repository and the branch it was cloned at, and no part of the plan.

    **Asked of the prompt, because the prompt is the whole of what this stage was given.** The
    signature takes a clone, a repository and a model, and the caller in production passes
    exactly those; a change that also handed over the `QaPlan` would still typecheck, and the
    report would then be a reaction to a QA plan a person had already approved rather than an
    independent reading of the code — and the gate cannot tell the two apart, because both
    arrive as an `ArchitectureReport`.

    **The first half is what gives the second half its meaning.** "The plan is absent" is
    satisfied by an empty question, so the question is first required to carry the inspection
    and the inspection is required to name the branch and the commit the run cloned — the two
    facts every claim in the report is about, and neither of which a thin question can carry.
    A prompt that had lost the inspection *and* the plan would pass a one-sided check, and
    losing the inspection is the likelier accident.

    **The prefix is the substrate claim, and it is what makes the coverage argument
    checkable.** `an_inspection_of` is a strict prefix of `an_inspection_of_the_code` — the
    same sections in the same order, with the code and the closing account of what was
    withheld added — so this file knows from the filesystem, before reading a single word the
    model wrote, that the architect was shown no source and therefore no test. That is the
    only thing a claim about the suite's coverage could have rested on, and it is not there.

    **The three sentences of judgement are asked about too.** The QA plan's own strings are
    matched verbatim rather than as a phrase, and the architect's question is the clone: an
    acceptance criterion or a scenario appearing in it is a person's approved words arriving
    at a stage that was handed a directory, and nothing in the graph would record the route.
    """
    the_inspection_the_architect_was_shown = an_inspection_of(the_cloned_repository)
    what_the_architect_was_asked = the_prompt_to_analyze_the_architecture(
        the_inspection_the_architect_was_shown, the_repository
    )

    assert the_inspection_the_architect_was_shown in what_the_architect_was_asked, (
        "the architect's question does not carry the inspection it was given, so 'the QA plan "
        "is not in it' below would be true of a question carrying nothing at all — and the "
        "question is the whole of what this stage was shown. The prompt is rebuilt here by "
        "calling the function the node calls, over the same clone, so this is the question as "
        "it was put and not a reconstruction of it"
    )

    for the_fact_the_inspection_carries in (
        f"branch: {the_cloned_repository.ref}",
        f"commit: {the_cloned_repository.commit}",
    ):
        assert the_fact_the_inspection_carries in what_the_architect_was_asked, (
            f"{the_fact_the_inspection_carries!r} is in neither the inspection nor the "
            "architect's question. Every claim this report makes is about one commit of one "
            "branch, and a question that does not say which is a question about a repository "
            "that looks like this one"
        )

    the_inspection_the_security_analyst_is_shown = an_inspection_of_the_code(the_cloned_repository)
    assert the_inspection_the_architect_was_shown in the_inspection_the_security_analyst_is_shown, (
        "the inspection the security analyst is handed is not the one discovery was handed plus "
        "something, so the two stages are being shown two different repositories' worth of "
        "facts and a comparison between their reports is a comparison of two questions"
    )

    what_the_qa_plan_says = _every_string_the_qa_plan_says(what_the_two_stages_answered.the_qa_plan)
    assert what_the_qa_plan_says, (
        f"the real QA plan said nothing at all across {', '.join(QaPlan.model_fields)}, so every "
        "absence below would be the absence of nothing. `EmptyQaPlanError` exists and the QA "
        "node raises it, so a plan reaching here means the refusal is not armed"
    )

    reached_the_architect = [
        said for said in what_the_qa_plan_says if said in what_the_architect_was_asked
    ]
    assert not reached_the_architect, (
        f"{reached_the_architect!r} is in the architect's question. A person approved this QA "
        "plan at the gate immediately before, and the report the next gate showed them could "
        "not have been informed by it — a risk reasoned about a plan nobody put in front of it "
        "is a risk whose account of the testing came from somewhere nobody recorded, and the "
        "gate cannot see the difference because both arrive as an `ArchitectureReport`"
    )

    what_the_qa_analyst_judged = what_the_two_stages_answered.what_the_qa_analyst_concluded.judged
    for a_judgement in JUDGEMENTS_EVERY_AGENT_MAKES:
        said = getattr(what_the_qa_analyst_judged, a_judgement)
        assert said.strip(), (
            f"the QA analyst left {a_judgement} empty, so there is no opinion of its own to be "
            "found in the architect's question. That absence is correct and it is also weaker "
            "than it looks, which is why it is asserted here rather than left to the loop below"
        )
        assert said not in what_the_architect_was_asked, (
            f"the QA analyst's {a_judgement} is in the architect's question. That stage is asked "
            "what shape a repository has, and a question carrying another model's opinion of the "
            "work makes the report a reaction rather than a reading — and nothing in the graph "
            "compares the two cards a person was shown"
        )


@pytest.mark.parametrize("what_the_two_stages_answered", list(LlmProvider), indirect=True)
def test_neither_card_a_gate_holds_side_by_side_repeats_the_other(
    what_the_two_stages_answered: WhatTheTwoStagesAnswered,
) -> None:
    """The architecture report says nothing the QA plan said, in either direction.

    **This is the only comparison of the two cards that is mechanical, and its reach is
    stated rather than implied.** A gate can ask whether one document contains the other's
    text; it cannot ask whether a risk is *about* the same work as a scenario written in other
    words, because that is a judgement about meaning and a second model asked to make it would
    be a model grading a model. So the claim here is the one that survives: the report does
    not restate the plan, and a report that had been handed the plan would very often contain
    a sentence of it.

    **The artifact has no field for the suite, so a coverage claim has to arrive as a
    boundary or as a risk** — and neither word is special to testing, which is why this
    comparison is over all five collections rather than over those two. Checking only the two
    would be about an empty list on any run where the architect filled `findings`, `modules`
    and `dependencies` and invented no boundary, and a check over nothing is the one thing
    this tier must never report as a pass.

    **What it cannot hear is written down here rather than left to the next red run.** A risk
    about coverage invented by the architect from the CI configuration alone shares no
    sentence with the QA plan and passes here. Nothing in `ArchitectureReport` can hold it and
    the architect is shown no test, so there is nothing mechanical to hold it against — which
    is the finding this file records rather than one it papers over with a keyword search.
    """
    the_plan = what_the_two_stages_answered.the_qa_plan
    the_report = what_the_two_stages_answered.the_architecture_report

    assert a_value_that_says_something(the_plan.everything_it_says()), (
        f"the QA plan says nothing across {', '.join(QaPlan.model_fields)}, so a check for the "
        "report repeating it would compare every sentence of the report against an empty "
        "document. `EmptyQaPlanError` exists for that and the node raises it"
    )
    assert a_value_that_says_something(the_report.everything_it_says()), (
        "the architecture report says nothing across "
        f"{', '.join(ArchitectureReport.model_fields)}, so there is no sentence of it that "
        "could be a repetition. `EmptyArchitectureReportError` exists for that and the node "
        "raises it, so a report reaching here means the refusal is not armed"
    )

    in_common = _what_the_two_cards_say_in_common(the_plan, the_report)
    assert not in_common, (
        f"{[where for where, _ in in_common]} appears word for word in both cards. The "
        "architect is handed a clone and a repository and no QA plan, and a person approved that "
        "plan at the gate immediately before — so a report repeating a sentence of it is a "
        "report that reached the plan somehow, and a gate holding both cards cannot see the "
        "route it took"
    )


@pytest.mark.parametrize("what_the_two_stages_answered", list(LlmProvider), indirect=True)
def test_both_cards_a_person_was_asked_to_rule_on_carry_something_to_rule_on(
    what_the_two_stages_answered: WhatTheTwoStagesAnswered,
    the_placeholders: frozenset[str],
) -> None:
    """The plan's filled fields hold real sentences and the report names a finding.

    **A comparison between two artifacts is worth nothing if either says nothing at all, and
    this tier's own finding is that a real model returned a `test_strategy` of one space.**
    A field that is a shape rather than a sentence reads on a card exactly like one that is
    not, so every field that claims to be filled is asked to be non-blank and not a
    placeholder — and the guard is per field rather than "the plan is non-empty", because a
    plan whose scenarios were real and whose strategy was a space is the case.

    **`findings` and not the other four collections.** `ArchitectureReport` refuses a report
    empty in all five, so all five empty cannot reach here — but four filled and one empty is
    a real answer, and a test demanding five would be demanding a guess about what a
    repository worth describing looks like. The finding is the one a reader starts at.

    **Both are restated checks of a production rule rather than the rule itself.** Each node
    refuses an answer that said nothing and each artifact normalises whitespace, so a
    document reaching this assertion means the refusal is armed. Asserting it anyway is the
    point: a rule that had been turned into a warning would leave every other assertion in
    this file true of a document nobody wrote.
    """
    the_plan = what_the_two_stages_answered.the_qa_plan
    the_report = what_the_two_stages_answered.the_architecture_report

    for a_field in QaPlan.model_fields:
        what_it_holds = getattr(the_plan, a_field)
        said_about_it = (
            [str(one_of_them) for one_of_them in what_it_holds]
            if isinstance(what_it_holds, list)
            else [str(what_it_holds)]
        )

        for said in said_about_it:
            assert not said or (said.strip() and said.strip().lower() not in the_placeholders), (
                f"{said!r} is in the QA plan's {a_field}, and it is either whitespace or "
                "placeholder text. A person approving this plan cannot tell a field holding a "
                "space from a field holding a strategy, and `QaPlan` normalises the first to "
                "the second's absence — so a shape here is a card that says nothing in front of "
                "a decision somebody made"
            )

    assert the_report.findings, (
        f"the architecture analyst was asked what shape this repository has and its findings "
        f"are empty, with {len(the_report.modules)} module(s), {len(the_report.dependencies)} "
        f"dependency(ies), {len(the_report.boundaries)} boundary(ies) and "
        f"{len(the_report.risks)} risk(s) filled instead. That artifact is what the gate after "
        "the QA plan's gate presents, and findings are where a reader starts"
    )

    for a_collection in the_report.everything_it_says():
        for said in a_collection:
            assert str(said).strip().lower() not in the_placeholders, (
                f"{said!r} is placeholder text in the architecture report, which means the model "
                "returned a shape rather than a finding. A gate presents this document beside "
                "the QA plan and records a decision against its version, and a placeholder is "
                "material nobody read"
            )
