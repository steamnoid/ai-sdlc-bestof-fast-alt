"""The architecture report a person approved, and the security report the next gate presented.

**This is the pair the README says already bit this system, and the two stages have been
wired to two different inspections since.** `an_inspection_of` was built for *discovery* —
whose own docstring says source files are deliberately not in it — and the security analyst
was later wired to that same one. It was therefore asked to find authentication and
authorization problems while being handed a directory listing and a `package.json`, and a
real run's gate refused the report for exactly that:

    "Six of the seven entries are then speculation from filenames and dependency
     declarations alone (findings 4, 5 and 7 reason from `Dockerfile`, `.dockerignore` and
     `bcryptjs` to MCP-endpoint, image-hygiene and cost-factor conclusions the report itself
     calls 'undecidable from the manifest')"

The fix was a second function, `an_inspection_of_the_code`, which carries the file contents
and **ends by naming what it did not show** — and `inspect_for_security_risk` is now wired to
it while `analyze_the_architecture` is still wired to the short one. **So this file is where
that asymmetry is measured, and it is measured on the questions themselves rather than on
what the models then said about them**: a report reasoning from a filename is
indistinguishable on a card from a report reasoning from the file, and a rule that lives
only in a prompt is not a rule.

**The handover this pair is about is still not there, and the signatures are the whole
argument.** `analyze_the_architecture(clone, repository, model)` and
`inspect_for_security_risk(clone, repository, model)` are handed the same clone and the same
repository, and neither is handed the other's artifact. The nodes agree: the architecture
node reads `state["clone"]` and `state["work_item"].repository`, the security node reads
`state["clone"]` and `state["work_item"].repository`, and `state["architecture_report"]` sits
in that same state with the only reader after the gate being `record_what_this_run_has`,
which writes it to a file. **Two calls that share a substrate cannot be wrong *about* each
other**, which is what leaves a gate holding both cards as the only place the pair is
comparable at all.

**And what is compared there is the ground under the evidence.** A security report has no
field naming a file, so the only thing a reader can hold it to is its own prose, and a signal
quoting code that is not in the checkout was either invented or remembered from another
repository. This file reuses the three grounds `test_inspect_for_security_risk.py` already
argued for rather than writing a second set — the report a person held *beside this
architecture report* has to be sound in the gate's hands, since it is the only place it will
ever be read.

**One clone, and that is where this pair differs from the plan→implementation one.** Neither
stage writes, so `the_cloned_repository` is the right fixture and a second copy would buy
nothing. `a_clone_this_run_may_write` exists for the one stage that commits, and the reason
the sibling file needs two is that *what a run changed* is only knowable as a difference
between two directories — a question that does not arise here, because nothing here changed
anything. Both artifacts come out of one checkout, which is the fact that makes them two
cards about the same repository.

**One of the four tests needs no model at all, and that is the point of it.** The inspection
is read off the filesystem, so the positive claim — the code is there, and the account of
what was withheld is the closing section — is a fact about a tool rather than about a
model's behaviour. What is asked of the real run there is only that the report exists, which
is what makes this a real repository rather than a fixture.

The provider is a parameter rather than a constant, so proving a second one is a different
run and not a rewritten test. A provider the deployment is not configured for says so out
loud.
"""

from __future__ import annotations

import re
from typing import NamedTuple

import pytest

from aisdlc.agents.analyze_the_architecture import (
    analyze_the_architecture,
    the_prompt_to_analyze_the_architecture,
)
from aisdlc.agents.architecture_report import ArchitectureReport
from aisdlc.agents.architecture_report_answer import ArchitectureReportAnswer
from aisdlc.agents.inspect_for_security_risk import (
    inspect_for_security_risk,
    the_prompt_to_inspect_for_security_risk,
)
from aisdlc.agents.security_report import SecurityReport
from aisdlc.domain.repository import Repository
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import (
    _the_source_is_below,
    _what_was_not_shown,
    an_inspection_of,
    an_inspection_of_the_code,
)
from tests.e2e.test_inspect_for_security_risk import (
    A_PATH_IN_A_QUOTE,
    _the_analyst_had_grounds_to_name,
)

pytestmark = pytest.mark.e2e

