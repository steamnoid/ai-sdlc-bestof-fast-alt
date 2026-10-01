"""A run deciding what work a repository shows, against a real model and a real report.

**This is the only artifact in this system that answers to no agent, and that is the whole reason
it needs proving on its own.** Every other artifact is a named agent answering a question a work
item carries — a request somebody typed, requirements a person approved. This one is a run
deciding what it will work on next, out of a `DiscoveryReport` a person has already ruled on,
which is why it sits **after** the discovery gate and **before** the product analyst: its output
is the request the analyst is then handed.

**The address is the thing worth proving, and its absence from the answer type is the reason this
file exists.** `CommissionedRequest` carries `filed_as`, and that field is what GitHub returned
the last time somebody filed this. A model asked to fill it would be asked for a string it can
invent, and a plausible invented host in front of an approver is worse than no address at all —
so `AProposedRequest` has exactly two fields and cannot be asked for a third. **A field that
cannot be filled cannot arrive invented**, which is the property asserted here structurally
rather than by reading what the model happened to say.

**And every request has to be workable, because a body is the whole of the work.** A title is a
line in a tracker, and the product analyst is asked to plan from the body alone — a request with
a title and no body is the shape a real implementer once read as a plan and changed no files.
The type refuses a blank body, so reaching these assertions means the model filled it; the
assertion is that it filled it with something rather than with a shape.

**Nothing here asserts content.** Real output varies per run, and a test that pinned the words a
model chose would fail every time the model was different without ever finding a defect.

**The report handed in is built here from the real clone, and not produced by the real discovery
agent.** Chaining two real agents in a file whose job is to isolate one would make this a
composition test in the tier that exists to prevent that — and `tests/e2e/test_discovery.py`
already proves that stage against a real model on this same clone. **So it is built from the
clone rather than written out**, because its citations have to be paths that really exist in the
checkout underneath this test: `evidence_for` is what the discovery node uses, and using it here
means a report whose evidence does not resolve fails this file rather than passing on a
citation nobody could click.

**The provider is a parameter rather than a constant, so proving a second one is a different run
and not a rewritten test.** A provider the deployment is not configured for says so out loud
rather than passing quietly.
"""

from __future__ import annotations

import json

import pytest

from aisdlc.agents.discovery_report import DiscoveryReport, evidence_for
from aisdlc.agents.propose_the_work_this_repository_shows import (
    AProposedRequest,
    TheWorkARepositoryShows,
    propose_the_work_this_repository_shows,
)
from aisdlc.domain.commissioned_request import CommissionedRequest
from aisdlc.domain.repository import Repository
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE

pytestmark = pytest.mark.e2e

JUDGEMENTS_THE_RUN_MAKES = ("what_it_found", "what_it_could_not_settle", "what_it_expects_next")

# The two fields the model is asked for, written out rather than read off the class, so that a
# field *added* to the answer type is caught by this list failing rather than by a reader
# noticing. An address arriving here would be a field a model could fill and therefore invent.
THE_FIELDS_THE_MODEL_IS_ASKED_FOR = ("title", "body")

# The fields the artifact carries. A run's work and its opinion of that work are two values, and
# putting the second inside the first would put sentences no human ruled on inside a document a
# gate presents.
THE_FIELDS_THE_ARTIFACT_CARRIES = ("requests", "judged")

# What a file's name says it is written in. **A suffix that is not here does not count at all**
# rather than being named after itself: a report listing `.json` as a language is describing a
# repository's manifests rather than its code, and a language this test cannot name is better
# left out than guessed at — a report that names nothing is a fact, and one that names `.yml` is
# not.
LANGUAGES_BY_SUFFIX = {
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".py": "Python",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".rb": "Ruby",
    ".sh": "Shell",
    ".sql": "SQL",
}

# The manifests a repository declares its build system in, in the order one is most likely to
# hold them. Read off the clone rather than remembered: a build system guessed here would be
# handed to a model as though it were a finding.
MANIFESTS_NAMING_A_BUILD_SYSTEM = (
    ("package.json", "npm"),
    ("pyproject.toml", "a Python project"),
    ("Cargo.toml", "Cargo"),
    ("go.mod", "the Go toolchain"),
    ("pom.xml", "Maven"),
    ("build.gradle", "Gradle"),
)

# The documents a repository holds about itself, in the order a reader would look for them.
# Whichever of these this clone really has becomes the evidence the report rests on, and a
# report resting on nothing is a paragraph.
DOCUMENTS_A_REPOSITORY_HOLDS_ABOUT_ITSELF = (
    "README.md",
    "README.rst",
    "README.txt",
    "README",
    "package.json",
    "tsconfig.json",
    "Dockerfile",
    "docker/Dockerfile",
    ".dockerignore",
    "vitest.config.ts",
    "playwright.config.ts",
)


