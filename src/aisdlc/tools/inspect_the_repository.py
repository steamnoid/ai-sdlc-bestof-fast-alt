"""`an_inspection_of`: the text a model is asked to reason about a repository by.

The substrate is a clone, so this tool's question is not how to fetch a repository but
*which files of it* a model should be shown. It is a selection, and the selection is the
whole design: a repository has thousands of files, a model has a context, and whatever
decides between them must decide the same way every time or two runs of one work item
are not comparable and a report cannot be checked against the repository it describes.

The selection is what `DiscoveryReport` asks for and no more. The manifests say which
language and which build system, the README says what the project is for, the CI
configuration says whether there is any, and the top-level listing says what the project
is made of. Source files are not in it, because a discovery report is a summary of a
repository's shape and not a copy of its contents.

Everything is read through `read_file_in_the_project`, with the clone as the boundary.
That is not ceremony: a workflow file is a file a pull request can add, and a symlink
named `.github/workflows/ci.yml` pointing at `/etc` would otherwise be followed without
anything noticing.

A file that is not there is left out. That is what makes `ci_system: None` reachable
from a real run — a tool that failed on a repository without CI would leave the model
with nothing, and a model with nothing guesses, which is the exact reason `ci_system` is
optional.
"""

from __future__ import annotations

from pathlib import Path

from aisdlc.tools.filesystem_read import (
    PathNotInTheProjectError,
    a_path_in_the_project,
    read_file_in_the_project,
)
from aisdlc.tools.github_clone_repository import ClonedRepository

MANIFESTS = (
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Gemfile",
    "composer.json",
    "Makefile",
)

READMES = ("README.md", "README.rst", "README.txt", "README")

# Named separately rather than as a tuple of pairs: a missing comma there unpacks a
# string into characters, and a reader has no way to see the difference.
WHERE_WORKFLOWS_LIVE = ".github/workflows"
SUFFIXES_A_WORKFLOW_MAY_HAVE = (".yml", ".yaml")
CI_AT_THE_ROOT = (
    ".gitlab-ci.yml",
    ".circleci/config.yml",
    "azure-pipelines.yml",
    "Jenkinsfile",
)

A_LIMIT_ON_A_SINGLE_FILE = 20_000

# A limit on everything, because a context is finite and a selection with no ceiling is a
# repository pasted into a question. It is generous: enough for a real service's
# security-relevant surface, and small enough that a manifest is not the fourth of it.
A_LIMIT_ON_THE_WHOLE_INSPECTION = 120_000

# What a file has to be called to be shown to a model reasoning about a repository. **A name and
# not a parse, because a name is the only signal available without reading every file in the
# repository.** The list is deliberately a list: a parser for JavaScript routes would be a second
# language implementation in a tool whose job is to choose what to read, and it would be wrong on
# the eleventh language somebody writes.
#
# **It was a list of security words, and a real run found what that costs.** This inspection
# existed for discovery, whose job is a repository's shape, and the security analyst was later
# wired to the same one — so it was handed a directory listing and a `package.json` while being
# asked to find authentication problems, and a real run's gate refused the report for reasoning
# from filenames. The words below fixed that and were then applied to *every* consumer, which is
# the same mistake one level up: a run asked to change the Dockerfile's healthcheck was then
# never shown the Dockerfile, because `Dockerfile` is not a security word. The architecture
# analyst said so honestly — it reported no base image, no `HEALTHCHECK` directive and no interval
# — and the gate refused it for exactly that. **A selection framed around one consumer's question
# is the wrong selection for the others**, so the list is now what a *change* tends to touch:
# where security lives, and also what builds, deploys and configures.
WHAT_A_NAME_SAYS_A_FILE_MAY_MATTER = (
    # where security lives
    "auth",
    "authenticate",
    "authorization",
    "middleware",
    "session",
    "token",
    "secret",
    "credential",
    "password",
    "crypto",
    "permission",
    "role",
    "acl",
    "login",
    "signup",
    "user",
    "admin",
    "api",
    "route",
    "router",
    "controller",
    "handler",
    "env",
    "config",
    "policy",
    "cors",
    "cookie",
    "jwt",
    "oauth",
    "sanit",
    "validat",
    # where a build and a deployment are described — **added after a real run refused an
    # architecture report for never having opened the Dockerfile**, which is the file that
    # work item was about
    "dockerfile",
    "docker-compose",
    "compose",
    "makefile",
    "entrypoint",
    "deploy",
    "build",
    "setup",
    "requirements",
    "manifest",
    "migrat",
    "seed",
    "schema",
    ".env",
    ".gitignore",
)