JUDGEMENTS_EVERY_AGENT_MAKES = (
    "what_it_found",
    "what_it_could_not_settle",
    "what_it_expects_next",
)

A_HEADING = re.compile(r"^#{1,6} (.+)$", re.MULTILINE)
"""A markdown heading at the start of a line, at any level, and only its own title.

**Read from the production functions rather than written out here.** `_the_source_is_below` and
`_what_was_not_shown` are the two sections this pair is about, and a heading spelled out in a
test is a second spelling of it: the day production renames the closing section, a test
carrying the old words would fail on a rename rather than on the claim it exists to make, and
the failure would say nothing about the claim. The first line of what each function returns
is its heading, and that is what is asked of it.
"""

THE_HEADING_NAMING_THE_CODE = _the_source_is_below(["a file of the checkout"]).splitlines()[0]
THE_HEADING_NAMING_WHAT_WAS_LEFT_OUT = _what_was_not_shown(["a file of the checkout"]).splitlines()[
    0
]


def _as_one_line(said: str) -> str:
    """The same text with its layout and its capitalisation thrown away.

    **Comparing whole sentences rather than fragments, and that is why the layout goes
    first.** A finding and a risk that differ only in a line break or a capital are the same
    claim, and a check that read them as two strings would call that a difference and pass a
    restatement.
    """
    return " ".join(said.split()).casefold()


def _every_string_the_architecture_report_says(the_report: ArchitectureReport) -> list[str]:
    """Every string an architecture report carries, in the order the glossary lists them.

    **All five collections.** A restatement can arrive in any of them, and a check pinned to
    one would hear only the arrival it expected.
    """
    said: list[str] = []
    for a_collection in the_report.everything_it_says():
        said.extend(str(one_of_them) for one_of_them in a_collection)
    return said


def _every_string_the_security_report_says(the_report: SecurityReport) -> list[str]:
    """Every string a security report carries, in the fields a reader reads for a conclusion.

    **Three fields of every finding, and not every field.** A `severity` is one of a closed
    set of words and `false_positive_notes` are the notes a reader uses to *dismiss* a
    finding, so both are text a report can share with any other document without either having
    read the other. What the report asserts, what it says it saw and what it advises are the
    three strings that would be here only if the report had been read.

    **The account of a report with no findings is in the list too, and that is what keeps the
    list from being empty.** `SecurityReport` refuses a report with neither findings nor an
    account, so a report reaching here always has something — but a model that found nothing
    puts its only prose in `nothing_found_because`, and a check over zero findings would then
    be about nothing. The account is asked of its first paragraph rather than of the whole
    thing, because the node composes the rest from the inspection and the inspection is shown
    to nobody here.
    """
    said: list[str] = []

    for a_finding in the_report.findings:
        for a_field in ("statement", "signal", "recommendation"):
            the_words = str(getattr(a_finding, a_field)).strip()
            if the_words:
                said.append(the_words)

    if the_report.nothing_found_because:
        the_first_paragraph = the_report.nothing_found_because.strip().split("\n\n", 1)[0].strip()
        if the_first_paragraph:
            said.append(the_first_paragraph)

    return said


def _what_the_two_cards_say_in_common(
    the_architecture_report: ArchitectureReport, the_security_report: SecurityReport
) -> list[tuple[str, str]]:
    """Every sentence of one card that appears word for word in the other, and which is whose.

    **Both directions, because a restatement can go either way.** A security finding that
    restates an architectural risk is a report that reached the risk somehow; an architectural
    risk that restates a finding is a claim about this repository's security made by a stage
    nobody asked about security. Each match is returned with the sentence as it was written
    and the card it came from, so a failure says what repeated rather than only that
    something did.
    """
    the_architect_says = [
        (_as_one_line(one_of_them), one_of_them)
        for one_of_them in _every_string_the_architecture_report_says(the_architecture_report)
    ]
    the_analyst_says = [
        (_as_one_line(one_of_them), one_of_them)
        for one_of_them in _every_string_the_security_report_says(the_security_report)
    ]

    in_common: list[tuple[str, str]] = []
    for the_shape_of_it, as_the_architect_wrote_it in the_architect_says:
        if the_shape_of_it and any(
            the_shape_of_it in said_by_the_analyst for _, said_by_the_analyst in the_analyst_says
        ):
            in_common.append(("the architecture report's", as_the_architect_wrote_it))
    for the_shape_of_it, as_the_analyst_wrote_it in the_analyst_says:
        if the_shape_of_it and any(
            the_shape_of_it in said_by_the_architect
            for _, said_by_the_architect in the_architect_says
        ):
            in_common.append(("the security report's", as_the_analyst_wrote_it))

    return in_common


