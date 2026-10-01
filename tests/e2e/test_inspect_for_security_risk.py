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
from aisdlc.tools.inspect_the_repository import an_inspection_of_the_code

pytestmark = pytest.mark.e2e

A_PATH_IN_A_QUOTE = re.compile(r"[`\"']([\w./-]+\.[A-Za-z]{1,5})[`\"']")
"""A candidate path as a model writes one: a dotted word, sometimes with a directory in front.

**This is a *candidate*, and the cost of a false accusation here is that it reads as a fact.**
Two of the words this deployment's model actually produced are not paths at all: `middleware.ts`
was `web-app/src/middleware.ts` named by its own last segment, and `payload.sub` was a **field in
a request body** — a property of an object, not a file anywhere. Refusing those is a claim about
the model that is simply false, and a test that cries fabrication about a real run is a test
nobody reads the second time. So the candidate is handed to `_the_analyst_had_grounds_to_name`,
which asks three questions and says which are cheap.
"""


def _the_analyst_had_grounds_to_name(clone: ClonedRepository, a_candidate: str) -> tuple[bool, str]:
    """Whether this quoted word is something the analyst could have read, and which ground says so.

    **Three grounds, and the third is the one the obvious check gets wrong.** A path is grounded
    if the checkout holds it, or if a file of the checkout is called exactly that, **or if the
    analyst was shown the word itself**. That last one exists because a repository *declaring* a
    file is not the same as containing one — this repository's own `tests/e2e/infra/env.ts` says
    `path.resolve(process.cwd(), "tests/e2e/data/e2e.db")` and that database is created by a test
    run rather than committed, so asking whether the file is there answers no for a path the
    analyst read with its own eyes. **The first version of this check called that a fabrication,
    twice, and was wrong both times.**

    **A candidate with no directory in it is not asked about at all**, and that is the honest
    narrowing: a bare dotted word is a location about half the time, and an assertion about half
    the time is not an assertion. `payload.sub` is the case. What that gives up is a fabrication
    named only by its own file name, and the cost is written here rather than left to be
    discovered by whoever reads the next red run.

    **`rglob` refuses a pattern with a directory in it**, so the bare-name ground guards its own
    condition rather than trusting the caller — and a model quoting `` `/etc/shadow.yaml` `` is
    quoting an absolute path, which is not a path in a checkout either, so the third ground is
    the only one that can answer it.
    """
    if (clone.path / a_candidate).is_file():
        return True, "the checkout holds a file at that path"

    if "/" not in a_candidate and any(
        an_ordinary_file.is_file() for an_ordinary_file in clone.path.rglob(a_candidate)
    ):
        return True, "a file of the checkout is called that, so the analyst saw the name"

    if a_candidate in an_inspection_of_the_code(clone):
        return True, "the analyst was shown the word itself, in a repository that declares it"

    return False, (
        "not a file of the checkout, not a name any file of the checkout carries, and not a word "
        "the analyst was shown — so it was invented, or remembered from another repository"
    )


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

    **Three grounds rather than one, and each is asked of the clone rather than assumed.** A
    signal naming a file that is *there* is fine even when the file holds a document rather than
    code, because grounding in what the analyst was shown is the most it can honestly do. A
    signal naming a file the checkout *declares* — `path.resolve(…, "tests/e2e/data/e2e.db")`
    in a file of its own, where the database is made by a test run and not committed — is
    equally fine, and the first version of this test called that a fabrication twice.

    **Only candidates naming a directory are asked about at all**, which is the narrowing and its
    cost together: `payload.sub` is a field in a request body, and `middleware.ts` is a file this
    repository has under a deeper path. A bare dotted word is a location about half the time, and
    this test is not going to accuse a model of inventing a property.

    **The reasons come back with the verdict**, so a failure says which of the three grounds was
    tried and why none of them answered — rather than a reader having to go and re-derive it.
    """
    ungrounded: list[tuple[str, str]] = []
    were_asked_about = 0

    for a_finding in a_real_report.findings:
        for a_candidate in A_PATH_IN_A_QUOTE.findall(a_finding.signal):
            if "/" not in a_candidate:
                continue
            were_asked_about += 1
            is_grounded, why = _the_analyst_had_grounds_to_name(the_cloned_repository, a_candidate)
            if not is_grounded:
                ungrounded.append((a_candidate, why))

    assert not ungrounded, (
        f"{sorted({a_candidate for a_candidate, _ in ungrounded})} are quoted as evidence in a "
        "security report produced from a clone that does not contain them: "
        + "; ".join(f"{a_candidate} — {why}" for a_candidate, why in ungrounded)
        + ". Either the model invented them or it remembered another repository — and a security "
        "report quoting code that is not there is the most persuasive kind of fiction there is. "
        "This is what `an_inspection_of_the_code` exists to prevent, by carrying the code and "
        "naming what it left out."
    )

    assert were_asked_about, (
        "no finding in this report quoted a path with a directory in it, so the check above "
        "compared an empty set against an empty checkout and found nothing wrong with any of "
        "them. That is a green tick about a rule that was never applied. **This assertion fails "
        "on a real run, and it is the honest outcome rather than a flaky one:** this deployment's "
        "model grounds a signal in a file it *read* and names it by its own name at least as "
        "often as by its path, so some runs give a checkable candidate and some do not. A run that "
        "gives none is a run this tier cannot say anything about, and saying so is the finding — "
        "which is why it is a failure and not a skip. Narrowing further to admit a bare name when "
        "the clone's own files end in that extension would close most of the gap, and would also "
        "start asking about `payload.sub` again, so the trade is written down here rather than "
        "taken silently."
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