def _every_file_the_clone_holds(clone: ClonedRepository) -> list[str]:
    """Every working-tree file of a clone, as the paths a plan or a report would name them by.

    **The history is skipped by name, because this report is about the repository's code rather
    than about its commits.** Somebody else's installed code is skipped for the reason every
    other reader of a clone skips it: a language count that includes `node_modules` is a count of
    a dependency tree.
    """
    held: list[str] = []
    for a_path in sorted(clone.path.rglob("*")):
        if not a_path.is_file():
            continue
        its_parts = a_path.relative_to(clone.path).parts
        if any(a_part in DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE for a_part in its_parts):
            continue
        held.append(str(a_path.relative_to(clone.path)))
    return held


def _the_languages_this_repository_is_written_in(every_path: list[str]) -> list[str]:
    """The languages the clone's own files say it is written in, most-used first.

    **Counted from the checkout rather than named here**, because this repository has never read
    the repository this tier is pointed at and a language list written into a test file is a
    guess. Three is enough to describe a project; twenty would be a list of dependency trees.
    """
    how_many_files_of_each_suffix: dict[str, int] = {}
    for a_path in every_path:
        its_name = a_path.rsplit("/", 1)[-1]
        if "." not in its_name:
            continue
        a_suffix = "." + its_name.rsplit(".", 1)[-1]
        if a_suffix not in LANGUAGES_BY_SUFFIX:
            continue
        how_many_files_of_each_suffix[a_suffix] = how_many_files_of_each_suffix.get(a_suffix, 0) + 1

    in_order_of_use = sorted(
        how_many_files_of_each_suffix,
        key=lambda a_suffix: (-how_many_files_of_each_suffix[a_suffix], a_suffix),
    )
    named: list[str] = []
    for a_suffix in in_order_of_use:
        a_language = LANGUAGES_BY_SUFFIX[a_suffix]
        if a_language not in named:
            named.append(a_language)
    return named[:3]


def _the_directories_a_repository_keeps_its_code_in(clone: ClonedRepository) -> list[str]:
    """The top-level directories holding files, which is what a reader would call the project."""
    the_top_level: list[str] = []
    for a_child in sorted(clone.path.iterdir()):
        if not a_child.is_dir():
            continue
        if a_child.name in DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE or a_child.name.startswith("."):
            continue
        the_top_level.append(a_child.name)
    return the_top_level[:5]