class WhatTheTwoStagesAnswered(NamedTuple):
    """Both reports and the architect's judgement, in the order this run produced them.

    **The checkout is not carried here and that is deliberate.** Both stages were handed the
    one read-only clone the tests also hold, and every grounding claim below is asked of that
    directory directly — carrying a second reference to it would be two names for one thing,
    and a comparison between two artifacts is only meaningful because both came out of it.

    **The judgement beside the architecture report and not only the report.** Each stage is
    asked three questions about its own work and keeps them beside the document rather than
    among it, and they are part of what has to be compared: an opinion one model reached is
    not something the next model was shown, and a pair carrying only the artifacts could not
    say so.
    """

    the_architecture_report: ArchitectureReport
    what_the_architect_concluded: ArchitectureReportAnswer
    the_security_report: SecurityReport


@pytest.fixture(scope="module")
def what_the_two_stages_answered(
    the_repository: Repository,
    the_cloned_repository: ClonedRepository,
    the_model_for,
    request,
) -> WhatTheTwoStagesAnswered:
    """Two real calls over one read-only clone, and neither handed the other's report.

    **The architect first and the security analyst second, and the order is the argument
    rather than an accident.** A report produced after the other could be a reaction to it, and
    a reader could wonder whether the security report's silence about the architecture came
    from a report that had been written after something. Taking the architecture first means
    the security report could not have been a reaction to it, and two calls that cannot see
    each other are not made different by the order they are made in.

    **Both are the production calls, unchanged.** `analyze_the_architecture` is handed a clone,
    a repository and a model; `inspect_for_security_risk` is handed the same three. No
    stand-in is used for either, because a pair that handed one stage a document the other
    wrote would be measuring a handover this pipeline does not have.

    **The provider is `request.param` and the tests parametrise it indirectly**, so a run
    configured for one provider *skips* the others with the reason printed.
    """
    the_model = the_model_for(request.param)

    the_architecture_report, what_the_architect_concluded = analyze_the_architecture(
        the_cloned_repository, the_repository, the_model
    )
    the_security_report = inspect_for_security_risk(
        the_cloned_repository, the_repository, the_model
    )

    return WhatTheTwoStagesAnswered(
        the_architecture_report=the_architecture_report,
        what_the_architect_concluded=what_the_architect_concluded,
        the_security_report=the_security_report,
    )


