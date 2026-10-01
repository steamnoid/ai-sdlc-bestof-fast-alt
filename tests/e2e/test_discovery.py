"""Repository discovery, against a real model and a real repository.

**This is the stage every other stage's evidence comes from, so it is the one this file
proves alone first.** A real public repository is cloned with real `git` over a real network,
inspected by the real selection, and read by a real model obtained through the real factory —
the whole chain, because a discovery report is the only artifact in this system whose claims
are about a repository nobody in the run has read.

**Nothing here asserts content.** Real output varies per run, and a test that pinned the
words a model chose would fail every time the model was different without ever finding a
defect. What is asserted is the contract, and there are four of it: the answer validated
into the artifact, the fields a real repository must have are filled, nothing came back as a
placeholder, and — the one that matters most — **every path the report names is a file that
really exists in the clone the run made**.

That last assertion is what separates a discovery report from a plausible paragraph. A model
asked to name files will name files, and naming files it never read is the failure mode a
summary of a repository cannot be checked for. Here the check is mechanical: the clone is on
disk, and the paths are looked up in it.

**The provider is a parameter rather than a constant, so proving a second one is a different
run and not a rewritten test.** A provider the deployment is not configured for says so out
loud rather than passing quietly — a green run that never called a model is the failure this
tier exists to prevent.
"""

from __future__ import annotations

import pytest

from aisdlc.agents.discover_the_repository import discover_the_repository
from aisdlc.agents.discovery_answer import DiscoveryAnswer
from aisdlc.agents.discovery_report import DiscoveryReport
from aisdlc.domain.repository import Repository
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository

pytestmark = pytest.mark.e2e

MUST_BE_FILLED = ("languages", "architecture_summary", "evidence_files")

JUDGEMENTS_THE_DISCOVERY_ANSWER_MAKES = ("what_it_found", "what_it_could_not_settle")


@pytest.fixture(scope="module")
def a_real_discovery(
    the_repository: Repository,
    the_cloned_repository: ClonedRepository,
    the_model_for,
    request,
) -> tuple[DiscoveryReport, DiscoveryAnswer]:
    """One real discovery, shared by every assertion about it.

    Module scope, because a clone and a model call are the expensive parts and the four
    assertions below are four different contracts about *one* report. Asserting separately
    about separate runs would only prove the model answers differently each time, which is
    true and not what this file is for.

    **The provider is `request.param` and the tests parametrise it indirectly**, so a run
    configured for one provider *skips* the others with the reason printed.
    """
    return discover_the_repository(
        the_cloned_repository, the_repository, the_model_for(request.param)
    )


@pytest.mark.parametrize("a_real_discovery", list(LlmProvider), indirect=True)
def test_a_real_model_describes_a_real_repository(
    a_real_discovery: tuple[DiscoveryReport, DiscoveryAnswer], the_placeholders: frozenset[str]
) -> None:
    """The answer validated into the artifact, and the fields a repository must have are filled.

    **A field left empty is a field the gate presents to a person as though it had been
    read.** A discovery report with no `architecture_summary` is a document a person is asked
    to approve, so the assertion is on the fields rather than on the report being non-empty:
    a report whose only content is a language list is a document and not a description.
    """
    the_report, the_answer = a_real_discovery

    assert isinstance(the_report, DiscoveryReport), (
        f"the stage answered with {type(the_report).__name__} rather than the artifact a gate "
        "presents, so nothing downstream can rely on which fields it carries"
    )
    assert isinstance(the_answer, DiscoveryAnswer), (
        "the judgement beside the artifact is not the answer type, so the note a person reads "
        "on the card is not the one the model reached"
    )

    for field in MUST_BE_FILLED:
        said = getattr(the_report, field)
        assert said, (
            f"a real repository was discovered and {field} is empty. That is the field a person "
            "reads first, and a document with a hole in it is a document nobody can approve on "
            "the evidence"
        )
        if isinstance(said, list):
            for one_of_them in said:
                assert str(one_of_them).strip().lower() not in the_placeholders, (
                    f"{one_of_them!r} in {field} is placeholder text, which means the model "
                    "returned a shape rather than a finding"
                )
        else:
            assert str(said).strip().lower() not in the_placeholders, (
                f"{said!r} in {field} is placeholder text, which means the model returned a "
                "shape rather than a finding"
            )

    for judgement in JUDGEMENTS_THE_DISCOVERY_ANSWER_MAKES:
        said = getattr(the_answer.judged, judgement)
        assert said.strip(), (
            f"the discovery agent left {judgement} empty. It is one of only two agents that see "
            "a whole repository, so its doubt is the widest the run has, and an empty one reads "
            "as a doubt nobody had"
        )