# What a file has to end in to count as source at all. A repository's own `node_modules` and
# lockfiles are thousands of files and none of them is code anybody wrote for this project.
SUFFIXES_THAT_MAY_BE_SOURCE = (
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".py",
    ".rb",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".php",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".cs",
    ".swift",
    ".scala",
    ".ex",
    ".exs",
    ".sh",
    ".sql",
)

# Directories whose contents are somebody else's. Walking into one of these is how an
# inspection turns into a paste of a dependency tree.
DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE = (
    "node_modules",
    ".git",
    "vendor",
    "dist",
    "build",
    ".next",
    "coverage",
    "__pycache__",
    ".venv",
    "venv",
    "target",
)

# How deep the search goes. Deep enough to find `web-app/src/app/api/.../route.ts` and shallow
# enough that a generated tree cannot become the answer on its own.
HOW_DEEP_THE_SEARCH_GOES = 6

# A file whose name says what it is and carries no extension. **The `Dockerfile` and the
# `Makefile` are in this list, and a real run refused an architecture report for never having
# opened one.** The suffix filter above exists to exclude lockfiles, images and data — and it
# excludes exactly these two, because "no extension" is not a suffix it knows. So extensionless
# files are decided by name, and a `Dockerfile` is the most consequential file in a repository a
# deployment is described in.
FILES_NAMED_WITHOUT_AN_EXTENSION = (
    "dockerfile",
    "makefile",
    "procfile",
    "license",
    "notice",
    "authors",
    "codeowners",
    "jenkinsfile",
)


def an_inspection_of(clone: ClonedRepository) -> str:
    """The files a model is shown, and the listing that gives them context."""
    inside = clone.path

    sections = [
        _what_the_project_is(clone),
        _the_top_level_listing(inside),
        *_the_contents_of(inside, "manifests", MANIFESTS),
        *_the_contents_of(inside, "readme", READMES),
        *_the_ci_configuration(inside),
    ]

    return "\n\n".join(section for section in sections if section)


def an_inspection_of_the_code(clone: ClonedRepository) -> str:
    """Everything `an_inspection_of` shows, plus the code, plus what was left out.

    **Two inspections and not one, because two consumers want different things and sharing one
    is what broke.** A discovery report wants a repository's *shape*, and this module's own note
    that source files are not in it is right for that: a summary of a project is not a copy of
    it. A security analyst is asked to find authentication and authorization problems in the
    code, and a manifest and a README cannot answer either — so it was handed the shape, and
    reasoned from filenames, and a real run's gate refused the report for exactly that:

        "Six of the seven entries are then speculation from filenames and dependency
         declarations alone (findings 4, 5 and 7 reason from `Dockerfile`, `.dockerignore`
         and `bcryptjs` to MCP-endpoint, image-hygiene and cost-factor conclusions the report
         itself calls 'undecidable from the manifest')"

    **The closing section is the half that matters more than the code.** A model shown files it
    was not shown cannot tell that it was not shown them, and a reader cannot either — which is
    how a report about a repository that was never read reaches a gate looking like a report
    about one that was. So the inspection ends by naming what it left out, and a finding about a
    file that is not in that list is visibly a finding about nothing.
    """
    inside = clone.path

    what_was_shown, what_was_not = _the_source_that_may_carry_risk(inside)

    sections = [
        _what_the_project_is(clone),
        _the_top_level_listing(inside),
        *_the_contents_of(inside, "manifests", MANIFESTS),
        *_the_contents_of(inside, "readme", READMES),
        *_the_ci_configuration(inside),
        _the_source_is_below(what_was_shown),
        _what_was_not_shown(what_was_not),
    ]

    return "\n\n".join(section for section in sections if section)


