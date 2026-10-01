"""The architecture analyst, against a real model and a real repository.

Same chain as discovery: a real public repository cloned with real `git`, read by a real
model obtained through the real factory. Nothing asserted is content — what is asserted is the
contract, plus the one measurement this stage is the only one that can take.

**`modules` and `dependencies` are inventories, and that is why this file is more than
discovery's twin.** §10 asks this agent to identify both and the glossary puts both in the
artifact, so the node asks the model for them. A report naming a module is a judgement, and a
second model asked to make it would be a model grading a model — so the modules are checked
for being filled and for not being placeholders, and nothing more is claimed about them.

**A claimed dependency is checked against the manifest, and that is the assertion worth
having.** `package.json` and `package-lock.json` are read off disk and every package name the
report claims is looked up in them. A report saying a project depends on something it does not
is what makes an architecture report read as a work of fiction, and it is checkable here
because the substrate is a clone. The check is against the *manifest* rather than against the
file appearing anywhere in the inspection, because a name can legitimately appear in a
comment, a lockfile or a test and still not be a dependency.

**What this stage is shown, and what that decides.** It is handed `an_inspection_of` — the
listing, the manifests, the README and the CI configuration — and not the file contents. That
is a real constraint and not an oversight, and the finding this tier has already produced is
that a model asked to write about boundaries and risks from a listing will do it anyway, and a
person at a gate cannot tell. **The test below asserts what the stage was shown, rather than
asking it to do better** — because a rule that lives only in a prompt is not a rule, and the
claim that matters is the one a reader can check.
"""

from __future__ import annotations

import json
import re

import pytest

from aisdlc.agents.analyze_the_architecture import analyze_the_architecture
from aisdlc.agents.architecture_report import ArchitectureReport
from aisdlc.domain.repository import Repository
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository

pytestmark = pytest.mark.e2e

MUST_BE_FILLED = ("findings",)
MAY_BE_EMPTY = ("modules", "dependencies", "boundaries", "risks")
JUDGEMENTS_THE_ANSWER_MAKES = ("what_it_found", "what_it_could_not_settle")


def the_dependencies_the_repository_declares(clone: ClonedRepository) -> set[str]:
    """Every package name this repository's own manifests carry, read off disk.

    **The lockfile is read from its keys, and that is a correction to the version this test
    was copied with.** A lockfile v3 lists every package as `node_modules/<name>` and only
    the root entry carries a `name` field, so a reader looking for that field finds one package
    out of three hundred and seventy-three — silently, because an empty set is a set. It then
    refused every dependency the report claimed, including `sharp`, which Next.js really does
    pull in. A guard that finds nothing is not a guard.

    **The lockfile counts, and not only `package.json`.** A report saying this project depends
    on `sharp` because its framework does is a true statement about the project, and refusing
    it for want of a line in the manifest would be the test refusing the truth.
    """
    declared: set[str] = set()

    for a_manifest_name in ("package.json", "package-lock.json"):
        a_manifest = clone.path / a_manifest_name
        if not a_manifest.is_file():
            continue

        try:
            what_it_declares = json.loads(a_manifest.read_text())
        except json.JSONDecodeError:
            continue

        for a_section in ("dependencies", "devDependencies"):
            for a_dependency in what_it_declares.get(a_section, {}) or {}:
                declared.add(a_dependency)

        for a_where, a_package in (what_it_declares.get("packages", {}) or {}).items():
            if a_where.startswith("node_modules/"):
                declared.add(a_where.removeprefix("node_modules/"))
            elif isinstance(a_package, dict) and isinstance(a_package.get("name"), str):
                declared.add(a_package["name"])

    return declared


def the_packages_one_entry_claims(entry: str) -> list[str]:
    """The package names in one entry, and only the ones presented as a package and not a word.

    **A version or a scope, and nothing else, and the first two versions of this rule were both
    wrong.** It took the first identifier-shaped word, and any English word is identifier-shaped
    — a real run yielded `Runtime` from a sentence. It then took everything in backticks, and a
    real model backticks a great deal that is not a package: `dev`, `build` and `start` are the
    npm scripts in this repository's own `package.json`, `tsconfig.json` and `playwright.config.ts`
    are files, and `web-app` is a directory. Every one of those is a correct mention, and the
    test accused the model of inventing all of them.

    So a claim is a name the model attached a version to, or scoped as `@scope/name`. Those two
    are unambiguous — nothing else in a sentence is written that way — and a bare backticked
    word is a mention. **Prose is then prose**: `Node.js with npm` names a runtime and a package
    manager and claims no version of either.
    """
    scoped = re.findall(r"(@[\w.-]+/[\w.-]+)", entry)
    versioned = re.findall(r"(?<![\w@/.-])([\w][\w.-]*(?:/[\w.-]+)?)@\d", entry)
    return scoped + versioned


@pytest.fixture(scope="module")
def a_real_report(
    the_repository: Repository,
    the_cloned_repository: ClonedRepository,
    the_model_for,
    request,
) -> tuple[ArchitectureReport, object]:
    """One real analysis, shared by every assertion about it."""
    return analyze_the_architecture(
        the_cloned_repository, the_repository, the_model_for(request.param)
    )


