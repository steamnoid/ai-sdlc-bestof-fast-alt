"""What the discovery agent learned about a repository, in the fields §10 lists.

The field names are not chosen here. `docs/domain-glossary.md` already fixed the
contents of this artifact, and the agent's name is the contract, so a field that drifts
from that table is a broken promise rather than a rename.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator, model_validator

from aisdlc.agents.a_value_that_says_something import a_value_that_says_something, as_absence
from aisdlc.domain.repository import Repository

THE_DISCOVERY_AGENT = "aisdlc-discover"
WHERE_A_REVIEWER_READS_A_FILE = "https://github.com/{owner}/{name}/blob/{branch}/{path}"


class EmptyDiscoveryReportError(Exception):
    """The rule is in `DiscoveryReport`, and this is the only thing that may say it broke.

    Raised rather than returned as a Pydantic `ValidationError`, because the caller has
    something to do about this one that it cannot do about a malformed field: a report
    with one bad language is a report to ask the agent to fix, and a report that says
    nothing is a fault to be told about in our own words.
    """


class EvidenceOutsideRepositoryError(Exception):
    """The rule is in `evidence_for`, and this is the only thing that may say it broke."""


class EvidenceFile(BaseModel):
    """One file of the repository, and the address a reviewer opens to see it.

    The link is derived rather than asked for, so a model cannot name a host it likes.
    What the agent contributes is the path; the address follows from the repository the
    run is about, which is why building it needs no model at all.
    """

    path: str
    link: str


class DiscoveryReport(BaseModel):
    """What a repository is, in the terms a reader would plan against it.

    `evidence_files` is the paths these claims rest on, and it is not an inventory of
    the repository. An inventory is a fact that can be counted, so it is computed rather
    than asked for, and a model asked to produce one will produce a plausible list
    either way. What only the agent knows is which files it concluded something from,
    and naming them is what makes a human's approval worth something and what lets a
    test check a report against a repository that really exists.
    """

    languages: list[str] = []
    frameworks: list[str] = []
    build_system: str | None = None
    ci_system: str | None = None
    architecture_summary: str = ""
    key_components: list[str] = []
    evidence_files: list[EvidenceFile] = []
    suggested_changes: list[str] = []

    @field_validator("build_system")
    @classmethod
    def _refuse_a_tool_name_with_nothing_to_act_on(cls, what_was_written: str | None) -> str | None:
        """A build system must say what the build runs on, and a bare tool's name is not that.

        **Two real runs were refused at a gate over this field, and this is the rule they were
        asking for.** Asked to declare which Node version a project requires, the discovery
        report said `build_system: npm` — one word, and the shortest true one — while the same
        report's `key_components` carried the Dockerfile pinning `node:22-bookworm` in two
        `FROM` lines and its `architecture_summary` described the two-stage image in detail. The
        refusal said the report *"never records the runtime floors that would bound an engines
        range"*, and it was right, and it happened twice.

        **The prompt now asks the better question; this is what stops the answer from being the
        old one anyway.** A `str | None` accepts `npm` forever, and a type that accepts a bare
        noun keeps receiving one however the question is worded. The question is a request and a
        model may answer it briefly; this is the system saying what it is willing to accept.

        **Only this field, and the reason is the shape of the answer rather than a preference.**
        A one-word `languages` entry is a language, and a one-word `key_components` entry is a
        path. A build system's whole content is a version and the runtime carrying it, so a short
        answer there is a missing one rather than a terse one.

        **Absent is untouched.** A repository with no build system says so with `None` and the
        question tells the model to leave the field out rather than guess. Refusing `None` would
        force an invention for a repository that genuinely has none.

        **A build system named in words is enough when there are no versions to name.** `make`,
        `cargo` and a plain `npm` in a repository that pins nothing anywhere are the honest
        answers for repositories that declare no version, and this refuses a bare noun only when
        it stands alone as the entire answer.
        """
        if what_was_written is None:
            return None

        said = what_was_written.strip()
        if not said:
            return said

        names_more_than_the_tool = any(
            a_character.isdigit() or a_character in "/@ " for a_character in said
        )
        if not names_more_than_the_tool:
            raise ValueError(
                f"build_system is {what_was_written!r}, which names a tool and nothing else. This "
                "field answers what the build *runs on* — the command, and the runtime or image "
                "and version it pins when the repository declares one — because a person at a gate "
                "cannot rule on a change about a required runtime while holding a report that says "
                "only which tool. A repository that declares no version is not this case: name the "
                "command and, if there is one, the runtime."
            )

        return said

    def everything_it_says(self) -> tuple[object, ...]:
        """Every field's value, in the order the glossary lists them."""
        return (
            self.languages,
            self.frameworks,
            self.build_system,
            self.ci_system,
            self.architecture_summary,
            self.key_components,
            self.evidence_files,
            self.suggested_changes,
        )

    @model_validator(mode="after")
    def a_field_that_said_nothing_is_absence(self) -> DiscoveryReport:
        """A field holding whitespace becomes the absence this system already represents.

        **A reader counts the entries.** `suggested_changes` is a list a person reads as a
        count of what the agent thought this repository wanted, and a list holding one blank
        entry is a report claiming a suggestion it did not make. `build_system` is the
        opposite case and the reason `None` is left alone: a repository with no build system is
        a fact about the repository rather than a field the model failed to fill.

        **The same rule as the other two artifacts, for the same reason.** A fix written
        against the shape a bug was found in would be the third in this repository made where
        the finding was rather than where the rule is.
        """
        for a_field in type(self).model_fields:
            setattr(self, a_field, as_absence(getattr(self, a_field)))
        return self

    @model_validator(mode="after")
    def it_must_say_something_about_the_repository(self) -> DiscoveryReport:
        """At least one field must carry a value, or this is a fault and not a report.

        "At least one" and not "all of them", because a repository with no CI has
        nothing to say about CI and must be able to say so. Absence is representable,
        and a rule demanding every field would only ever be satisfied by a report that
        guesses.
        """
        if not any(a_value_that_says_something(value) for value in self.everything_it_says()):
            raise EmptyDiscoveryReportError(
                f"{THE_DISCOVERY_AGENT} reported nothing at all about the repository: "
                "every field was empty. That is a fault rather than an artifact, "
                "because a person cannot tell an empty report from a real one by "
                "looking at it."
            )

        return self