@pytest.mark.parametrize("what_the_two_stages_answered", list(LlmProvider), indirect=True)
def test_the_security_analyst_was_asked_about_the_code_and_not_about_the_architecture(
    what_the_two_stages_answered: WhatTheTwoStagesAnswered,
    the_cloned_repository: ClonedRepository,
    the_repository: Repository,
) -> None:
    """The question carries the code and carries no part of the report a person approved.

    **Asked of the prompt, because the prompt is the whole of what this stage was given.** The
    signature takes a clone, a repository and a model, and the caller in production passes
    exactly those; a change that also handed over the `ArchitectureReport` would still
    typecheck, and the security report would then be a reaction to a shape a person had
    already approved rather than a reading of the code — and the gate cannot tell the two
    apart, because both arrive as a `SecurityReport`.

    **Both halves, and the first is what gives the second its meaning.** "The architecture
    report is absent" is satisfied by an empty question, so the question is first required to
    carry the inspection production gave this stage, and the test beside this one checks that
    the inspection carries the code. A prompt that had lost the inspection *and* the report
    would pass a one-sided check, and losing the inspection is the likelier accident, because
    the inspection is the thing the repair replaced.

    **The three sentences of judgement are asked about too, and the architect's question is
    asked for the code section and is expected not to have it.** That is the asymmetry this
    file documents: the two stages read one repository through two selections on purpose, and
    a change that swapped them back would be the defect this repository has already paid for
    once, going the other way.

    **Every string checked for absence is checked verbatim, not as a phrase.** A model writing
    about a boundary in different words is not a handover, and a check that matched on words
    rather than sentences would report one — so a failure here quotes the whole string that
    matched, and a reader who thinks it is a coincidence can see it in the message.
    """
    the_inspection_the_analyst_was_shown = an_inspection_of_the_code(the_cloned_repository)
    what_the_analyst_was_asked = the_prompt_to_inspect_for_security_risk(
        the_inspection_the_analyst_was_shown, the_repository
    )

    assert the_inspection_the_analyst_was_shown in what_the_analyst_was_asked, (
        "the security analyst's question does not carry the inspection it was given, so 'the "
        "architecture report is not in it' below would be true of a question carrying nothing "
        "at all. The prompt is rebuilt here by calling the function the node calls, over the "
        "same clone, so this is the question as it was put and not a reconstruction of it"
    )

    what_the_architect_was_asked = the_prompt_to_analyze_the_architecture(
        an_inspection_of(the_cloned_repository), the_repository
    )
    assert THE_HEADING_NAMING_THE_CODE not in what_the_architect_was_asked, (
        f"{THE_HEADING_NAMING_THE_CODE!r} is in the architect's question. The architect is "
        "handed a repository's shape on purpose — §10 gives it repository questions and a "
        "report of the shape is what a person reads before changing anything — so the two "
        "stages being on two different selections is the design, and this assertion is what "
        "hears it being undone"
    )

    what_the_architecture_report_says = _every_string_the_architecture_report_says(
        what_the_two_stages_answered.the_architecture_report
    )
    assert what_the_architecture_report_says, (
        f"the real architecture report said nothing at all across "
        f"{', '.join(ArchitectureReport.model_fields)}, so every absence below would be the "
        "absence of nothing. `EmptyArchitectureReportError` exists and the node raises it, so a "
        "report reaching here means the refusal is not armed"
    )

    reached_the_analyst = [
        said for said in what_the_architecture_report_says if said in what_the_analyst_was_asked
    ]
    assert not reached_the_analyst, (
        f"{reached_the_analyst!r} is in the security analyst's question. A person approved this "
        "architecture report at the gate immediately before, and the security report the next "
        "gate showed them could not have been informed by it — a finding reasoning about a risk "
        "nobody put in front of it is a finding whose account of the danger came from somewhere "
        "nobody recorded, and both arrive as a `SecurityReport`"
    )

    what_the_architect_judged = what_the_two_stages_answered.what_the_architect_concluded.judged
    for a_judgement in JUDGEMENTS_EVERY_AGENT_MAKES:
        said = getattr(what_the_architect_judged, a_judgement)
        assert said.strip(), (
            f"the architecture analyst left {a_judgement} empty, so there is no opinion of its "
            "own that could be found in the security analyst's question. That absence is correct "
            "and it is also weaker than it looks, which is why it is asserted rather than left "
            "to the loop below"
        )
        assert said not in what_the_analyst_was_asked, (
            f"the architecture analyst's {a_judgement} is in the security analyst's question. A "
            "stage asked to find risk in code, holding another model's opinion of the shape, "
            "produces a report that reasons about a conclusion rather than about the files — "
            "and the architect's note is the one place that opinion appears, so a reader of the "
            "security report has no way to know how much of it came from there"
        )