@pytest.mark.parametrize("a_real_discovery", list(LlmProvider), indirect=True)
def test_every_file_the_report_cites_really_exists_in_the_clone(
    a_real_discovery: tuple[DiscoveryReport, DiscoveryAnswer],
    the_cloned_repository: ClonedRepository,
) -> None:
    """The grounding assertion, and the one that makes a cited file mean something.

    A real model cited a directory once, and the link in the report resolved to nothing
    while looking exactly like a link — which is why a directory is refused the same way a
    missing file is. The node checks this before the report exists; asserting it here is a
    second, independent check that the check is armed, because a test that trusted the node
    would pass on a node whose check was commented out.
    """
    the_report, _ = a_real_discovery

    assert the_report.evidence_files, (
        "the report cites nothing, so its conclusions rest on evidence nobody can look at — and "
        "a report with no citations is a paragraph"
    )

    cited_paths = [a_citation.path for a_citation in the_report.evidence_files]
    not_in_the_clone = [
        a_path for a_path in cited_paths if not (the_cloned_repository.path / a_path).is_file()
    ]

    assert not not_in_the_clone, (
        f"{not_in_the_clone} are cited as evidence in a report produced from a clone that does "
        "not hold them. Either the model invented them or it remembered another repository, and "
        "a link shaped exactly like a link to a file is the most persuasive kind of fiction "
        "there is. `CitedFileNotFoundError` exists for this and the node raises it; a report "
        "reaching this assertion means the check either is not armed or was made a warning."
    )


@pytest.mark.parametrize("a_real_discovery", list(LlmProvider), indirect=True)
def test_every_cited_file_carries_an_address_this_system_derived(
    a_real_discovery: tuple[DiscoveryReport, DiscoveryAnswer], the_repository: Repository
) -> None:
    """Every citation points at the repository, and none of them at a host the model liked.

    `DiscoveryAnswer` has no field an address could arrive in, so a link in the report is one
    this system built. Asserting it is a check on that: an address reaching the artifact
    anyway — through a model that filled a field that does not exist, or through a type that
    grew one — would put a reviewer's link on a page about somebody else's repository.
    """
    the_report, _ = a_real_discovery

    wrong = [
        a_citation.link
        for a_citation in the_report.evidence_files
        if the_repository.address not in a_citation.link
    ]

    assert not wrong, (
        f"{wrong} are not addresses of {the_repository.address}. The system derives every link "
        "from the repository it cloned, so a link pointing elsewhere is either a host a model "
        "invented or a derivation reading the wrong repository — and both put a reviewer's "
        "click on the wrong page while looking like a link"
    )


@pytest.mark.parametrize("a_real_discovery", list(LlmProvider), indirect=True)
def test_the_report_is_the_artifact_and_the_judgement_stayed_beside_it(
    a_real_discovery: tuple[DiscoveryReport, DiscoveryAnswer], the_placeholders: frozenset[str]
) -> None:
    """The three sentences of judgement are not inside the document a person approves.

    **A structural assertion, and the reason it is here rather than a prose one.** The
    artifact is what a gate presents and what an `Approval` names with a version; the
    judgement is what a person and the repair supervisor read afterwards. Putting the second
    inside the first would put three sentences no human ruled on inside a document they are
    asked to rule on — and the version an approval is invalidated by would then cover a
    document containing material the decision was never about.

    Asserted by reading the artifact's own fields rather than by looking for a name, so a
    type that quietly gained a `judged` is caught whichever way it was spelled.
    """
    _, the_answer = a_real_discovery

    assert "judged" not in DiscoveryReport.model_fields, (
        "DiscoveryReport now carries the judgement. A gate presents this artifact and an "
        "Approval names it with a version, so a document that also carries a model's opinion of "
        "its own contents is a document whose version covers material the decision was not about"
    )

    the_fields_the_glossary_names = {
        "languages",
        "frameworks",
        "build_system",
        "ci_system",
        "architecture_summary",
        "key_components",
        "evidence_files",
        "suggested_changes",
    }
    added = set(DiscoveryReport.model_fields) - the_fields_the_glossary_names
    assert not added, (
        f"DiscoveryReport now carries {sorted(added)}. The glossary names eight fields and a "
        "person is asked to approve exactly those, so a field added here is material in front "
        "of a gate that no rule asked for"
    )

    for judgement in JUDGEMENTS_THE_DISCOVERY_ANSWER_MAKES:
        said = getattr(the_answer.judged, judgement)
        assert said.strip().lower() not in the_placeholders, (
            f"{said!r} is placeholder text in {judgement}, which means the model returned a "
            "shape rather than a judgement"
        )
