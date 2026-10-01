"""The security report a person approved, and the plan that came after it — the sharpest pair here.

**This is the pair where the code has already written its own finding down.**
`_how_the_requirements_read` in `plan_the_change` says it: *"a plan written from the original
sentence can contradict the security report it never read, and nothing downstream would notice."*
Read the signature and the sentence is a description of a type: `plan_the_change(requirements,
clone, repository, model, what_the_suite_announced)`, so the planner is handed requirements and a
checkout and **not** the `SecurityReport` a person approved two gates earlier. The node agrees —
`plan_the_change_in_this_run` reads `state["requirements"]`, `state["clone"]` and the repository,
while `state["security_report"]` sits in that same state and nothing ever reads it.

**Two artifacts a person approved in sequence, one of them invisible to the stage that came after,
and no mechanism in the graph that compares them.** So what is measured here is a gap rather than a
defect: the second approval could not have been informed by the first, and a file that went looking
for a plan *contradicting* a finding would be looking for something these seams cannot produce. A
plan that cannot see the report cannot argue with it.

**And so the honest half is positive, and it is checked.** What a gate can do with these two
artifacts in hand is stated in the tests below rather than approximated: the plan's paths are
grounded in the checkout the planner was shown, and every path a finding quotes is one the analyst
could have read out of that same checkout. Both are the mechanical claims two approved artifacts
must satisfy before anybody may hold them side by side, and neither needs a model to agree about
anything.

**The security report is taken first, and that order is the argument rather than an accident.** A
report produced after the requirements could be a reaction to them, and a reader could wonder
whether the plan's silence about it is explained by a report that was written after something.
Taking it first means the report could not have been a reaction to the requirements, and two calls
that cannot see each other are not made different by the order they are made in.

**The product analyst runs in the middle, and that is scaffolding rather than a third stage under
test.** The planner's input is approved `Requirements`, so a file measuring security→plan needs
them, and `test_plan_the_change.py` states the case against chaining a real agent into a file whose
job is to isolate one. Three real calls happen, in the order this file needs them, and the pair
under test is the security report's and the plan's.

**`what_the_suite_announced` is the production constant, and a refusal is skipped out loud.**
`plan_node` hands the planner `THE_RUNNER_ANNOUNCED_NOTHING_YET`, so that constant is imported
rather than `""` written here, and the test is the production value by construction instead of by
agreement. A plan naming a test in a directory this repository does not collect is refused by
`PlannedTestDirectoryNotCollectedError`, and this file skips with the refusal printed rather than
letting a refusal it did not cause end the module as an error — for the reason
`test_the_plan_into_the_implementation.py` gives, which is the same one: the refusal is decided
before the seam this file measures even opens, and a plan that will not be run by this repository's
suite is a fact about the repository and this deployment's model rather than a fault in either.

**What this file therefore does not prove.** It does not prove a plan is *wrong* about security —
nothing in the graph compares the two artifacts and nothing here invents that comparison, because a
second model asked to make the judgement would be a model grading a model and §0.3 puts reasoning
quality in `evals/`. It does not prove the planner would have obeyed a recommendation even if it
had been shown one. It proves what was in the question, which is the part a reader can check and the
part the code itself says nothing notices.

The provider is a parameter rather than a constant, so proving a second one is a different run and
not a rewritten test. A provider the deployment is not configured for says so out loud.
"""

from __future__ import annotations

import re
from typing import NamedTuple

import pytest

from aisdlc.agents.analyze_the_repository import analyze_the_repository
from aisdlc.agents.implement_the_plan import the_paths_the_plan_names
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.inspect_for_security_risk import inspect_for_security_risk
from aisdlc.agents.plan_the_change import (
    PlannedFileNotFoundError,
    PlannedFileToAddFoundError,
    PlannedTestDirectoryNotCollectedError,
    PlannedTestDirectoryNotFoundError,
    _every_file_to_change_is_in_the_clone,
    plan_the_change,
    the_prompt_to_plan_a_change,
)
from aisdlc.agents.requirements import Requirements
from aisdlc.agents.security_report import SecurityReport
from aisdlc.domain.commissioned_request import CommissionedRequest
from aisdlc.domain.repository import Repository
from aisdlc.graph.plan_node import THE_RUNNER_ANNOUNCED_NOTHING_YET
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import an_inspection_of, an_inspection_of_the_code

pytestmark = pytest.mark.e2e