def _the_source_that_may_carry_risk(inside: Path) -> tuple[list[str], list[str]]:
    """The source files whose names say a change might touch them, and the names of the rest.

    **Chosen by name and capped by characters, in that order.** A name is the only signal
    available without reading every file, and a cap is what keeps a large repository from becoming
    a paste. When the cap is reached the search stops and everything left goes into the "not
    shown" list — so a truncated inspection says it was truncated rather than looking complete.

    **The cap bites from the top down, not in an arbitrary order.** Sorted by depth and then by
    path, so the files nearest the root — which is where a `Dockerfile`, a `Makefile` and a
    `package.json` live — are the ones that survive it.
    """
    how_many_characters_are_spent = 0
    what_was_shown: list[str] = []
    what_was_not: list[str] = []

    for a_path in _every_source_file_in(inside):
        if not _this_name_says_a_file_may_matter(inside, a_path):
            # **Named rather than skipped, and this line is the fix.** A file the name filter
            # rejects is not a file that was considered and left out -- it is a file nobody in this
            # run ever knew about, which is a worse state than being left out, because a model
            # cannot notice a coverage it does not know it has. The section below promises to name
            # what was not shown, and a promise computed over the *filtered* set is true and
            # useless: a real gate read "every file whose name suggests it may carry risk is above"
            # alongside a report that reasoned about `web-app/src/lib/db.js`, a file no word of
            # the filter matches.
            what_was_not.append(a_path)
            continue

        its_text = _the_text_of(inside, a_path)

        if its_text is None:
            what_was_not.append(a_path)
            continue

        if how_many_characters_are_spent + len(its_text) > A_LIMIT_ON_THE_WHOLE_INSPECTION:
            what_was_not.append(a_path)
            continue

        what_was_shown.append(f"## {a_path}\n\n{its_text}")
        how_many_characters_are_spent += len(its_text)

    return what_was_shown, what_was_not


def _every_source_file_in(inside: Path) -> list[str]:
    """Every source file in this repository, nearest the root first, skipping nobody's code.

    **Every one of them, and not only the ones whose name suggests they matter.** The name filter
    decides which files get *read*; it used to decide which files *existed* as far as the
    inspection was concerned, so a file it rejected was invisible in both directions -- not shown,
    and not named as withheld. A model can notice a coverage it knows it has and cannot notice one
    it does not, which is how a report came to reason about `lib/db.js` while the inspection
    insisted that nothing had been left out. A real gate refused exactly that report.

    **Sorted by depth and then by path, so two runs of one work item are comparable.** An
    inspection whose order came out of the file system would be a different question each time,
    and a report checked against it would be checked against a different thing.
    """
    found: list[tuple[int, str]] = []

    for a_path in inside.rglob("*"):
        if not a_path.is_file():
            continue

        its_parts = a_path.relative_to(inside).parts
        if any(a_part in DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE for a_part in its_parts):
            continue
        if len(its_parts) > HOW_DEEP_THE_SEARCH_GOES:
            continue

        its_name = a_path.name.lower()
        if a_path.suffix not in SUFFIXES_THAT_MAY_BE_SOURCE and (
            its_name not in FILES_NAMED_WITHOUT_AN_EXTENSION
        ):
            continue
        found.append((len(its_parts), str(a_path.relative_to(inside))))

    return [a_path for _, a_path in sorted(found)]


def _this_name_says_a_file_may_matter(inside: Path, a_path: str) -> bool:
    """Whether this file's name is one a reader of a risk should be shown, judged by name alone.

    **A name is the only signal available without reading every file**, and a cap is what keeps a
    large repository from becoming a paste. `Dockerfile`, `Makefile` and `package.json` carry no
    extension, which is why they are listed separately: a run's gate refused a security report for
    reasoning from a `Dockerfile` this filter could not see.

    **And the order the cap bites in is depth first and then path**, so the files nearest the
    root -- which is where those three live -- are the ones that survive it.
    """
    its_name = Path(a_path).name.lower()
    return any(a_word in its_name for a_word in WHAT_A_NAME_SAYS_A_FILE_MAY_MATTER)


def _the_text_of(inside: Path, a_path: str) -> str | None:
    """One file's text, or `None` when it could not be read or is too large to be worth having.

    **Read through the confined reader, so a symlink out of the clone is refused rather than
    followed.** A repository is arbitrary input: a file named `auth.ts` is a file a pull request
    can add, and it can be a link to somewhere else on the machine.
    """
    try:
        read = read_file_in_the_project(
            a_path_in_the_project(project_directory=inside, path=a_path)
        )
    except PathNotInTheProjectError:
        return None

    if len(read.text) > A_LIMIT_ON_A_SINGLE_FILE:
        return None

    return read.text


def _the_source_is_below(what_was_shown: list[str]) -> str | None:
    """The code, under a heading saying the rest of this is the code rather than a summary."""
    if not what_was_shown:
        return None
    return "# The code that may carry risk\n\n" + "\n\n".join(what_was_shown)


