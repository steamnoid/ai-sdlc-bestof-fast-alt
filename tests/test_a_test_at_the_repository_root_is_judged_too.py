"""A test at the repository root is judged like every other test, and for a while it was not.

**A real model's plan was refused four times for the right thing and then answered with a test
at the repository root, and nothing in this system could refuse that.** The directory rule reads
a plan's test paths, works out the directory each sits in, and asks whether the repository keeps
its tests there. The first line of that loop skipped the repository root:

    if its_directory in ("", "."):
        continue

`Path("a.test.ts").parent.relative_to(clone)` is `.` for a file at the top level, so every
root-level test fell through the whole rule — not because the root is a legitimate test
directory, but because nobody wrote the case down. The runner's own `include` lines, which name
exactly which directories are collected, were never consulted for it.

**And the rule this file asks for is not "never the root".** A flat repository keeps its tests at
the top: `test_the_thing.py` beside `the_thing.py` is an ordinary Python layout, and a rule
refusing it would make this system unable to plan a first test for anything shaped that way. So
both directions are asserted, and the deciding evidence is the same evidence as everywhere else
in the function — what the runner announced, and failing that what the repository demonstrably
does.

**The second finding is in the same file and the same loop, and it is why this is one test file
rather than one test.** The runner's answer is consulted first and "wins", but the check is
skipped before it is reached, so on every input the runner's answer is ignored for a root-level
test. A rule with two halves where one of them is unreachable is a rule that reads as two and
behaves as one, and a test that only asserted the refusal would have been satisfied by a
function that had deleted the runner branch entirely.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.plan_the_change import (
    PlannedTestDirectoryNotCollectedError,
    _every_test_is_where_the_suite_will_look_for_it,
)
from aisdlc.tools.github_clone_repository import ClonedRepository

A_RUNNER_THAT_COLLECTS_TWO_DIRECTORIES = (
    "include: tests/unit/**/*.{test,spec}.ts, tests/integration/**/*.{test,spec}.ts\n"
    "  12 files passed"
)
"""A real vitest opening line, and the one this repository's own suite announces.

The root is not in it, so a test at the root is not collected. A pattern with no `**` in front
reaches nothing here, and the `tests/unit/**` prefix ends on a segment boundary so it does not
reach `tests` either — which is the distinction the function's own docstring says is "the whole
defect".
"""


def a_clone_where(a_project_root: Path, holds_a_test_at: str) -> ClonedRepository:
    """A checkout on disk, holding one test in the directory named.

    **A real directory rather than a fixture, because the question is what is on the disk.** The
    rule reads the file system, so a stubbed clone would answer a question about the stub — and
    the whole reason this rule exists is that a directory holding no test of its own is not a
    place the repository runs tests from.
    """
    inside = a_project_root / "repository"
    (inside / holds_a_test_at).mkdir(parents=True, exist_ok=True)
    (inside / holds_a_test_at / "test_the_existing_thing.test.ts").write_text("// one")
    return ClonedRepository(path=inside, ref="main", commit="0" * 40)


def test_a_test_at_the_repository_root_is_refused_when_the_runner_does_not_collect_it(
    tmp_path: Path,
) -> None:
    """The root is a directory like any other, and this runner does not collect it.

    **The refusal, and it names the test rather than the rule.** A person reading a refusal
    learns which file to move and why; a refusal naming a rule they cannot look up is a
    dead end at the one moment somebody is trying to act on it.
    """
    a_plan = ImplementationPlan(tests_to_add=["readme-node-version.test.ts"])
    a_clone = a_clone_where(tmp_path, holds_a_test_at="tests/unit")

    with pytest.raises(PlannedTestDirectoryNotCollectedError) as what_was_refused:
        _every_test_is_where_the_suite_will_look_for_it(
            a_clone, a_plan, A_RUNNER_THAT_COLLECTS_TWO_DIRECTORIES
        )

    assert "readme-node-version.test.ts" in str(what_was_refused.value), (
        f"the refusal does not name the file: {what_was_refused.value}"
    )


def test_the_runners_own_answer_decides_the_root_rather_than_being_skipped(
    tmp_path: Path,
) -> None:
    """A runner that collects the top level says so, and a test there is accepted.

    **The other direction, and it is what makes the first one a rule rather than a ban.** A
    pattern that reaches every directory — `**` with nothing before it — is a runner that
    collects the root, and a plan putting a test there is correct. A fix that simply removed the
    `continue` would refuse this, so the refusal in the test above would be green and the rule
    would be wrong.
    """
    a_plan = ImplementationPlan(tests_to_add=["readme-node-version.test.ts"])
    a_clone = a_clone_where(tmp_path, holds_a_test_at="tests/unit")

    _every_test_is_where_the_suite_will_look_for_it(
        a_clone, a_plan, "include: **/*.{test,spec}.ts\n  1 file passed"
    )


def test_a_flat_repository_keeps_its_test_at_the_root_and_the_plan_is_allowed(
    tmp_path: Path,
) -> None:
    """A repository whose tests sit beside its code is a repository with a root test directory.

    **The runner is silent, as it is on every real plan in this system.** `plan_the_change` asks
    the runner, the node that drives a real run hands it `THE_RUNNER_ANNOUNCED_NOTHING_YET`
    because the listing cannot be produced before the dependencies are installed — so the
    filesystem is the only evidence available on the common path, and this is that path.

    `test_the_thing.py` beside `the_thing.py` is an ordinary Python layout, and a rule refusing
    it would make this system unable to plan a first test for any repository shaped that way.
    """
    a_plan = ImplementationPlan(tests_to_add=["test_the_readme.py"])
    a_clone = a_clone_where(tmp_path, holds_a_test_at=".")

    _every_test_is_where_the_suite_will_look_for_it(a_clone, a_plan, "")


def test_a_root_test_in_a_repository_whose_runner_collects_only_tests_is_still_refused(
    tmp_path: Path,
) -> None:
    """The same file, a repository that has moved its tests in, and the refusal comes back.

    **The case the carve-out was hiding, and it is the one a real model produced.** The
    repository keeps every test under `tests/unit`, its runner announces that, and a plan puts a
    test at the root anyway: the suite passes identically on both sides of the change, the
    delivery carries a test nobody ever opened, and verification fails two stages later about a
    test that had never run. The fixture is shaped so the root holds *no* test, which is what
    makes the root a directory this repository does not run tests from.
    """
    a_clone = a_clone_where(tmp_path, holds_a_test_at="tests/unit")
    (a_clone.path / "package.json").write_text('{"name": "a-project"}\n')
    a_plan = ImplementationPlan(tests_to_add=["readme-node-version.test.ts"])

    with pytest.raises(PlannedTestDirectoryNotCollectedError):
        _every_test_is_where_the_suite_will_look_for_it(
            a_clone, a_plan, A_RUNNER_THAT_COLLECTS_TWO_DIRECTORIES
        )