A_PATH_IN_A_QUOTE = re.compile(r"[`\"']([\w./-]+\.[A-Za-z]{1,5})[`\"']")
"""A quoted word ending in something extension-shaped, which is what a path looks like in prose.

**Copied from `tests/e2e/test_inspect_for_security_risk.py` rather than imported from it.** The
alternative would make this file's grounding check agree with the code by construction, and a
pattern that lost its quoting anchors would take the assertion meant to notice with it — a check on
a check is the only kind that survives the check being wrong. Matched loosely on purpose: what comes
out is a *candidate*, and what is then asked of it is written down in
`_names_a_location_in_the_checkout`.
"""


def _names_a_location_in_the_checkout(a_candidate: str) -> bool:
    """Whether a quoted word names a place in a repository, or only looks as though it might.

    **A slash, and nothing else, decides it.** `tests/e2e/data/e2e.db` names a place, because a path
    spelled from the root cannot be anything else. `middleware.ts` and `payload.sub` are the two
    words this deployment's model produced, and the check cannot tell them apart: the first was
    `web-app/src/middleware.ts` named by its own last segment, the second was a *field* in a request
    body, and reporting that as a file the repository does not have is a claim about the model that
    is simply false. **A bare dotted word is a location about half the time, and an assertion about
    half the time is not an assertion.**

    **So a candidate with no slash in it is not asked about, and the cost is written down here
    rather than left for somebody to discover.** A fabrication named by its own file name alone —
    `secrets.json` — is not caught by this file. `test_inspect_for_security_risk.py` asks about both
    forms and is therefore flaky for this reason as well as the next one; that is a finding about
    that file, and nothing in this one can fix it from here.
    """
    return "/" in a_candidate


def _the_analyst_had_grounds_to_name(clone: ClonedRepository, a_quoted: str) -> bool:
    """Whether this quoted path is something the analyst could have read, and so had reason to name.

    **Three grounds, and the third is the one the obvious check gets wrong.** A path is grounded if
    the checkout holds it, or if some file of the checkout is called that, **or if the analyst was
    shown the path itself** — because a repository *declaring* a file is not the same thing as
    containing one, and a security finding naming a declared-but-absent file is the most ordinary
    finding there is. This repository's own `tests/e2e/infra/env.ts` says

        export const DATA_DB = path.resolve(process.cwd(), "tests/e2e/data/e2e.db");

    and that database is created by a test run rather than committed, so `(clone.path /
    "tests/e2e/data/e2e.db").is_file()` answers no for a path the analyst read with its own eyes.
    **The first version of this file called that a fabrication, twice, and was wrong both times** —
    the evidence is the line above and not a model that remembered something.

    **The second ground is a bare file name, and only a bare file name.** `rglob` is the last
    segment, so what is asked is literally "is there a file called this somewhere in the checkout",
    and a substring match is never involved because the name has to be the whole of the last
    segment. **It also refuses a pattern with a directory in it** — `NotImplementedError:
    Non-relative patterns are unsupported` — so the guard is load-bearing rather than tidiness: a
    model that quotes `` `/etc/shadow.yaml` `` is quoting an absolute path, and `rglob` turns that
    into an exception rather than into the answer the assertion wants. An absolute path is not a
    path in a checkout either, so the ground does not apply to one and the third answers it.
    """
    if (clone.path / a_quoted).is_file():
        return True
    if "/" not in a_quoted and any(
        an_ordinary_file.is_file() for an_ordinary_file in clone.path.rglob(a_quoted)
    ):
        return True
    return a_quoted in an_inspection_of_the_code(clone)


def _what_the_report_alone_says(the_report: SecurityReport) -> list[tuple[str, str]]:
    """Every string that could only have come from this report, named by where it is in it.

    **Three fields of every finding, and not every field.** A `severity` is one of a closed set of
    words and `false_positive_notes` are the notes a reader uses to *dismiss* a finding, so both
    are text a report can share with any other document without either having read the other. What
    the report asserts, what it says it saw and what it advises are the three strings that would be
    here only if the report had been read.

    **The account of a report with no findings is in the list too, and that is what keeps the list
    from being empty.** `SecurityReport` refuses a report with neither findings nor an account, so
    a report reaching here always has something — but a model that found nothing puts its only
    prose in `nothing_found_because`, and an absence check over zero findings would then be about
    nothing. The account is asked of its first paragraph, which the node composes from its own
    inspection and which no other stage is shown.
    """
    said: list[tuple[str, str]] = []

    for a_number, a_finding in enumerate(the_report.findings, start=1):
        for a_field in ("statement", "signal", "recommendation"):
            the_words = str(getattr(a_finding, a_field)).strip()
            if the_words:
                said.append((f"finding {a_number}'s {a_field}", the_words))

    if the_report.nothing_found_because:
        the_first_paragraph = the_report.nothing_found_because.strip().split("\n\n", 1)[0].strip()
        if the_first_paragraph:
            said.append(("the account of what the analyst examined", the_first_paragraph))

    return said