@pytest.mark.parametrize("what_the_two_stages_answered", list(LlmProvider), indirect=True)
def test_the_inspection_the_security_analyst_read_carries_the_code_and_says_what_it_left_out(
    what_the_two_stages_answered: WhatTheTwoStagesAnswered,
    the_cloned_repository: ClonedRepository,
) -> None:
    """The code is really in it, and the closing section is the account of what was not shown.

    **This is the positive half of the finding, and it needs no model.** The defect this pair
    exists for was a stage asked to find authentication problems while holding a directory
    listing and a `package.json`, and nothing about that is visible in what a model then said:
    a report reasoning from a filename and a report reasoning from the file read exactly
    alike on a card. So the claim is asked of the tool, where it is a fact rather than a
    judgement — the inspection a real run handed this analyst ends with the two sections
    production adds, and at least one file it carries is a file of this checkout whose own text
    is inside it.

    **The file-with-its-text check is the one that cannot be satisfied by a longer string.** A
    selection that grew by listing more names would pass a length comparison and fail this,
    because a path in a heading is a name and the file's text is the evidence. That is also
    why the question is which of the headings is a file rather than how many there are: a
    `Dockerfile` comment begins with a hash and reads as a heading, so counting headings would
    be counting the code as well as the selection of it.

    **The two added sections are placed rather than counted, and the reason is in the check.**
    A Dockerfile comment and a README's own `##` headings mean the number of markdown headings
    in this text is not the number of sections in it, so what is asserted is that each of the
    two sections production adds is present here and absent from the discovery inspection, and
    then where each of them begins: the code after everything discovery was shown, the account
    after the code, the account carrying a body, and no file of the checkout named below it. A
    fourth section added later would break one of those rather than being absorbed — and the
    presence assertions come before the positions are read off the text, because an
    `IndexError` from a section that is simply gone is not a message a reader of a red run can
    do anything with.

    **The short inspection is a strict prefix of the long one, and that is what makes this a
    statement about addition rather than about difference.** It is why the architect's question
    is checked above for the code section and is expected not to have it: the two stages read
    the same repository through two different selections, and the reason the security
    analyst's is longer is the reason its report can be held to the code.

    **The only thing asked of the real run is that the report exists.** Every fact below is
    read off the filesystem, and the run is what makes this a real repository rather than a
    fixture — a check over a hand-built directory would pass for the wrong reason.
    """
    the_short_inspection = an_inspection_of(the_cloned_repository)
    the_long_inspection = an_inspection_of_the_code(the_cloned_repository)

    assert the_short_inspection in the_long_inspection, (
        "the inspection the security analyst is handed is not the discovery inspection plus "
        "something. The two were meant to be the same sections in the same order with the code "
        "and the account of what was withheld added, and if that is no longer true then the "
        "two stages are being shown two different repositories' worth of facts and the "
        "comparison between their reports is a comparison of two questions"
    )
    assert len(the_long_inspection) > len(the_short_inspection), (
        f"the security analyst is being shown {len(the_long_inspection)} characters and "
        f"discovery {len(the_short_inspection)}. The defect this pair was written for was a "
        "security report reasoned from a directory listing, and a selection that had stopped "
        "growing would bring that back with nothing in the report to show for it"
    )

    for a_heading_production_adds, what_that_heading_names in (
        (THE_HEADING_NAMING_THE_CODE, "the code this selection carries"),
        (THE_HEADING_NAMING_WHAT_WAS_LEFT_OUT, "the account of what it withheld"),
    ):
        assert a_heading_production_adds in the_long_inspection, (
            f"{a_heading_production_adds!r} is nowhere in the inspection the security analyst is "
            f"shown, so {what_that_heading_names} is not in the question at all. A report cannot "
            "be held to evidence it was not given, and a model told its own limits in a prompt "
            "but not shown them has been told nothing it can check itself against"
        )
        assert a_heading_production_adds not in the_short_inspection, (
            f"{a_heading_production_adds!r} is in the discovery inspection too, so the two "
            "stages are no longer on two different selections and the defect this repository "
            "already paid for once has come back"
        )

    the_code_section_begins_at = the_long_inspection.index(THE_HEADING_NAMING_THE_CODE)
    the_account_begins_at = the_long_inspection.index(THE_HEADING_NAMING_WHAT_WAS_LEFT_OUT)

    assert the_code_section_begins_at > len(the_short_inspection), (
        f"{THE_HEADING_NAMING_THE_CODE!r} is inside the discovery inspection, so the security "
        "analyst is being shown the shape rather than the code — which is the defect this "
        "repository already paid for once, a report refused for reasoning from filenames and "
        "dependency declarations alone"
    )
    assert the_account_begins_at > the_code_section_begins_at, (
        f"{THE_HEADING_NAMING_WHAT_WAS_LEFT_OUT!r} comes before the code it is accounting for. "
        "The closing section is what makes a finding about a withheld file visibly a finding "
        "about nothing, and a model that reads it first has been told its limits before it has "
        "been shown what it may reason about"
    )
    assert the_long_inspection[
        the_account_begins_at + len(THE_HEADING_NAMING_WHAT_WAS_LEFT_OUT) :
    ].strip(), (
        f"{THE_HEADING_NAMING_WHAT_WAS_LEFT_OUT!r} is a heading with nothing under it. A model "
        "shown a section that names no file cannot tell a repository whose risk-relevant files "
        "were all shown from one whose were not, and the whole of the fix is that this section "
        "says which"
    )

    files_named_after_the_account = [
        a_path
        for a_path in A_HEADING.findall(the_long_inspection[the_account_begins_at:])
        if (the_cloned_repository.path / a_path).is_file()
    ]
    assert not files_named_after_the_account, (
        f"{files_named_after_the_account} are shown after the account of what was withheld, so "
        "the account is not the closing section and a model reading it could believe a file was "
        "left out that is in fact below it. The claim that a report may be held to its own "
        "coverage rests on that section being the last thing in the question"
    )

    what_follows_the_code_section = A_HEADING.findall(
        the_long_inspection[the_code_section_begins_at:]
    )
    the_files_shown_with_their_own_text = [
        a_path
        for a_path in what_follows_the_code_section
        if (the_cloned_repository.path / a_path).is_file()
        and (the_cloned_repository.path / a_path).read_text(encoding="utf-8", errors="replace")
        in the_long_inspection
    ]
    assert the_files_shown_with_their_own_text, (
        f"{len(what_follows_the_code_section)} heading(s) follow the code section and not one of "
        "them is a file of this checkout whose own text is inside the inspection. Some of those "
        "headings are lines of the code itself — a Dockerfile comment reads as a heading — which "
        "is why the question is which of them is a file rather than how many there are. A path "
        "in a heading is a name, and a security finding reasoning from a name is the defect this "
        "file exists to keep fixed: the selection is asserted to carry evidence, and not to "
        "carry more text"
    )

    assert isinstance(what_the_two_stages_answered.the_security_report, SecurityReport), (
        f"the stage answered with "
        f"{type(what_the_two_stages_answered.the_security_report).__name__} rather than the "
        "artifact a gate presents"
    )


