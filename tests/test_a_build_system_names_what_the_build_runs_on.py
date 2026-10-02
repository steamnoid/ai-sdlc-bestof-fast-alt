"""A build system is what the build *runs*, and one word is not that.

**A real run was refused at its very first gate over this, and the refusal named the field.**
Asked to add an `engines` field naming the Node version, the run stopped at discovery:

> The report never records the runtime floors that would bound an engines range … Add a finding
> stating which Node versions the repo actually builds and runs against, with evidence links.

Then it was tried again and refused the same way. So I read what the report actually said, and
this is what it said:

    build_system = "npm"

**One word, and it is true.** `wellbeing-tracker-public` builds with npm — and the same
repository's `Dockerfile` pins `node:22-bookworm` in two `FROM` lines, the report's own
`key_components` carries that Dockerfile, and the report's `architecture_summary` describes the
two-stage image in detail. **Every fact a person needs to rule on "name the version this project
requires" was in the report — in a field nobody asked for, while the field named `build_system`
held one word.**

**This is the same shape as the whitespace finding, one level up.** There, a field of `" "`
validated as an answer because the emptiness rule asked whether the *artifact* said anything. Here
a field of `"npm"` validates as an answer because the rule asks whether anything was *said*, and
nothing asks whether it was enough. `build_system` is `str | None`: one word and a whole
deployment description are both structurally acceptable, and the model takes the shortest true
answer, which is exactly what a model asked a noun will do.

**Two tests, because the claim has two halves and one of them costs a model to check.** The
prompt is asserted here with no model at all, because the question is what is being asked and the
question is a string. The compliance is asserted in `tests/e2e/test_discovery.py`, against a
repository that pins a version, because *whether a model follows a well-asked question* is a fact
about a model and about a real repository and not about a constant.

**Not asserted: that the answer be exhaustive.** A build system in a large repository has more
than one dimension, and a test demanding all of it would be demanding a format rather than a
fact. What is demanded is the one thing a gate cannot proceed without — the thing the repository
itself pins.
"""

from __future__ import annotations

import pytest

from aisdlc.agents.discover_the_repository import the_prompt_to_discover_a_repository
from aisdlc.domain.repository import Repository

A_REPOSITORY = Repository(owner="paligakrzychu", name="wellbeing-tracker-public")


def test_the_question_asks_the_build_system_to_name_what_the_build_runs_on() -> None:
    """`build_system` is asked as a noun, and a noun comes back one word long.

    **Asserted on the question, which is a string, so no model is needed to check it.** The
    defect is not that the model answered briefly; it is that the question made a brief answer
    sufficient. The model was asked to *name* a build system and answered `npm`, which is the
    most obedient answer available and carries none of the information the gate needs.

    **The words are looked for rather than the field's name, because the field name is already
    present and already passes.** The claim is about what the question demands, and a test that
    only checked `build_system` was named would be satisfied by the question that produced the
    one-word answer.
    """
    the_question = the_prompt_to_discover_a_repository("the inspection", A_REPOSITORY)
    what_it_says_about_the_build_system = _what_the_question_says_about_a_build_system(the_question)

    names_the_field = "build_system" in what_it_says_about_the_build_system
    asks_for_a_version = "version" in what_it_says_about_the_build_system
    asks_for_a_runtime = "runtime" in what_it_says_about_the_build_system

    assert names_the_field and asks_for_a_version and asks_for_a_runtime, (
        f"the question names the field: {names_the_field}, asks for a version: "
        f"{asks_for_a_version}, asks for a runtime: {asks_for_a_runtime}. It does not say so, so "
        "the answer that came back was `npm` — one word, and the shortest true one. Everything a "
        "gate needs to rule on a change about a required runtime was in the report and in no field "
        "anybody asked for: the repository's Dockerfile pins node:22-bookworm in two FROM lines, "
        "that Dockerfile is in the report's own key_components, and the architecture_summary "
        "describes the two-stage image in detail. A refusal at that gate said the report 'never "
        "records the runtime floors that would bound an engines range', twice, and it was right."
    )


def _what_the_question_says_about_a_build_system(the_question: str) -> str:
    """The paragraphs of the question that talk about a build system, lowercased.

    **The whole question is not searched, because a word anywhere is not a demand.** The question
    mentions versions in several places that have nothing to do with the build system — a `FROM`
    line, an image, a lockfile — so a search over all of it would be satisfied by any of them. What
    has to carry the demand is the text near the field.

    **Found by proximity to the field name rather than by a phrase I wrote and then forgot.**
    The first version of this test looked for a list of exact strings, and it failed on a prompt
    that had been fixed correctly — one of the phrases had markdown asterisks in the middle of it.
    A test that can fail on correct prose is a test that gets deleted rather than fixed, and the
    prose is not what is being specified here.
    """
    the_paragraphs = the_question.split("\n\n")
    about_the_build_system = [
        a_paragraph for a_paragraph in the_paragraphs if "build_system" in a_paragraph
    ]
    assert about_the_build_system, (
        "the question never mentions `build_system` by name, so there is nothing to demand "
        "anything of and the field is filled by whatever the model puts in it"
    )
    return " ".join(about_the_build_system).lower()


def test_a_build_system_naming_only_the_tool_is_refused() -> None:
    """`npm` is not read as an answer to "what does this project build on".

    **Asserted as a refusal, because that is what a rule looks like when it holds.** The prompt
    fix above asks a better question; a prompt is a request and a model may answer it briefly
    anyway. `build_system: str | None` accepts one word forever, so the type is the thing that
    says what this system is willing to call an answer — and a type that accepts a bare noun will
    keep receiving one whatever the question asks.

    **Absent is still legal and is not what this refuses.** A repository with no build system says
    so with `None`, and the question tells the model to leave the field out rather than guess. What
    is refused is a value that carries a tool's name and nothing a gate could act on.

    **And the refusal is about this one field.** Every other field of the artifact is a
    `list[str]` or a sentence a reader can judge, and a one-word `languages` entry is a language.
    A build system is the one field whose whole content is a version, so it is the one where a
    short answer is a missing one.
    """
    from pydantic import ValidationError

    from aisdlc.agents.discovery_report import DiscoveryReport

    a_report_naming_only_the_tool = {
        "languages": ["TypeScript"],
        "architecture_summary": "A web application with an API beside it.",
        "build_system": "npm",
        "evidence_files": [{"path": "package.json", "link": "https://example.invalid/p"}],
    }

    with pytest.raises((ValidationError, ValueError)) as what_was_refused:
        DiscoveryReport(**a_report_naming_only_the_tool)

    assert "npm" in str(what_was_refused.value), (
        f"the refusal does not say which value was refused: {what_was_refused.value}"
    )

    assert (
        DiscoveryReport(
            languages=["TypeScript"],
            architecture_summary="A repository of plain text files and no build at all.",
            build_system=None,
        ).build_system
        is None
    ), (
        "a build system of nothing is this system's own word for absence, and the question tells "
        "the model to leave the field out rather than guess. Refusing `None` would force a model "
        "to invent a build system for a repository that has none"
    )