def _everything_the_product_analyst_said(the_requirements: Requirements) -> list[str]:
    """Every string the requirements carry, in the order the artifact lists them.

    **The ambiguity's own wording and not the mark beside it.** `one_line_of` prefixes
    `[only a person can answer]` to some of them, so asking for the bare text is the more demanding
    check: a requirement rendered differently would not be found, which is the conservative
    direction for an assertion whose whole job is to fail when a handover quietly stops happening.
    """
    said = [*the_requirements.requirements, *the_requirements.acceptance_criteria]
    said += [an_ambiguity.what_is_undetermined for an_ambiguity in the_requirements.ambiguities]
    return said


class WhatTheTwoStagesAnswered(NamedTuple):
    """The report, the requirements and the plan, in the order this run produced them."""

    the_security_report: SecurityReport
    the_requirements: Requirements
    the_plan: ImplementationPlan


@pytest.fixture(scope="module")
def what_the_two_stages_answered(
    the_repository: Repository,
    the_cloned_repository: ClonedRepository,
    a_request: CommissionedRequest,
    the_model_for,
    request,
) -> WhatTheTwoStagesAnswered:
    """Three real calls, in the order this file needs them, over one read-only clone.

    **The report first, the requirements second and the plan last, and each of the three is the
    production call.** `inspect_for_security_risk` is handed a clone, a repository and a model;
    `analyze_the_repository` is handed the same clone, that repository, the request and the model;
    `plan_the_change` is handed the requirements the analyst concluded, the clone, the repository,
    the model and the runner's announcement. Nothing here reaches around a seam.

    **The plan is unwrapped from its answer and the answer's three sentences are dropped.** The
    planning node hands on `what_the_planning_agent_concluded.plan`, so carrying the whole
    `ImplementationPlanAnswer` into the assertions would measure a handover production does not make
    — and those three sentences are the planner's own opinion about the plan, which is the subject
    of `test_the_plan_into_the_implementation.py` rather than of this file.

    **Nothing here writes, so the read-only clone is the one every stage is given.** The one stage
    in this pipeline that changes a checkout is handed a copy of it, and a file measuring what
    three read-only stages were shown has no reason to spend that.

    **A plan whose test the suite will not collect is skipped with the refusal printed.** The
    refusal fires only after this deployment's correction budget is spent, so it is both slow and
    about something upstream of the seam this file measures; reporting it as a failure of the pair
    would be a claim about the wrong thing, and swallowing it would be worse.
    """
    the_model = the_model_for(request.param)

    the_security_report = inspect_for_security_risk(
        the_cloned_repository, the_repository, the_model
    )
    the_requirements, _ = analyze_the_repository(
        the_cloned_repository, the_repository, a_request, the_model
    )

    try:
        what_the_planning_agent_concluded = plan_the_change(
            the_requirements,
            the_cloned_repository,
            the_repository,
            the_model,
            THE_RUNNER_ANNOUNCED_NOTHING_YET,
        )
    except PlannedTestDirectoryNotCollectedError as refused:
        pytest.skip(
            f"a real planning agent, given real requirements and this repository, would not name a "
            f"test in a directory the suite collects, and this run's correction budget was spent "
            f"before it answered. {str(refused).strip()}\n\nThat is a fact about this repository "
            f"and this deployment's model, and it is decided before the seam this file measures "
            f"begins. Point the tier at a repository whose tests live where a planner puts them, "
            f"and run again."
        )

    return WhatTheTwoStagesAnswered(
        the_security_report=the_security_report,
        the_requirements=the_requirements,
        the_plan=what_the_planning_agent_concluded.plan,
    )


