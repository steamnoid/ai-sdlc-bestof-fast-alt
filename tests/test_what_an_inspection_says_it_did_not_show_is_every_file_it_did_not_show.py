"""The section saying what was not shown is the complement of what was shown — over every file.

**A real gate refused a security report over this, and it refused it because the inspection
told it there was nothing to refuse.** The report's `informational` item said
`web-app/src/lib/events.js` and `web-app/src/lib/db.js` were absent from the inspection, and the
inspection's own closing section had said *"Nothing. Every file whose name suggests it may carry
risk is above, and nothing was left out for being too large or too numerous."* The gate read
those two sentences together and said:

> …the report's own informational item states that `web-app/src/lib/events.js` and
> `web-app/src/lib/db.js` were absent from the inspection while the inspection's closing section
> claimed nothing was withheld, so severities are set on code the run says it never read.

**Both sentences were true, and together they are the defect.** The closing section is computed
over the files the *name filter* selected, and `db.js` and `events.js` were never selected: no
word in `WHAT_A_NAME_SAYS_A_FILE_MAY_MATTER` appears in either name. So they cannot appear under
"not shown" — a file that was never a candidate is not a candidate that was dropped.

**Which is a way of saying nothing, in the one place the inspection promised to say something.**
The section exists so that a model knows its own coverage: a finding about a file that was not
shown has to say so rather than reason from the name. But a model that has never heard of
`db.js` has no way to know it is outside its coverage — it is not an omission it can notice, it
is an absence of information, and the closing section actively tells it the coverage is complete.

**The fix is a change of set, not of wording, and that is why it is a test.** The list has to be
every source file in the repository that was not shown. Then `db.js` is named, the model can see
that it exists and has not seen it, and a finding about it has to say so — which is precisely
what the gate asked for. Whether the security analyst then reports a different severity is a
judgement about the model and belongs to the real tier; **what it is given to judge is a fact
about this module, and that is what is asserted here.**

**A skip and not a guess, for a repository with no source files at all.** There is then no
complement to compute and the section says nothing was withheld, which is true.
"""

from __future__ import annotations

from pathlib import Path

from aisdlc.domain.repository import Repository
from aisdlc.tools.github_clone_repository import (
    ClonedRepository,
)
from aisdlc.tools.inspect_the_repository import (
    DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE,
    HOW_DEEP_THE_SEARCH_GOES,
    SUFFIXES_THAT_MAY_BE_SOURCE,
    an_inspection_of_the_code,
)

A_REPOSITORY = Repository(owner="paligakrzychu", name="wellbeing-tracker-public")
A_FILE_NO_WORD_IN_THE_NAME_FILTER_MATCHES = "web-app/src/lib/db.js"
"""The file the refused run's report named, and the reason this file exists.

No word of `WHAT_A_NAME_SAYS_A_FILE_MAY_MATTER` appears in `db.js` — no `auth`, no `session`, no
`api`. It is a database wrapper, which is exactly as likely to carry a defect as any other file,
and exactly as likely to be named by a model reasoning about persistence.
"""


def _a_clone_with_these_files_beside_each_other(a_projects_root: Path) -> ClonedRepository:
    """A checkout holding one file the name filter selects and one it cannot.

    **Two files, chosen for the asymmetry rather than for their content.** `auth.js` matches
    `auth`; `db.js` matches nothing in the list. Between them they say what the defect is: both
    are source files in the repository, both are candidates for being read, and only one of them
    can ever be named under "what you were not shown".

    **Real directories, because the answer is a fact about what is on the disk** and a fixture
    that pretended to be a checkout would only prove what the fixture holds.
    """
    inside = a_projects_root / "repository"
    (inside / "lib").mkdir(parents=True)
    (inside / "lib" / "auth.js").write_text("export const verify = () => true;\n")
    (inside / "lib" / "db.js").write_text("export const query = () => rows;\n")
    return ClonedRepository(path=inside, ref="main", commit="0" * 40)


def _every_source_file_in_the_clone(a_clone: ClonedRepository) -> set[str]:
    """Every file in this clone that is source by extension, by name, or by either — no filter."""
    inside = a_clone.path
    every: set[str] = set()

    for a_path in inside.rglob("*"):
        if not a_path.is_file():
            continue
        its_parts = a_path.relative_to(inside).parts
        if any(a_part in DIRECTORIES_THAT_HOLD_SOMEONE_ELSES_CODE for a_part in its_parts):
            continue
        if len(its_parts) > HOW_DEEP_THE_SEARCH_GOES:
            continue
        if a_path.suffix in SUFFIXES_THAT_MAY_BE_SOURCE:
            every.add(str(a_path.relative_to(inside)))

    return every


def test_every_source_file_that_was_not_shown_is_named_as_not_shown(
    tmp_path: Path,
) -> None:
    """A source file the name filter skipped is still named under what was not shown.

    **The claim is about the union of two sets, and both halves are needed.** The inspection says
    nothing was withheld, *and* a file nobody has seen is missing from that statement — and those
    two facts together are what a gate read as "this report was written about files it was shown".
    Asserting either half alone would pass on today's code.

    **The whole inspection and not the section's own string**, because a section can list a file
    without the model being able to see it was omitted. What matters is that the file is present in
    what the model was handed, and present under the heading that means *not read*.
    """
    a_clone = _a_clone_with_these_files_beside_each_other(tmp_path)
    the_inspection = an_inspection_of_the_code(a_clone)

    every_source_file = _every_source_file_in_the_clone(a_clone)
    assert every_source_file, (
        "the fixture holds no source file by extension, so the comparison below would be between "
        "an empty set and an empty inspection"
    )

    was_shown = {a_path for a_path in every_source_file if a_path in the_inspection}
    was_not_shown = {
        a_path
        for a_path in every_source_file
        if a_path not in the_inspection
        and a_path in the_inspection.split("# What you were not shown")[-1]
    }

    assert was_not_shown == every_source_file - was_shown, (
        f"{sorted((every_source_file - was_shown) - was_not_shown)} are in this clone, are not in "
        "the inspection, and are not named under the heading that says what was not shown. That is "
        "the defect a real gate refused a report over: the section is computed over the files a "
        "*name filter* selected, so a file the filter never matched cannot be listed, and the "
        "closing sentence — *every file whose name suggests it may carry risk is above* — is true "
        "while the model has never heard of a file a finding is about to reason from.\n\n"
        f"The section said:\n{the_inspection.split('# What you were not shown')[-1].strip()}"
    )


def test_a_repository_with_no_source_files_at_all_still_says_nothing_was_withheld(
    tmp_path: Path,
) -> None:
    """A repository of documents has no complement, and the section says so rather than guessing.

    **The other direction, because "list everything not shown" can go wrong the other way.** A
    checkout holding no source file would otherwise produce a section naming every manifest and
    README as withheld, which is its own kind of lie: those files are above, in their own
    sections, and a model told they were not shown would distrust the whole inspection.
    """
    inside = tmp_path / "a-documentation-only-repository" / "repository"
    inside.mkdir(parents=True)
    (inside / "README.md").write_text("# a project\n")

    the_inspection = an_inspection_of_the_code(
        ClonedRepository(path=inside, ref="main", commit="0" * 40)
    )

    assert not _every_source_file_in_the_clone(
        ClonedRepository(path=inside, ref="main", commit="0" * 40)
    ), "the fixture holds a file of no source kind, so this case is not the one it claims"

    the_closing_section = the_inspection.split("# What you were not shown")[-1].strip()

    assert "Nothing" in the_closing_section, (
        f"a repository with no source files has nothing to have withheld, and the section says "
        f"something else: {the_closing_section}"
    )
