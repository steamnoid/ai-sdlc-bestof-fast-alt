"""Discovery as a node: ask the model, then build the artifact the gate presents.

The order matters and is the whole design. The model answers first, in a shape that
cannot carry an address, and only then does the system attach addresses it derived
itself. A single type would have to make the address optional to accommodate a model
that might fill it in, and an address that may be absent is an address nobody can rely
on clicking.
"""

from __future__ import annotations

import time

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from aisdlc.agents.discovery_answer import DiscoveryAnswer
from aisdlc.agents.discovery_report import (
    DiscoveryReport,
    EvidenceFile,
    evidence_for,
)
from aisdlc.domain.repository import Repository
from aisdlc.graph.discover_node import Discover
from aisdlc.llm.asking_a_model_for import ask_a_model_for
from aisdlc.llm.correction_budget import (
    how_a_model_is_told_what_was_wrong,
    may_this_run_keep_asking,
)
from aisdlc.llm.llm_configuration import a_configuration_from_the_environment
from aisdlc.llm.model_factory import a_model_for
from aisdlc.tools.filesystem_read import (
    a_path_in_the_project,
    the_path_inside_the_project,
)
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import an_inspection_of_the_code

THE_FIELDS_THE_ANSWER_MAY_NAME = (
    "languages",
    "frameworks",
    "build_system",
    "ci_system",
    "architecture_summary",
    "key_components",
    "evidence_files",
    "suggested_changes",
)

# **The three judgements, asked in the same question as the inventory.** One call and one
# answer, so there is no second model call to pay for and no way for a judgement to be written
# about an inventory that is not the one beside it. The middle one is the one worth having: a
# discovery agent is the only agent that sees the whole repository, so its doubt is the widest
# one the run has, and it is a doubt nothing else will be in a position to have.
THE_JUDGEMENTS_THE_ANSWER_MAY_NAME = (
    "what_it_found",
    "what_it_could_not_settle",
    "what_it_expects_next",
)


class CitedFileNotFoundError(Exception):
    """The rule is in `discover_the_repository`, and only it may say the rule broke."""


def the_prompt_to_discover_a_repository(
    inspection: str,
    repository: Repository,
    what_was_wrong_about_the_last_answer: str | None = None,
) -> str:
    """The question put to the model about one inspected repository.

    The inspection is inlined rather than referenced because the model has no other way
    to see the repository: this node is given what was inspected, and a question that
    omitted it would leave the model describing whatever it could infer from a
    repository's name.

    The instruction about evidence being paths is here, but nothing depends on the model
    obeying it. `DiscoveryAnswer` has no field an address could arrive in, so the rule
    is enforced by the shape and the sentence is only there to save the model from
    guessing at something it is not asked for.
    """
    correction = (
        ""
        if what_was_wrong_about_the_last_answer is None
        else (
            "\nYour last answer was wrong, and this is what was wrong with it:\n"
            f"{what_was_wrong_about_the_last_answer}\n"
            "Name only files the inspection shows.\n"
        )
    )

    return (
        f"You are inspecting the public repository {repository.owner}/{repository.name}.\n"
        "Answer from the inspection below and from nothing else.\n"
        "\n"
        f"Name these fields for the inventory: "
        f"{', '.join(THE_FIELDS_THE_ANSWER_MAY_NAME)}. Then three sentences of judgement, naming "
        f"{', '.join(THE_JUDGEMENTS_THE_ANSWER_MAY_NAME)}.\n"
        f"{correction}"
        "\n"
        "Say only what the inspection supports. If the inspection does not show a build\n"
        "system or a CI system, leave that field out rather than guessing, and an absent\n"
        "field is read as absent rather than as unknown.\n"
        "\n"
        "`build_system` is what the build *runs on*, not the tool's name. A tool alone is not an\n"
        "answer: write the command and, when the inspection shows one, the runtime or image it\n"
        "runs in and the version that pins — `node:22-bookworm` in a `FROM` line is the fact a\n"
        "person needs, and `npm` on its own is not it. **Two real runs were refused at a gate over\n"
        "exactly this**: asked to declare which Node version the project requires, the report said\n"
        "`build_system: npm` while its own `key_components` carried the Dockerfile pinning\n"
        "`node:22-bookworm`. Every fact was there and in no field anybody asked for.\n"
        "\n"
        "In `evidence_files`, name the files your conclusions rest on, as paths inside\n"
        "this repository. Name files, not directories, and only files the inspection\n"
        "actually shows. Do not write addresses: the system derives them, and one you\n"
        "invent would point a reviewer away from the work they commissioned.\n"
        "\n"
        f"Inspection of {repository.owner}/{repository.name}:\n"
        f"{inspection}"
    )