@pytest.mark.parametrize("what_the_two_stages_answered", list(LlmProvider), indirect=True)
def test_the_planners_question_carries_the_requirements_and_not_the_security_report(
    what_the_two_stages_answered: WhatTheTwoStagesAnswered,
    the_cloned_repository: ClonedRepository,
    the_repository: Repository,
) -> None:
    """The report is in the gate's hands and out of the planner's question, and both are checked.

    **Asked of the prompt, because the prompt is the whole of what this stage was given.** The
    signature takes requirements, a clone and a repository, and the caller in production passes
    exactly those; a change that also passed the `SecurityReport` would still typecheck, and a plan
    written in reaction to a report a person had already approved is a different artifact from one
    written without it — and the gate cannot tell the two apart, because both arrive as an
    `ImplementationPlan`.

    **Both halves, and the first is what gives the second its meaning.** "The report is absent" is
    satisfied by an empty question, so the question is first required to carry something the product
    analyst really concluded. A prompt that had lost the requirements *and* the report would pass a
    one-sided check, and losing the requirements is the likelier accident.

    **The prompt is rebuilt from the same clone the planner was given.** `an_inspection_of` is what
    `plan_the_change` inlines, so a question built over anything else would pass for the wrong
    reason.
    """
    what_the_planners_question = the_prompt_to_plan_a_change(
        what_the_two_stages_answered.the_requirements,
        an_inspection_of(the_cloned_repository),
        the_repository,
    )

    what_the_analyst_said = _everything_the_product_analyst_said(
        what_the_two_stages_answered.the_requirements
    )
    assert any(the_words in what_the_planners_question for the_words in what_the_analyst_said), (
        f"the planner's question carries none of the {len(what_the_analyst_said)} statement(s) the "
        "product analyst really concluded, so the handover this pair sits downstream of did not "
        "happen — and the report's absence below would then be true of a question that carried "
        "nothing at all. Those requirements are what a person approved two gates earlier and they "
        "are the planner's whole input document"
    )

    what_the_report_says = _what_the_report_alone_says(
        what_the_two_stages_answered.the_security_report
    )
    the_number_of_findings = len(what_the_two_stages_answered.the_security_report.findings)
    the_report_names_what_it_examined = bool(
        what_the_two_stages_answered.the_security_report.nothing_found_because
    )
    assert what_the_report_says, (
        f"the security report says nothing a reader could weigh: {the_number_of_findings} "
        f"finding(s) and {'an' if the_report_names_what_it_examined else 'no'} account of what was "
        "examined. Every absence below is then the absence of nothing, so this assertion would be "
        "about an artifact that was never really written"
    )

    reached_the_planner = [
        where
        for where, the_words in what_the_report_says
        if the_words in what_the_planners_question
    ]
    assert not reached_the_planner, (
        f"{reached_the_planner} is in the planner's question. A person approved this security "
        "report and then approved a plan, and the second approval could not have been informed by "
        "the first — a plan that reasons about a finding nobody put in front of it is a plan whose "
        "account of the risk came from somewhere nobody recorded, and the gate cannot tell the two "
        "apart because both arrive as an `ImplementationPlan`"
    )


@pytest.mark.parametrize("what_the_two_stages_answered", list(LlmProvider), indirect=True)
def test_the_plans_paths_are_grounded_in_the_checkout_it_was_planned_against(
    what_the_two_stages_answered: WhatTheTwoStagesAnswered,
    the_cloned_repository: ClonedRepository,
    the_repository: Repository,
) -> None:
    """Every path the real plan names is a file of this clone, or one the change brings into being.

    **This is the positive half of the finding, and it is a real gate's work rather than this
    file's.** Two approved artifacts a person may hold side by side are only comparable if each is
    about the same repository: the plan's `files_to_change` has to be files the repository has,
    `files_to_add` files it has not, and `tests_to_add` tests going where the repository already
    keeps them. The report makes no such promise about paths — it has no field for one — so the
    plan is the side of the pair that can be held to it, and this is the check.

    **The production rule is called rather than restated.** `plan_the_change` already refuses a plan
    whose paths are not grounded, so a plan reaching here has passed it and this assertion is about
    a *real* plan over a *real* checkout. Restating the rule here would be a second copy that could
    drift from the first, which is the failure this repository keeps paying for. What is added is
    the `assert`, because a rule that raised would take the module down as an error rather than
    reporting a contract this file claims to have checked.

    **The non-empty guard is first, and it is not decoration.** Every path of a plan that names
    nothing is a path the checkout grounds, so a check that could not hear about an empty plan would
    pass exactly the case it exists for.
    """
    the_plan = what_the_two_stages_answered.the_plan
    the_named_paths = the_paths_the_plan_names(the_plan)
    assert the_named_paths, (
        f"the real plan names no path at all across "
        f"{', '.join(ImplementationPlan.model_fields)}, so nothing is being grounded and every "
        f"assertion below would be true of a plan that says nothing to do. `EmptyPlanError` exists "
        f"for that and the planning node raises it, so a plan reaching here means the refusal is "
        f"not armed"
    )

    refused: Exception | None = None
    try:
        _every_file_to_change_is_in_the_clone(the_cloned_repository, the_repository, the_plan)
    except (
        PlannedFileNotFoundError,
        PlannedFileToAddFoundError,
        PlannedTestDirectoryNotFoundError,
    ) as said:
        refused = said

    assert refused is None, (
        f"the real plan names {the_named_paths} and the checkout it was planned against does not "
        f"ground them: {str(refused).strip()}\n\nA person is asked to approve this plan beside a "
        f"security report about the same repository, and neither can be compared until the paths "
        f"both of them talk about are real. `files_to_change` is a promise about files that are "
        f"there, and a plan making it about nothing is refused before a person ever sees it"
    )


