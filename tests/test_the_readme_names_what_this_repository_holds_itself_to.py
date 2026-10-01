"""The README has to name every test file here, because twice it did not.

**Two failures of the same kind, and this is the second guard for it.** The tag feature landed
with eleven tests and a commit message describing a README section that was never written — the
edit anchored on a heading from another repository's README, so it silently did nothing, and the
commit went through because an unrelated line in the same edit did land. Two days later the README
still said "four test files" when there were six. **Both times a count or a name in the README went
stale without anything noticing**, and a stale count is the kind of thing a reader trusts.

**So the check is mechanical rather than a habit.** Every test file in this repository is compared
against the README's table of what each file holds this repository to. A new test file with no row
fails; a row naming a file that no longer exists fails. Neither can be satisfied by editing prose,
which is the failure mode being guarded against.

**Every test file, and the second failure of the same kind is this one.** It read `glob`, which
does not descend, so a test file in a tier's own directory — `tests/e2e/`, `tests/graph/` — was not
a test file this guard could see, and a whole tier could land undocumented with the guard green. The
claim is about the test files a reader can be sent to, and a reader arriving at `tests/e2e/`
followed from the README by exactly the same route as a reader arriving at `tests/`. **The
directory is read rather than assumed**, so a tier moved to a new path cannot quietly leave the
guard pointing at the old one.

**The table rather than a prose sentence, and that is the design.** A sentence can say "six test
files" and be wrong in a way no test can see; a table that has to list each one is wrong in a way
this can see. It also forces the useful half — saying what each file *holds the repository to*,
rather than what kind of test it is, which is the thing that goes stale when a file grows a second
purpose.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

THE_README = Path(__file__).resolve().parent.parent / "README.md"
THE_TESTS = Path(__file__).resolve().parent


def _the_test_files_that_exist() -> set[str]:
    return {
        a_file.name
        for a_file in sorted(THE_TESTS.glob("test_*.py"))
        if a_file.is_file()
    }


def _the_test_files_the_readme_names() -> set[str]:
    """Every `test_*.py` the README mentions in backticks, however it mentions it.

    **Any mention counts, not a table row.** The point is that a reader arriving at this repository
    can find the file from the README, and a guard that only accepted one particular format would
    fail on a perfectly good sentence.
    """
    what_the_readme_says = THE_README.read_text(encoding="utf-8")
    return set(re.findall(r"`(test_[a-z0-9_]+\.py)`", what_the_readme_says))


def test_the_readme_names_every_test_file_and_no_file_it_names_is_gone() -> None:
    assert _the_test_files_that_exist(), (
        "no test files were found, so this is comparing two empty sets and would pass forever"
    )

    the_files_that_exist = _the_test_files_that_exist()
    the_files_the_readme_names = _the_test_files_the_readme_names()

    undocumented = the_files_that_exist - the_files_the_readme_names
    assert not undocumented, (
        f"{', '.join(sorted(undocumented))} exists and the README does not say what it holds this "
        "repository to. A test file nobody can find is a claim nobody is reading, and this "
        "repository has now had a feature land that way — with a commit message describing "
        "documentation that was never written"
    )

    gone = the_files_the_readme_names - the_files_that_exist
    assert not gone, (
        f"the README names {', '.join(sorted(gone))} and there is no such file, so a reader is "
        "sent to look for something that is not there"
    )


def test_a_test_file_in_a_tier_of_its_own_is_a_test_file_this_repository_holds_itself_to(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A test file below `tests/` is named in the README, not only one sitting beside this file.

    **This is the third failure of the kind the guard above exists for, and the guard had the
    same hole the failures did.** The other two were a stale count and an unmentioned file; this
    one is a whole tier, because `glob` does not descend and `tests/e2e/`, `tests/graph/` and
    `tests/unit/` are where the tiers live. A guard that only looks at the files beside itself
    passes with an entire tier undocumented — and the tier is the part that touches a real model,
    so it is the part a reader most needs to find.

    **Asked of a directory built here rather than of the repository's own layout**, because the
    claim is about the guard's reach and the repository may hold no subdirectory at all today. A
    test that passed because the layout happened to suit it would be green for the wrong reason,
    which is what the two guards before it were.

    **The file is named in a README this test writes**, so the assertion is about discovery and
    not about this repository's current documentation — a second copy of the README in `tmp_path`
    would have made the failure a claim about prose rather than about reach.
    """
    a_tier = tmp_path / "tests" / "e2e"
    a_tier.mkdir(parents=True)
    (a_tier / "test_a_stage_against_a_real_model.py").write_text("", encoding="utf-8")

    a_readme = tmp_path / "README.md"
    a_readme.write_text("`test_a_stage_against_a_real_model.py`", encoding="utf-8")

    monkeypatch.setattr("tests.test_the_readme_names_what_this_repository_holds_itself_to.THE_TESTS", a_tier.parent)
    monkeypatch.setattr(
        "tests.test_the_readme_names_what_this_repository_holds_itself_to.THE_README", a_readme
    )

    the_files_that_exist = _the_test_files_that_exist()
    the_files_the_readme_names = _the_test_files_the_readme_names()

    assert the_files_that_exist == {"test_a_stage_against_a_real_model.py"}, (
        f"a test file sitting in tests/e2e/ was not seen at all, so no naming of it in any "
        f"README could be checked. The guard looked in {THE_TESTS} and found "
        f"{sorted(the_files_that_exist)}, which means a whole tier can land undocumented with "
        "this guard green — and the tier is the part that asks a real model."
    )
    assert not the_files_that_exist - the_files_the_readme_names