def _the_suite_this_repository_declares(clone: ClonedRepository) -> str | None:
    """The script `package.json` itself names, or `None` because this repository names none."""
    manifest = clone.path / "package.json"
    if not manifest.is_file():
        return None
    try:
        what_it_declares = json.loads(manifest.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    the_test_script = (what_it_declares.get("scripts") or {}).get("test")
    if not isinstance(the_test_script, str):
        return None
    return the_test_script


def _the_dependencies_this_repository_declares(clone: ClonedRepository) -> list[str]:
    """What `package.json` says it depends on, which is a fact about the repository."""
    manifest = clone.path / "package.json"
    if not manifest.is_file():
        return []
    try:
        what_it_declares = json.loads(manifest.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return []
    every_dependency: list[str] = []
    for a_list_of_dependencies in ("dependencies", "devDependencies"):
        for a_name in what_it_declares.get(a_list_of_dependencies) or {}:
            if a_name not in every_dependency:
                every_dependency.append(a_name)
    return every_dependency


def _the_paths_this_report_rests_on(clone: ClonedRepository, every_path: list[str]) -> list[str]:
    """The evidence paths, every one of them a file of this clone.

    **Read off the checkout and filtered by asking the checkout**, so `evidence_for` is never
    handed a path that resolves to nothing — a citation that looks exactly like a link and goes
    nowhere is the failure `EvidenceOutsideRepositoryError` exists for, and a report resting on
    one is a paragraph wearing a link.
    """
    wanted: list[str] = []
    for a_path in DOCUMENTS_A_REPOSITORY_HOLDS_ABOUT_ITSELF:
        if a_path in every_path:
            wanted.append(a_path)

    a_test_this_repository_runs = next(
        (a_path for a_path in every_path if ".test." in a_path or ".spec." in a_path), None
    )
    if a_test_this_repository_runs is not None:
        wanted.append(a_test_this_repository_runs)

    a_workflow_this_repository_declares = next(
        (a_path for a_path in every_path if a_path.startswith(".github/workflows/")), None
    )
    if a_workflow_this_repository_declares is not None:
        wanted.append(a_workflow_this_repository_declares)

    if not wanted:
        pytest.skip(
            "this clone holds none of the documents a repository holds about itself and no test "
            "and no workflow, so there is no path a discovery report could cite and a report "
            "resting on nothing is a paragraph. This tier does not invent a citation."
        )

    return wanted


def _the_architecture_of_this_repository(
    clone: ClonedRepository, every_path: list[str], the_languages: list[str]
) -> str:
    """A sentence about how this repository is laid out, built from what the checkout shows.

    **Written here rather than asked of a model, because the report is an input and not the
    subject of this file.** Everything in it is read out of the clone — the languages from the
    files, the directories from the top level, the suite command from the manifest — so the one
    thing this stage is handed is a description that is true of the repository underneath it
    rather than a plausible paragraph about some repository.
    """
    the_directories = _the_directories_a_repository_keeps_its_code_in(clone)
    the_suite = _the_suite_this_repository_declares(clone)
    where_its_tests_are = _where_this_repository_keeps_most_of_its_tests(every_path)

    the_sentence = (
        f"A repository written in {', '.join(the_languages) or 'languages this test cannot name'}, "
        f"laid out as {', '.join(the_directories) or 'a single directory'}."
    )
    if the_suite is not None:
        the_sentence += f" Its own suite is the one its manifest declares as `{the_suite}`."
    if where_its_tests_are is not None:
        the_sentence += f" Most of the tests it keeps are under {where_its_tests_are}."
    return the_sentence


def _where_this_repository_keeps_most_of_its_tests(every_path: list[str]) -> str | None:
    """The one directory most of this repository's own tests sit in, or `None` because it has none.

    **The directory rather than a count of directories**, because a repository that keeps a suite
    per ticket has as many test directories as it has tickets, and naming the first four of them
    alphabetically says nothing about where the suite is actually run from.
    """
    how_many_tests_in_each_directory: dict[str, int] = {}
    for a_path in every_path:
        if ".test." not in a_path and ".spec." not in a_path:
            continue
        its_directory = a_path.rsplit("/", 1)[0] if "/" in a_path else "."
        how_many_tests_in_each_directory[its_directory] = (
            how_many_tests_in_each_directory.get(its_directory, 0) + 1
        )

    if not how_many_tests_in_each_directory:
        return None

    return sorted(
        how_many_tests_in_each_directory,
        key=lambda a_directory: (-how_many_tests_in_each_directory[a_directory], a_directory),
    )[0]


@pytest.fixture(scope="module")
def a_report_a_person_already_ruled_on(
    the_repository: Repository, the_cloned_repository: ClonedRepository
) -> DiscoveryReport:
    """A real discovery report about this repository, with citations that resolve.

    **A stand-in for what the discovery node produces, named as one.** The real report is proved
    against a real model by `tests/e2e/test_discovery.py`; what this stage needs from it is a
    description of this clone and evidence a reviewer could click, so it is assembled here out of
    the clone rather than chained from another real agent.
    """
    every_path = _every_file_the_clone_holds(the_cloned_repository)
    the_languages = _the_languages_this_repository_is_written_in(every_path)
    the_paths_to_cite = _the_paths_this_report_rests_on(the_cloned_repository, every_path)

    the_build_system = next(
        (
            what_it_says
            for a_manifest, what_it_says in MANIFESTS_NAMING_A_BUILD_SYSTEM
            if a_manifest in every_path
        ),
        None,
    )
    the_ci_system = (
        "GitHub Actions"
        if any(a_path.startswith(".github/workflows/") for a_path in every_path)
        else None
    )

    return DiscoveryReport(
        languages=the_languages,
        frameworks=_the_dependencies_this_repository_declares(the_cloned_repository)[:8],
        build_system=the_build_system,
        ci_system=the_ci_system,
        architecture_summary=_the_architecture_of_this_repository(
            the_cloned_repository, every_path, the_languages
        ),
        key_components=_the_directories_a_repository_keeps_its_code_in(the_cloned_repository),
        evidence_files=evidence_for(the_paths_to_cite, the_repository),
    )


@pytest.fixture(scope="module")
def the_work_this_repository_shows(
    a_report_a_person_already_ruled_on: DiscoveryReport, the_model_for, request
) -> TheWorkARepositoryShows:
    """One real answer to *what work does this repository show*, shared by every assertion below.

    Module scope, because a model call is the expensive part and the assertions are four
    contracts about *one* answer. Asserting separately about separate runs would prove only that
    the model answers differently each time, which is true and is not what this file is for.

    **The provider is `request.param` and the tests parametrise it indirectly**, so a run
    configured for one provider *skips* the others with the reason printed rather than passing
    quietly.
    """
    return propose_the_work_this_repository_shows(
        a_report_a_person_already_ruled_on, the_model_for(request.param)
    )


@pytest.mark.parametrize("the_work_this_repository_shows", list(LlmProvider), indirect=True)
def test_no_request_this_stage_produced_carries_an_address(
    the_work_this_repository_shows: TheWorkARepositoryShows,
) -> None:
    """The answer type cannot be asked for an address, so none of the requests carries one.

    **`filed_as` is absent and that is the point.** `CommissionedRequest` takes the address
    GitHub returned the last time somebody filed the request, and a model asked to fill it would
    be asked for a string it can invent — a plausible invented host in front of an approver is
    worse than no address at all. **A field that cannot be filled cannot arrive invented**, which
    is why this is asserted on the type and not by looking for a suspicious string in the output.

    **`extra="forbid"` as well, because the field could arrive by another route.** A type that
    ignores a keyword it has no name for is a type where an address would be silently dropped
    rather than refused, and a rule a model cannot hold should fail loudly.

    **And no produced request carries one either, which is the consequence rather than the
    cause.** Nothing in this call asks GitHub anything, so `where_it_can_be_read` has nothing to
    return — and a request with an address shaped like a link that resolves to nothing is worse
    than no link at all, because a reader months later cannot tell which they are holding.
    """
    assert "filed_as" not in AProposedRequest.model_fields, (
        "AProposedRequest now carries `filed_as`, so a model can be asked for the address of a "
        "filing and will invent one — a plausible invented host in front of an approver is worse "
        "than no address at all, and the field this stage refuses to fill is the one thing that "
        "made inventing it impossible"
    )
    assert set(AProposedRequest.model_fields) == set(THE_FIELDS_THE_MODEL_IS_ASKED_FOR), (
        f"AProposedRequest carries {sorted(AProposedRequest.model_fields)} and the model is "
        f"asked for {list(THE_FIELDS_THE_MODEL_IS_ASKED_FOR)}. Every field on this type is a "
        "string a model fills, so a field added here is a string a model can invent"
    )
    assert AProposedRequest.model_config.get("extra") == "forbid", (
        "AProposedRequest accepts a keyword it has no name for. An address reaching this type by "
        "any other route would then be dropped rather than refused, and a caller would believe "
        "they had said something"
    )

    for a_request in the_work_this_repository_shows.requests:
        assert a_request.filed_as is None, (
            f"{a_request.title!r} carries the filing {a_request.filed_as}. Nothing in this call "
            "asks GitHub anything, so any address here was not read from GitHub — and an address "
            "this system did not read is one somebody will click and find nothing at"
        )
        assert a_request.where_it_can_be_read() is None, (
            f"{a_request.title!r} can be read at an address, and nothing in this call asked "
            "GitHub for one. `CommissionedRequest` takes the address GitHub returned rather "
            "than one composed from `owner/name`, precisely because a link that resolves is a "
            "different kind of fact from one that does not"
        )


@pytest.mark.parametrize("the_work_this_repository_shows", list(LlmProvider), indirect=True)
def test_every_request_could_be_worked_from_by_whoever_reads_it_next(
    the_work_this_repository_shows: TheWorkARepositoryShows, the_placeholders: frozenset[str]
) -> None:
    """Every request has a subject and a body, and the body is not the title written twice.

    **A title is a line in a tracker and a body is the work.** The product analyst is asked to
    plan from the body alone, so a request with a title and no body asks a planner to plan
    nothing — which is the shape a real implementer once read as a plan and changed no files.

    **The type refuses a blank body, so reaching this assertion means the model filled it**; what
    is asserted is that it filled it with something rather than with a shape. A body that is the
    title again is the same words twice, and a planner reading it twice learns no more than a
    planner reading it once.

    **Nothing is asserted about what the work is**, because that is a judgement about meaning and
    this file is about the contract. Whether these are good proposals for this repository is an
    eval's business.
    """
    the_requests = the_work_this_repository_shows.requests

    assert the_requests, (
        "a run that has just read a repository was asked what work it shows and named none. "
        "Either there is nothing to do, which is an answer somebody has to read and agree with, "
        "or the model was asked the wrong question — and an empty list reads as the first of "
        "those to whoever reads it next"
    )

    for a_request in the_requests:
        assert a_request.title.strip(), (
            "a request arrived with no subject. The title is the one field a person reads to "
            "know what the work is, and a blank one leaves the work with no subject and the run "
            "with nothing to be about"
        )
        assert a_request.body.strip(), (
            f"{a_request.title!r} arrived with a body of nothing. A title is not work: the body "
            "is where a person learns what is wrong and why it matters, and the product analyst "
            "is asked to plan from the body alone"
        )
        assert a_request.body.strip() != a_request.title.strip(), (
            f"the body of {a_request.title!r} is its title written again. Two copies of one line "
            "is what a tracker looks like when nobody has written the request, and a planner "
            "reading it twice learns no more than a planner reading it once"
        )

        for a_field, its_text in (
            ("title", a_request.title),
            ("body", a_request.body),
        ):
            assert its_text.strip().lower() not in the_placeholders, (
                f"{its_text!r} is placeholder text in a request's {a_field}, which means the "
                "model returned a shape rather than a request somebody could have typed"
            )


@pytest.mark.parametrize("the_work_this_repository_shows", list(LlmProvider), indirect=True)
def test_the_note_beside_the_work_carries_all_three_of_the_runs_judgements(
    the_work_this_repository_shows: TheWorkARepositoryShows, the_placeholders: frozenset[str]
) -> None:
    """The three sentences about its own work are filled in, and none is a shape.

    **This is the only judgement in the run about the run's own next step.** Every other agent is
    handed a question somebody asked; this one decides what the run will work on, so the sentence
    about what it expects next is the one a person supervising it has no other way of getting.

    **A blank reads as *nobody asked*, which is not a thing anybody can check**, and an answer
    naming nothing is a shape rather than a finding. Both are refused by the answer type; both are
    asserted here on a real model, because a rule that lives in a type is not the same as a rule
    anybody has watched hold.
    """
    the_note = the_work_this_repository_shows.judged

    for a_judgement in JUDGEMENTS_THE_RUN_MAKES:
        said = getattr(the_note, a_judgement)
        assert said.strip(), (
            f"the run left {a_judgement} empty. It is asked three questions about its own work "
            "and an agent with nothing to report has words to reach for, so an empty field here "
            "means the question was not put rather than that there was no answer"
        )
        assert said.strip().lower() not in the_placeholders, (
            f"{said!r} is placeholder text in {a_judgement}, which means the model filled the "
            "shape and stopped rather than saying anything"
        )


@pytest.mark.parametrize("the_work_this_repository_shows", list(LlmProvider), indirect=True)
def test_the_artifact_is_the_one_the_next_stage_reads_and_it_carries_nothing_else(
    the_work_this_repository_shows: TheWorkARepositoryShows,
) -> None:
    """The work is this type, each request is a `CommissionedRequest`, and the note stayed out.

    **A machine asking for work is not a new idea here, so no parallel request type was invented
    for it.** `Commissioned by` is a string rather than a switch precisely so an identifier in
    the `aisdlc-` namespace can say *a machine was asked*, and the approval gate reads the same
    prefix to tell an agent from a person. A request type of its own would be one concept under
    two names, which is the thing this repository's naming rule exists to prevent — and the run
    that reaches this one is commissioning the same work any other run commissions.

    **The judgement is asserted to be outside the requests as well as inside the artifact.** The
    requests are what a work item is built from and a card is made of, so three sentences about
    the run's own work carried inside one of them would put material no human ruled on inside the
    thing a human rules on.
    """
    the_work = the_work_this_repository_shows

    assert isinstance(the_work, TheWorkARepositoryShows), (
        f"the stage answered with {type(the_work).__name__} rather than the artifact the product "
        "analyst is handed, so nothing downstream can rely on which fields it carries"
    )
    assert set(TheWorkARepositoryShows.model_fields) == set(THE_FIELDS_THE_ARTIFACT_CARRIES), (
        f"TheWorkARepositoryShows carries {sorted(TheWorkARepositoryShows.model_fields)} and the "
        f"run's own view of its work is {list(THE_FIELDS_THE_ARTIFACT_CARRIES)}. Every field "
        "added here is a thing the next stage was not asked for and has to read anyway"
    )

    for a_request in the_work.requests:
        assert isinstance(a_request, CommissionedRequest), (
            f"{type(a_request).__name__} is not a CommissionedRequest. A machine asking for work "
            "is not a new concept — `Commissioned by` is a string so an `aisdlc-` name can say "
            "*a machine was asked* — and a parallel request type would be one concept under two "
            "names"
        )

    assert "judged" not in CommissionedRequest.model_fields, (
        "CommissionedRequest now carries the judgement. A request is what a work item is born "
        "from and what a card is made of, so three sentences about the run's own work inside one "
        "would put material no human ruled on inside the thing a human rules on"
    )
