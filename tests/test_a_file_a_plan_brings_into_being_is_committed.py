"""A file the plan brings into being is committed, and for a while it was written and forgotten.

**The defect is the third list of three, and the code beside it already says there are three.**
`the_paths_the_plan_names` returns `files_to_change`, `files_to_add` and `tests_to_add`, and its
docstring records why the middle one exists: a real run asked for an endpoint, the route could
not be named anywhere, and the implementer was refused for writing the file the request was
about. So the rule that decides what a change may touch knows about all three lists.

`a_commit_recording_the_change` staged two of them. `git add -- <files_to_change> <tests_to_add>`,
and `files_to_add` was absent from that line — so a plan whose change *is* a new file had the
file written to the working tree, was committed without it, verified, and delivered. **The
change is on the disk and not in the history**, which is the one state this repository's own
README records as having shipped a delivery out of: a run wrote its files, reported a green
suite, and GitHub answered `No commits between main and aisdlc/…` forty-five minutes later.

**Why a plan adding a new file is ordinary and not an edge.** `files_to_add` was added to the
artifact for exactly that reason, and the planner's own prompt asks for it by name
(`name files this change creates that the inspection does not show`). Every change that
introduces a file goes through it, so this is the common path for a whole class of work rather
than a corner.

**The assertion is on `git`, and not on the function's arguments.** A guard that read the
`git add` line out of the source would be satisfied by staging the paths in a different order,
or by computing them through a helper that happens to be right today. What has to be true is
that after a change is committed, `git show --name-only` on the change's own commit names the
file — and that is a fact about a repository on disk, which is where the delivery reads it from.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aisdlc.agents.a_commit_recording_the_change import a_commit_recording_the_change
from aisdlc.agents.implement_the_plan import the_paths_the_plan_names
from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.tools.github_clone_repository import ClonedRepository

A_COMMAND_WHICH_TAKES_THE_PLAN_THE_REFUSAL_IS_THE_ANSWER_TO = (
    "add a route for a health check the repository does not have yet"
)
A_FILE_THE_CHANGE_BRINGS_INTO_BEING = "web-app/src/app/api/health/route.ts"
A_TEST_THE_CHANGE_ADDS = "tests/unit/health-route.test.ts"
A_FILE_THE_CHANGE_MODIFIES_IN_PLACE = "README.md"


def _git(a_clone: ClonedRepository, *arguments: str) -> str:
    finished = subprocess.run(
        ["git", *arguments],
        cwd=a_clone.path,
        capture_output=True,
        text=True,
        check=True,
    )
    return finished.stdout.strip()


@pytest.fixture
def a_clone_with_a_commit_to_branch_from(tmp_path: Path) -> ClonedRepository:
    """A real checkout with one commit in it, so a change is a commit rather than the first.

    **Made here rather than borrowed from the real tier.** This is a deterministic rule about
    what lands in a commit, so it belongs in the default suite where it runs in milliseconds and
    needs no model, no network and no container. What it asserts is a fact about `git`, and `git`
    is the only thing that can be asked about it.
    """
    a_repository = tmp_path / "the-origin.git"
    a_repository.mkdir()
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main"],
        cwd=a_repository,
        check=True,
        capture_output=True,
    )

    a_working_copy = tmp_path / "a-working-copy"
    a_working_copy.mkdir()
    for an_argument in (
        ("init", "--initial-branch=main"),
        ("config", "user.name", "a person"),
        ("config", "user.email", "a.person@example.invalid"),
    ):
        subprocess.run(
            ["git", *an_argument],
            cwd=a_working_copy,
            check=True,
            capture_output=True,
        )

    (a_working_copy / "README.md").write_text("# a project\n", encoding="utf-8")
    for an_argument in (
        ("add", "--", "README.md"),
        ("commit", "-m", "the first commit"),
        ("remote", "add", "origin", str(a_repository)),
        ("push", "-u", "origin", "main"),
    ):
        subprocess.run(
            ["git", *an_argument],
            cwd=a_working_copy,
            check=True,
            capture_output=True,
        )

    a_clone = tmp_path / "the-clone"
    subprocess.run(
        ["git", "clone", str(a_repository), str(a_clone)],
        check=True,
        capture_output=True,
    )

    return ClonedRepository(
        path=a_clone,
        ref="main",
        commit=_git(ClonedRepository(path=a_clone, ref="main", commit=""), "rev-parse", "HEAD"),
    )


def _a_plan_whose_change_is_a_new_file(
    the_directory_a_new_file_goes_in: str = "src/api",
) -> ImplementationPlan:
    """A plan that adds a file, changes a file and adds a test — the ordinary shape.

    **All three lists at once, because the defect is only visible with all three present.** A
    plan that only adds a file and a plan that also modifies one commit the same way, and the
    test that catches this has to be the one a person would actually hand the planner.
    """
    return ImplementationPlan(
        files_to_change=[A_FILE_THE_CHANGE_MODIFIES_IN_PLACE],
        files_to_add=[f"{the_directory_a_new_file_goes_in}/health.ts"],
        tests_to_add=[A_TEST_THE_CHANGE_ADDS],
    )


def test_the_paths_a_plan_accounts_for_include_a_file_it_brings_into_being() -> None:
    """The rule that decides what a change may touch knows about all three of a plan's lists.

    **Asserted first, and as a precondition of the commit test rather than as its subject.**
    The commit used to name two lists and this function three, and a test written only against
    the commit fails with a message about commits when the thing that is actually wrong is that
    two places disagree about what a plan contains. This says which is right, and says why.
    """
    a_plan = _a_plan_whose_change_is_a_new_file()

    what_the_plan_accounts_for = the_paths_the_plan_names(a_plan)

    assert a_plan.files_to_add[0] in what_the_plan_accounts_for, (
        f"{a_plan.files_to_add[0]!r} is a file the plan brings into being and it is not among "
        f"{what_the_plan_accounts_for}. This is the function the implementer is refused against, "
        "so a plan naming a new file is a plan whose new file the implementer may not write — and "
        "the docstring records the real run that asked for exactly that"
    )


def test_a_commit_records_every_path_the_plan_accounted_for(
    a_clone_with_a_commit_to_branch_from: ClonedRepository,
) -> None:
    """`git show` on the change's own commit names the new file, and not only the two lists.

    **The commit is asked, because a delivery asks.** `a_delivery_this_system_may_make` pushes
    this working tree and opens a pull request against the remote, so a file the commit does not
    carry is a file nobody receives — however well the suite ran and however green the
    verification reported it.
    """
    a_clone = a_clone_with_a_commit_to_branch_from
    a_plan = _a_plan_whose_change_is_a_new_file()

    for a_path in the_paths_the_plan_names(a_plan):
        where = a_clone.path / a_path
        where.parent.mkdir(parents=True, exist_ok=True)
        where.write_text(f"// {a_path}\n", encoding="utf-8")

    a_commit_recording_the_change(
        a_clone.path, a_plan, A_COMMAND_WHICH_TAKES_THE_PLAN_THE_REFUSAL_IS_THE_ANSWER_TO
    )

    the_change = _git(a_clone, "rev-parse", "HEAD")
    what_the_commit_shows = _git(a_clone, "show", "--name-only", "--format=", the_change)
    the_paths_the_commit_carries = set(what_the_commit_shows.split())

    not_carried = [
        a_path
        for a_path in the_paths_the_plan_names(a_plan)
        if a_path not in the_paths_the_commit_carries
    ]

    assert not not_carried, (
        f"{not_carried} are in the approved plan and are not in the commit the delivery pushes. "
        f"git show --name-only on {the_change} names {sorted(the_paths_the_commit_carries)}. So "
        "the change is on the working tree and not in the history, the suite was green on a file "
        "the pull request does not contain, and the one thing this stage exists to prevent — a "
        "delivery whose diff is empty — happens with a green verification rather than in spite of "
        "one. `the_paths_the_plan_names` has carried all three lists since a real run could not "
        "finish a change that added an endpoint; the commit is the second place that has to know "
        "the same three."
    )