def discover_the_repository(
    clone: ClonedRepository, repository: Repository, model: BaseChatModel
) -> tuple[DiscoveryReport, DiscoveryAnswer]:
    """The discovery report for a repository this run cloned.

    The answer is validated rather than cast, because `with_structured_output` is typed
    to hand back either the class or plain data and a provider that ignores the schema
    is a real case rather than a theoretical one. Validating is not trusting: a field of
    the wrong shape is still refused, here and deterministically.

    Every cited file is looked up in the clone before the report exists. The real tier
    found the alternative: a model cited `web-app/`, a directory, and its link resolved
    to nothing while looking exactly like a link. `evidence_for` checks that a path does
    not *leave* the repository, and nothing checked that it *is* a file of it — which is
    the claim a report makes most and the one a reader most wants true. It is checkable
    because the substrate is a clone on disk, and that is the argument for a clone over
    an API read: without one, this refusal could not exist.

    A directory is refused the same way a missing file is, because it is the same
    failure: an address that leads nowhere, presented as though it led somewhere.
    """
    # **The code, not only the shape — the third consumer of the same inspection.** This module
    # was written when the inspection was a listing, a manifest and a README, and a discovery
    # report was a summary of a repository's shape; the security analyst was then wired to the
    # same one and reasoned from filenames, and a run's gate refused the report for it. The
    # lesson was not "the security analyst needs more" — it was that **one inspection built for
    # one consumer was being handed to another**, and a real run then refused a discovery report
    # for citing a `Dockerfile` whose contents the report itself said it had not seen.
    inspection = an_inspection_of_the_code(clone)
    what_was_wrong: str | None = None

    began_at = time.monotonic()
    asked_so_far = 0
    while may_this_run_keep_asking(asked_so_far, began_at):
        asked_so_far += 1
        asking = ask_a_model_for(model, DiscoveryAnswer)
        try:
            answer = DiscoveryAnswer.model_validate(
                asking.invoke(
                    the_prompt_to_discover_a_repository(
                        inspection, repository, what_was_wrong
                    )
                )
            )
            return _the_report_about(clone, repository, answer, inspection)
        except (CitedFileNotFoundError, ValidationError) as refused:
            what_was_wrong = how_a_model_is_told_what_was_wrong(refused)
            last = refused

    raise last


def _the_report_about(
    clone: ClonedRepository,
    repository: Repository,
    answer: DiscoveryAnswer,
    inspection: str,
) -> tuple[DiscoveryReport, DiscoveryAnswer]:
    """The report and the answer it was built from, once every citation is a file of this clone.

    Split out so the correction loop can tell the difference between "this answer is
    wrong" and "this run is broken".

    **Two values rather than one, and the note is not in the report.** The report is what a
    person approves and has exactly the fields the glossary gives it; the answer's three
    sentences are what a person and a repair supervisor read afterwards.
    """
    return DiscoveryReport(
        languages=answer.languages,
        frameworks=answer.frameworks,
        build_system=answer.build_system,
        ci_system=answer.ci_system,
        architecture_summary=answer.architecture_summary,
        key_components=answer.key_components,
        evidence_files=_the_cited_files_that_are_in(
            clone, answer.evidence_files, repository, _the_paths_the_inspection_showed(inspection)
        ),
        suggested_changes=answer.suggested_changes,
    ), answer


def _the_paths_the_inspection_showed(inspection: str) -> str:
    """Every path the inspection put in front of this agent, as one string to match against.

    **Read out of the inspection rather than kept alongside it**, because the inspection is the
    thing that decides what the model was shown and a second list is a second thing that can
    disagree with it. The headings are the paths: the top-level listing is prose, the manifests
    and the code sections are `## <path>` each, and the closing section is the one this exists
    to contradict.
    """
    return "\n".join(
        line.removeprefix("## ")
        for line in inspection.splitlines()
        if line.startswith("## ")
    )


def _the_cited_files_that_are_in(
    clone: ClonedRepository, cited: list[str], repository: Repository, was_shown: str = ""
) -> list[EvidenceFile]:
    """The evidence, every citation proved a file of this clone **and one that was shown**.

    **Two checks and the second is the one a real run needed.** A citation that is not a file of
    the repository is a link to nowhere. A citation that *is* a file of the repository but was
    never shown to the model is a link to somewhere — and the report saying so in one field while
    claiming it in another is worse, because the claim is the one a reader acts on. A run's gate
    refused exactly that:

        "the report supplies no current interval, no base image … while Dockerfile nonetheless
         appears in evidence_files with blob links as though they had been read"

    The path rule runs before the file check, because the two refusals answer different
    questions and the sharper one is more use to a caller: a URL is a path that leaves the
    repository, and `evidence_for` already knows how to say that in terms of a boundary
    rather than in terms of a file being absent. The check is on the resolved file rather
    than on the spelling, so a trailing slash and a `..` are both what they are.
    """
    addresses = evidence_for(cited, repository)

    for evidence in addresses:
        # **Through the boundary, not `clone.path / path` by hand.** This was the only place in
        # an agent that built a path itself, and building one skips every guard the boundary
        # has: the escape check, the address check, and the shape check a real run needed. A
        # 600-character citation reached `stat`, and `stat` raised rather than answering.
        where = the_path_inside_the_project(a_path_in_the_project(clone.path, evidence.path))

        if not where.is_file():
            raise CitedFileNotFoundError(
                f"{evidence.path!r} is not a file of "
                f"{repository.owner}/{repository.name} as it was cloned, so it cannot be "
                "evidence. A report that cites something that is not there is asking a "
                "reader to click a link that leads nowhere, and the citation is the claim "
                "the report rests on."
            )

        if was_shown and evidence.path not in was_shown:
            raise CitedFileNotFoundError(
                f"{evidence.path!r} is a file of {repository.owner}/{repository.name}, and this "
                "report cites it as evidence — but the inspection this agent was shown does not "
                "contain it, so nothing in this report rests on having read it. A citation is a "
                "claim that a file was read, and a file that was never shown has not been. The "
                "inspection ends with a section naming what it withheld; this is that section "
                "being true."
            )

    return addresses


def the_discovery_using_the_configured_model() -> Discover:
    """The real discovery: the model the deployment's environment names.

    A factory rather than a default argument on `the_lifecycle`, because the graph should
    not know how a model is obtained — it is handed a function, and this is the one that
    asks the environment. A test hands it a different function and never reads a key.
    """
    def discovering(
        clone: ClonedRepository, repository: Repository
    ) -> tuple[DiscoveryReport, DiscoveryAnswer]:
        return discover_the_repository(
            clone, repository, a_model_for(a_configuration_from_the_environment())
        )

    return discovering