@pytest.mark.parametrize("what_the_two_stages_answered", list(LlmProvider), indirect=True)
def test_every_finding_grounds_its_signal_in_the_clone_the_analyst_read(
    what_the_two_stages_answered: WhatTheTwoStagesAnswered,
    the_cloned_repository: ClonedRepository,
) -> None:
    """Every path a finding quotes is one the analyst could have read, in the checkout it read.

    **The artifact a gate holds and cannot check is the one this is about.** A
    `SecurityReport` has no field naming a file, so the only thing a reader can hold it to is
    its own prose, and a path in that prose which is nowhere in the checkout was invented or
    remembered from another repository. **A security report quoting code that does not exist is
    the most persuasive kind of fiction there is** — and this report is the only place a
    person will read about the risk, because the stage that acts on the change is never shown
    it.

    **The three grounds are imported rather than copied, and the cost is written down.** They
    are one rule about a checkout rather than two facts about a pair, and a second copy of a
    three-ground rule is a second rule that can drift from the first. What that gives up is
    this: a defect in the shared helper is a defect in both files at once, and the file that
    would hear about it is `test_inspect_for_security_risk.py` — which is why the grounds' own
    reasoning is read there rather than restated here, including the one that matters most,
    that a repository *declaring* a file is not the same thing as containing one. The first
    version of a copy of that check called such a path a fabrication, twice, and was wrong both
    times.

    **Only the words naming a directory are asked about, and that is a narrowing with a cost.**
    `payload.sub` is a field in a request body and `middleware.ts` is a file this repository
    has under a deeper path, so a bare dotted word is a location about half the time and an
    assertion about half the time is not an assertion. What it gives up is a fabrication named
    only by its own file name, and that is recorded here rather than left to whoever reads the
    next red run.

    **The count of candidates asked about is asserted, and a run that gives none fails rather
    than skips.** An empty candidate set compared against an empty checkout finds nothing
    wrong with anything, and a green tick about a rule that was never applied is the one thing
    this tier is not allowed to produce. The sibling file says the same about itself: this
    deployment's model grounds a signal in a file it *read* and names it by its own name at
    least as often as by its path, so the honest outcome on some runs is a failure.
    """
    the_report = what_the_two_stages_answered.the_security_report

    if not the_report.findings:
        pytest.skip(
            "a real security analyst examined this repository and reported no findings, so there "
            "is no signal to hold to the checkout. That is a defensible answer for a repository "
            "with no visible risk — §10 calls this analysis advisory rather than a replacement "
            "for a scanner — and the report says so in words rather than in silence."
        )

    ungrounded: list[tuple[str, str]] = []
    were_asked_about = 0

    for a_finding in the_report.findings:
        for a_candidate in A_PATH_IN_A_QUOTE.findall(a_finding.signal):
            if "/" not in a_candidate:
                continue
            were_asked_about += 1
            is_grounded, why = _the_analyst_had_grounds_to_name(the_cloned_repository, a_candidate)
            if not is_grounded:
                ungrounded.append((a_candidate, why))

    assert not ungrounded, (
        f"{sorted({a_candidate for a_candidate, _ in ungrounded})} are quoted as evidence in a "
        "report a gate holds beside an architecture report about this same checkout, and the "
        "analyst had no way to have read them: "
        + "; ".join(f"{a_candidate} — {why}" for a_candidate, why in ungrounded)
        + ". Either the model invented them or it remembered another repository — and this is "
        "the only place a person will read about the risk, because the stage that acts on the "
        "change is never shown this report. `an_inspection_of_the_code` is what prevents it, by "
        "carrying the code and naming what it left out."
    )

    assert were_asked_about, (
        f"no finding in this report quoted a path with a directory in it, so the check above "
        f"compared an empty set against an empty checkout and found nothing wrong with any of "
        f"the {len(the_report.findings)} finding(s). That is a green tick about a rule that was "
        "never applied, and it is the honest outcome rather than a flaky one: this "
        "deployment's model grounds a signal in a file it read and names it by its own name at "
        "least as often as by its path, so some runs give a checkable candidate and some do "
        "not. A run that gives none is a run this tier cannot say anything about, and saying "
        "so is the finding."
    )