def evidence_for(paths: list[str], repository: Repository) -> list[EvidenceFile]:
    """The evidence for a set of paths, each with the address a reviewer opens.

    Every path is checked before any link is built, so a set containing one bad path
    produces no evidence at all rather than a report that is partly clickable.
    """
    return [_the_evidence_for(path, repository) for path in paths]


def _the_evidence_for(path: str, repository: Repository) -> EvidenceFile:
    if not _is_a_path_inside_the_repository(path):
        raise EvidenceOutsideRepositoryError(
            f"{path!r} is not a path inside {repository.owner}/{repository.name}, so it "
            "cannot be evidence. A report's links must stay on the repository the human "
            "was asked to approve, because that is where they will be clicked."
        )

    return EvidenceFile(
        path=path,
        link=WHERE_A_REVIEWER_READS_A_FILE.format(
            owner=repository.owner,
            name=repository.name,
            branch=repository.default_branch,
            path=path,
        ),
    )


def _is_a_path_inside_the_repository(path: str) -> bool:
    """Whether this string is a path in a repository, rather than a way out of one.

    Four shapes get out, and each is refused on its own terms: nothing at all, a URL
    with a scheme, a rooted path, and a `..` that climbs above the repository. A rooted
    path covers the protocol-relative `//host/...` too, since it is rooted.

    The `..` test looks at whole segments rather than looking for two dots, so an
    ordinary file called `app..tsx` is a file and not an escape.
    """
    if not path.strip():
        return False

    if "://" in path:
        return False

    if path.startswith("/"):
        return False

    return ".." not in path.split("/")