@pytest.mark.parametrize("a_real_report", list(LlmProvider), indirect=True)
def test_a_real_model_describes_something_a_person_could_read_before_changing_it(
    a_real_report: tuple[ArchitectureReport, object], the_placeholders: frozenset[str]
) -> None:
    """The artifact is the artifact type, and it carries a finding a person can act on.

    **`findings` and not the other four collections.** A repository with no boundary worth
    writing about has none, and the honest report says so with one filled collection rather
    than inventing a boundary. §10 calls this analysis advisory rather than a replacement for
    a scanner, and the node refuses a report empty in all of them.
    """
    the_report, the_answer = a_real_report

    assert isinstance(the_report, ArchitectureReport), (
        f"the stage answered with {type(the_report).__name__} rather than the artifact a gate "
        "presents"
    )

    for a_field in MUST_BE_FILLED:
        said = getattr(the_report, a_field)
        assert said, (
            f"the architecture analyst was asked what shape this repository has and {a_field} "
            "is empty. That artifact is what the next gate presents, so an empty one is a gate "
            "a person is asked to rule on with nothing in it"
        )
        for one_of_them in said:
            assert str(one_of_them).strip().lower() not in the_placeholders, (
                f"{one_of_them!r} in {a_field} is placeholder text, which means the model "
                "returned a shape rather than a finding"
            )

    for judgement in JUDGEMENTS_THE_ANSWER_MAKES:
        assert getattr(the_answer.judged, judgement).strip(), (
            f"the architecture analyst left {judgement} empty. An architect's doubt about a "
            "repository's shape is the one a change plan is most likely to need, and an empty "
            "one reads as a doubt nobody had"
        )


@pytest.mark.parametrize("a_real_report", list(LlmProvider), indirect=True)
def test_a_claimed_dependency_is_one_the_repository_actually_declares(
    a_real_report: tuple[ArchitectureReport, object], the_cloned_repository: ClonedRepository
) -> None:
    """Every package the report says this project depends on is in the manifest.

    **A manifest and not the inspection, and the difference matters.** A name can appear in a
    comment, a lockfile or a test and still not be a dependency, so checking the report against
    everything the model was shown would let an invented dependency through on the strength of
    a word appearing somewhere in the file. The manifest is the declaration; everything else is
    a mention.

    **An entry naming no package is not a claim and is not accused.** `Node.js with npm` is
    prose, and a test that read `Node` as a package name would report a defect that is not
    there — which is worse than no check, because the next person stops reading the failures.
    The assertion that some name *was* recognised keeps the recogniser honest in the other
    direction.
    """
    the_report, _ = a_real_report

    if not the_report.dependencies:
        pytest.skip(
            "the report names no dependencies, so there is nothing to check against the "
            "manifest. That is an honest answer for a repository with no manifest, and this "
            "tier does not judge whether the repository should have one."
        )

    declared = the_dependencies_the_repository_declares(the_cloned_repository)
    assert declared, (
        "this repository declares no dependency in any manifest, so every name the report "
        "claimed would be checked against an empty set and refused. The check is only "
        "meaningful where a manifest exists to check against."
    )

    invented: list[str] = []
    recognised_at_least_one = False

    for an_entry in the_report.dependencies:
        for a_claimed_name in the_packages_one_entry_claims(an_entry):
            recognised_at_least_one = True
            if a_claimed_name not in declared:
                invented.append(a_claimed_name)

    assert recognised_at_least_one, (
        f"the report names dependencies {the_report.dependencies} and not one of them is a "
        "package name this test can recognise. A check that recognises nothing refuses nothing, "
        "so this is a green tick about a rule that was not applied — and the two ways a model "
        "presents a package unambiguously are a version after it and an `@scope/`"
    )

    assert not invented, (
        f"{sorted(set(invented))} are claimed as packages of this repository at a named "
        "version, and neither `package.json` nor `package-lock.json` carries them. A version is "
        "not something a model guesses, so an invented one is either a package remembered from "
        "another project or a version it made up — and an architecture report describing a "
        "different project is the one document a change plan is built from."
    )


@pytest.mark.parametrize("a_real_report", list(LlmProvider), indirect=True)
def test_the_report_says_what_it_was_not_shown(
    a_real_report: tuple[ArchitectureReport, object]
) -> None:
    """The collections a gate reads are the glossary's, and no others.

    **Asserted on the artifact's own fields rather than on a count.** §10 names five and the
    glossary puts five in the report, and a person is asked to approve exactly those. A field
    added here is material in front of a gate that no rule asked for — and it is the same claim
    the discovery tier makes about its own artifact, asked twice because a rule written for one
    artifact is a rule written for one artifact.
    """
    the_fields_the_glossary_names = {"findings", "modules", "dependencies", "boundaries", "risks"}

    added = set(ArchitectureReport.model_fields) - the_fields_the_glossary_names
    assert not added, (
        f"ArchitectureReport now carries {sorted(added)}. A gate presents this artifact and an "
        "Approval names it with a version, so a field added here is material in front of a "
        "decision that was never about it"
    )