@pytest.mark.parametrize("what_the_two_stages_answered", list(LlmProvider), indirect=True)
def test_the_report_the_gate_holds_beside_the_plan_is_grounded_in_what_the_analyst_was_shown(
    what_the_two_stages_answered: WhatTheTwoStagesAnswered,
    the_cloned_repository: ClonedRepository,
) -> None:
    """Every path a finding quotes is one the analyst could have read out of this checkout.

    **The artifact a gate holds and cannot check is the one this is about.** The plan can be held
    to the checkout by its paths, and the test above does that; a `SecurityReport` has no field
    naming a file, so the only thing a reader can hold it to is its own prose. A path in that prose
    which is nowhere in the checkout was invented or remembered from another repository, and **a
    security report quoting code that does not exist is the most persuasive kind of fiction there
    is** — which is why the report the planner never sees has to be sound in the gate's hands, since
    that is the only place a person will ever read it.

    **"Could have read", and not "is a file of the checkout", and two real runs are why.** This
    repository's `tests/e2e/infra/env.ts` says `path.resolve(process.cwd(),
    "tests/e2e/data/e2e.db")`, and that database is created by a test run rather than committed —
    so a finding naming it names a file the analyst read and the filesystem does not have, which is
    the most ordinary finding a security report carries. The first version of this file asked only
    whether the path was a file, called that a fabrication, and was wrong; the second asked only
    whether the path was in the inspection, and would have missed a file the analyst read by its own
    last segment. **Three grounds, then**, and each names a way a model is right about a path that
    is not a file at the root.

    **Why it is here and not only in the isolation file.** `test_inspect_for_security_risk.py`
    proves one report is grounded. This proves the report a person held *beside this plan* is
    grounded in the same checkout the plan was planned against — a comparison is only meaningful
    when both artifacts came out of one directory, and that is a fact about a pair rather than
    about an agent.

    **Skipped, loudly, when there is nothing to ground.** A report with no findings has no signal,
    and an assertion over an empty list of findings is an assertion about nothing; a report whose
    findings quote no path at all has the same problem. Both are said out loud rather than passed,
    because a green tick for a check that examined nothing is the one thing this tier is not allowed
    to produce.

    **Only the words that name a place are asked about, and a run's `payload.sub` is why.** That
    was a field in a request body, not a file, and a check that reports it as a missing file is not
    doubt about grounding; it is the check being wrong. A bare dotted word is a location about half
    the time, and the narrowing that follows is written down in `_names_a_location_in_the_checkout`
    together with what it gives up.
    """
    the_report = what_the_two_stages_answered.the_security_report

    if not the_report.findings:
        pytest.skip(
            "a real security analyst examined this repository and reported no findings, so there "
            "is no signal to hold to the checkout. That is a defensible answer for a repository "
            "with no visible risk — §10 calls this analysis advisory rather than a replacement for "
            "a scanner — and the report says so in words rather than in silence."
        )

    every_path_a_finding_quoted = [
        a_quoted
        for a_finding in the_report.findings
        for a_quoted in A_PATH_IN_A_QUOTE.findall(a_finding.signal)
        if _names_a_location_in_the_checkout(a_quoted)
    ]

    if not every_path_a_finding_quoted:
        pytest.skip(
            f"none of the {len(the_report.findings)} finding(s) in this real report quotes a path "
            f"— that is, a word with a directory in it — so there is nothing to hold to the "
            f"checkout and every assertion below would be about an empty list. Point the tier at "
            f"a repository whose security findings name the files they are about, or accept that "
            f"this repository's report says so in prose only."
        )

    ungrounded = [
        a_quoted
        for a_quoted in every_path_a_finding_quoted
        if not _the_analyst_had_grounds_to_name(the_cloned_repository, a_quoted)
    ]
    assert not ungrounded, (
        f"{sorted(set(ungrounded))} are quoted as evidence in a report a gate holds beside a plan "
        f"planned against this same checkout, and the analyst had no way to have read them: the "
        f"checkout holds no such file, no file is called that, and the string is in none of the "
        f"code, manifests, README or CI configuration the inspection carried. Either the model "
        f"invented them or it remembered another repository — and this report is the only place a "
        f"person will read about the risk, because the planner that acts on the change is never "
        f"shown it. `an_inspection_of_the_code` is what prevents it, by carrying the code and "
        f"naming what it left out"
    )
