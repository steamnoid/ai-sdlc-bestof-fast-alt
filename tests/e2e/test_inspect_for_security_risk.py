"""The security analyst, against a real model and a real repository.

**This is the stage whose inspection a real run had to change, and the change is why it is
the one worth proving alone.** `an_inspection_of` was built for *discovery* — a repository's
shape, its own docstring saying source files are deliberately not in it — and this analyst was
later wired to the same one. It was therefore asked to find authentication and authorization
problems while being handed a directory listing and a `package.json`, and a run's gate refused
the report for exactly that:

    "Six of the seven entries are then speculation from filenames and dependency
     declarations alone (findings 4, 5 and 7 reason from `Dockerfile`, `.dockerignore` and
     `bcryptjs` to MCP-endpoint, image-hygiene and cost-factor conclusions the report itself
     calls 'undecidable from the manifest')"

The same model on the same repository then produced 7 findings every one of which quoted code,
and 10,835 characters of evidence where there had been 1,434.

**So the assertion that matters here is that every finding's evidence is a file of the clone
the run made.** A signal quoting a line that is not there was either invented or remembered
from another repository, and a security report quoting code that does not exist is the most
persuasive kind of fiction there is. This is checkable because the substrate is a checkout on
disk, and it is the reason the inspection carries file contents and names what it left out.

**Findings are not required to be found, but an empty report is still a fault.** §10 calls this
analysis advisory rather than a replacement for a scanner, so the artifact is defensible with
little in it — and it carries `nothing_found_because` for that case. The node refuses a report
empty in every field, so a run reaching this assertion has either reported something or failed
loudly, and the test says which rather than passing on silence.
"""

from __future__ import annotations

import re

import pytest

from aisdlc.agents.inspect_for_security_risk import inspect_for_security_risk
from aisdlc.agents.security_report import SecurityReport
from aisdlc.agents.severity import Severity
from aisdlc.domain.repository import Repository
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository

pytestmark = pytest.mark.e2e

A_PATH_IN_A_QUOTE = re.compile(r"[`\"']([\w./-]+\.[A-Za-z]{1,5})[`\"']")
"""A path as a model writes one: a slash-separated word ending in something extension-shaped.

Matched loosely on purpose — the question is whether the *candidate* resolves in the clone, and
a path that does not is a finding whatever it is called. A quote is not required: grounding in
a document is a real signal about a real file, and refusing that would leave this agent with
nothing to report.
"""


@pytest.fixture(scope="module")
def a_real_report(
    the_repository: Repository,
    the_cloned_repository: ClonedRepository,
    the_model_for,
    request,
) -> SecurityReport:
    """One real analysis, shared by every assertion about it."""
    return inspect_for_security_risk(
        the_cloned_repository, the_repository, the_model_for(request.param)
    )


@pytest.mark.parametrize("a_real_report", list(LlmProvider), indirect=True)
def test_a_real_model_weighs_every_finding_it_reports(
    a_real_report: SecurityReport, the_placeholders: frozenset[str]
) -> None:
    """Every finding carries its weighing, and none of its five fields is a shape.

    **Per field rather than "the report is non-empty", because the value of an advisory report
    is in the weighing.** A finding with an empty `false_positive_notes` is a finding a reader
    cannot dismiss and therefore will not dismiss — it is the difference between a report and a
    list of worries, and it is the field the artifact exists to require.
    """
    assert isinstance(a_real_report, SecurityReport), (
        f"the stage answered with {type(a_real_report).__name__} rather than the artifact a gate "
        "presents"
    )

    assert a_real_report.findings or a_real_report.nothing_found_because, (
        "the run reached this assertion with no findings and no reason, which means the node did "
        "not refuse an empty report — and an empty security report with no reason reads as safety"
    )

    for a_finding in a_real_report.findings:
        for a_field in ("statement", "signal", "false_positive_notes", "recommendation"):
            said = str(getattr(a_finding, a_field))
            assert said.strip(), (
                f"a finding left {a_field} empty, so a reader cannot weigh it. This is the field "
                "that makes a security report a report: a finding nobody can dismiss is a finding "
                "nobody will dismiss"
            )
            assert said.strip().lower() not in the_placeholders, (
                f"{said!r} is placeholder text in {a_field} of a finding, which means the model "
                "returned a shape rather than a finding"
            )


@pytest.mark.parametrize("a_real_report", list(LlmProvider), indirect=True)
def test_no_finding_quotes_a_file_the_run_never_saw(
    a_real_report: SecurityReport, the_cloned_repository: ClonedRepository
) -> None:
    """The grounding assertion, and the one that makes a signal mean anything.

    A signal quoting a path that is not in the clone was invented or remembered from elsewhere.
    A signal naming a file that *is* there is fine even when the file holds a document rather
    than code, because grounding in what the analyst was shown is the most it can honestly do
    and refusing that would leave it with nothing.
    """
    invented: list[str] = []

    for a_finding in a_real_report.findings:
        for a_quoted in A_PATH_IN_A_QUOTE.findall(a_finding.signal):
            if not (the_cloned_repository.path / a_quoted).is_file():
                invented.append(a_quoted)

    assert not invented, (
        f"{sorted(set(invented))} are quoted as evidence in a security report produced from a "
        "clone that does not contain them. Either the model invented them or it remembered "
        "another repository — and a security report quoting code that is not there is the most "
        "persuasive kind of fiction there is. This is what `an_inspection_of_the_code` exists to "
        "prevent, by carrying the code and naming what it left out."
    )


@pytest.mark.parametrize("a_real_report", list(LlmProvider), indirect=True)
def test_a_severity_is_one_of_the_levels_a_card_can_read(a_real_report: SecurityReport) -> None:
    """Every finding's severity is a level, so a board can order on it and a card can colour it.

    **The severity is a word a person's card shows, and a card is the only interface most people
    will ever have to this system.** An arbitrary string is a card that says `moderate-ish`, and
    one that says nothing is a card whose colour the board has to invent. The set is read off
    `Severity` rather than restated, so a level added there is allowed here without this test
    being edited — which is the point of putting the closed set in the domain.
    """
    for a_finding in a_real_report.findings:
        assert isinstance(a_finding.severity, Severity), (
            f"{a_finding.severity!r} is not a {Severity.__name__}. A severity is shown on a card "
            "and used to order a board, and a value nobody defined is a card a person has to "
            "interpret for themselves"
        )