@pytest.mark.parametrize("what_the_two_stages_answered", list(LlmProvider), indirect=True)
def test_the_security_report_repeats_no_sentence_of_the_architecture_report(
    what_the_two_stages_answered: WhatTheTwoStagesAnswered,
) -> None:
    """Neither card says what the other said, in either direction.

    **This is what a gate can do with two approved cards and no model to ask.** It can ask
    whether one document contains the other's text; it cannot ask whether a finding is *about*
    the same risk as a boundary written in other words, because that is a judgement about
    meaning and a second model asked to make it would be a model grading a model. So the claim
    is the one that survives, and it is not a weak one here: a security finding that restates
    an architectural risk sentence for sentence is a report that reached the risk somehow, and
    the two calls that could have done it share nothing but a directory.

    **The layout goes before the comparison, so a line break is not a difference.** A risk
    printed as two lines and a finding printed as one is the same claim, and a check that read
    them as different strings would pass a restatement.

    **Both lists are non-empty on every run that reaches here, and that is what keeps the
    comparison from being about nothing.** `ArchitectureReport` refuses a report empty in all
    five fields and `SecurityReport` refuses one with neither findings nor an account, so each
    document carries real text — and the assertions say so rather than trusting a validator two
    modules away.
    """
    the_architecture_report = what_the_two_stages_answered.the_architecture_report
    the_security_report = what_the_two_stages_answered.the_security_report

    assert _every_string_the_architecture_report_says(the_architecture_report), (
        f"the real architecture report said nothing at all across "
        f"{', '.join(ArchitectureReport.model_fields)}, so there is no sentence of it that "
        "could be a repetition"
    )
    assert _every_string_the_security_report_says(the_security_report), (
        f"the real security report has {len(the_security_report.findings)} finding(s) and "
        f"{'an' if the_security_report.nothing_found_because else 'no'} account of what was "
        "examined, so it says nothing a repetition could be measured against. "
        "`EmptySecurityReportError` exists for that and the node raises it, so a report "
        "reaching here means the refusal is not armed"
    )

    in_common = _what_the_two_cards_say_in_common(the_architecture_report, the_security_report)
    assert not in_common, (
        f"{in_common} is in both cards. The security analyst is handed a clone and a repository "
        "and no architecture report, and a person approved that report at the gate immediately "
        "before — so a finding repeating a sentence of it is a finding that reached the report "
        "somehow, and a gate holding both cards cannot see the route it took"
    )