def _what_was_not_shown(what_was_not: list[str]) -> str:
    """What this inspection left out, said plainly and first.

    **A model that knows its own coverage can be held to it, and a reader can too.** The whole
    finding of the run that produced this is a report reasoning about files nobody had shown it,
    and the reason it read as a report is that nothing said otherwise. This section is the
    otherwise.
    """
    if not what_was_not:
        return (
            "# What you were not shown\n\nNothing. Every file whose name suggests it may carry "
            "risk is above, and nothing was left out for being too large or too numerous."
        )

    return (
        "# What you were not shown\n\n"
        f"{len(what_was_not)} further source file(s) whose names suggested a change might touch "
        "them, and which are **not** above. A finding about one of these is a finding about a "
        "file nobody has shown you, and it has to say so rather than reason from the name — a "
        "real run's gate refused an architecture report for exactly that, having reported no "
        "base image and no healthcheck interval about a Dockerfile it had never been shown:\n\n"
        + "\n".join(f"- `{a_path}`" for a_path in what_was_not[:60])
        + (f"\n- and {len(what_was_not) - 60} more" if len(what_was_not) > 60 else "")
    )


def _what_the_project_is(clone: ClonedRepository) -> str:
    """Which repository, which commit, which branch — because every claim is about one.

    A model told about a repository without being told which one will answer in general
    terms, and the report it produces will be about a repository that looks like this
    one. The commit is here for the same reason it is in `ClonedRepository`: every later
    reference in the run is about a specific one.
    """
    return (
        "# The repository under inspection\n\n"
        f"clone at {clone.path}\n"
        f"branch: {clone.ref}\n"
        f"commit: {clone.commit}"
    )


def _the_top_level_listing(inside: Path) -> str:
    """What the project is made of, at one level.

    One level and not a tree, because the point is to name the shape rather than to
    enumerate it, and a tree of a large repository is a wall of directory names that
    answers nothing a summary cannot say more cheaply.
    """
    directories = sorted(entry.name for entry in inside.iterdir() if entry.is_dir())
    files = sorted(entry.name for entry in inside.iterdir() if entry.is_file())

    return (
        "## What is at the top level\n\n"
        f"directories: {', '.join(directories) if directories else 'none'}\n"
        f"files: {', '.join(files) if files else 'none'}"
    )


def _the_contents_of(inside: Path, what: str, names: tuple[str, ...]) -> list[str]:
    """Each named file that exists, with its text, under a heading naming it."""
    sections: list[str] = []

    for name in names:
        section = _the_section(inside, name, what)
        if section:
            sections.append(section)

    return sections


def _the_ci_configuration(inside: Path) -> list[str]:
    """Every CI file, not just the first.

    A repository may have both a workflow directory and a config file at the root, and
    which one actually runs is not ours to assume. The workflow directory is globbed
    rather than listed because the names in it belong to the repository.
    """
    sections: list[str] = []

    if (inside / WHERE_WORKFLOWS_LIVE).is_dir():
        for a_workflow in sorted((inside / WHERE_WORKFLOWS_LIVE).iterdir()):
            if a_workflow.is_file() and a_workflow.suffix in SUFFIXES_A_WORKFLOW_MAY_HAVE:
                section = _the_section(
                    inside,
                    f"{WHERE_WORKFLOWS_LIVE}/{a_workflow.name}",
                    "CI configuration",
                )
                if section:
                    sections.append(section)

    sections.extend(_the_contents_of(inside, "CI configuration", CI_AT_THE_ROOT))

    return sections


def _the_section(inside: Path, name: str, what: str) -> str | None:
    """One file's text, or nothing at all when the file is not there.

    Reading goes through the confined reader with the clone as the boundary, so a file
    that turns out to be a symlink out of the clone is refused rather than followed.
    A file too large to be worth the context is named and left out, because a truncated
    manifest is a manifest that lies about its own contents.
    """
    try:
        read = read_file_in_the_project(
            a_path_in_the_project(project_directory=inside, path=name)
        )
    except PathNotInTheProjectError:
        return None

    if len(read.text) > A_LIMIT_ON_A_SINGLE_FILE:
        return f"## {name}\n\n(omitted: {len(read.text)} characters, too large to read)"

    return f"## {name}\n\n{read.text}"

