"""That a person can continue a run which died, and that a refusal reads as a sentence.

**`a_resumed_run_of` was written, never called, and never tested.** Two hundred and some lines in
`src/aisdlc/tools/`, reachable from nothing — and its own docstring claims *"the only way back into
it was to rebuild the state by hand"*, which is a sentence about a door somebody believed they had
opened. **Nothing in this repository can fail on that shape**: the default suite cannot fail on a
module no test imports, and the real tier cannot fail on a run nobody starts. A capability with no
caller is not half-built — it is invisible.

**It is needed rather than dead, and that is the part worth establishing.** The checkpointer is
`InMemorySaver`, so a run that reaches its third gate and then loses its process loses everything —
the checkpoint went with it. What survives is the work item in the register and the artifacts on
disk beside the clone. **That is exactly what this function reads**, and the lifecycle's own
docstring says a durable checkpointer is what would make a suspended approval survive a restart and
that this is a later phase. **So the resume path is the only thing between a person and losing four
gates of work to a terminal closing.**

**These two tests are about the door and nothing else, and that is a decision rather than a
shortcut.** The function's own contract — that a run resumed after three gates carries three
artifacts and presents the *fourth* — is asserted nowhere in this repository either, and writing
those tests means building a register that holds both what SQLite holds and what the resuming run
reads, because the two are written by different callers. **That is a real finding and it is
recorded as one; it is a second capability, and this cycle is the first.**

**A refusal has to read as a sentence here, and that is the half worth having.** Every other
command in this CLI already does it — `run` catches `ThisRunCannotBeAssembledError` and echoes the
message, because *a terminal reader is a person and a traceback is a thing a person hands to a
developer rather than reads*. A resume command that raised would hand four gates of work to a
traceback, which is the exact loss this capability exists to prevent.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from aisdlc.cli import aisdlc

A_REPOSITORY = "pikuniu/a-project"
A_RUN_NOBODY_STARTED = "a-run-this-deployment-never-began"
WHERE_PROJECTS_LIVE = "AISDLC_PROJECTS_DIR"


@pytest.fixture
def an_empty_deployment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A register and a projects root with nothing in them, because both of these stages write.

    **The register is opened here and not left to the first call that needs it**, because nothing
    opens a file on the spot in this repository — a process that serves a board or runs a pipeline
    calls `the_register_lives_at` once at startup. A fixture that skipped it would be testing a
    path no process takes.
    """
    from aisdlc.store.where_the_register_lives import (
        the_register_lives_at,
        where_the_register_should_live,
    )

    monkeypatch.setenv(WHERE_PROJECTS_LIVE, str(tmp_path / "projects"))
    the_register_lives_at(where_the_register_should_live())

    return tmp_path


def test_the_command_line_offers_a_way_to_continue_a_run() -> None:
    """A capability nobody can reach is not half-built, it is invisible.

    **Run through the real command-line application, and not by calling the function the command
    would call.** A double proves the function works; this proves there is something to call. That
    distinction is the whole of this cycle — `a_resumed_run_of` is correct and unreachable, and a
    test that imported it would have stayed green for ever.
    """
    what_a_person_typed = CliRunner().invoke(aisdlc, ["--help"])

    assert what_a_person_typed.exit_code == 0, (
        f"the command line would not even print its help: {what_a_person_typed.output}"
    )

    assert "resume" in what_a_person_typed.output, (
        f"`aisdlc --help` offers serve and run and no way to continue a run. The capability "
        "exists, is written, and is unreachable — and nothing in this repository would ever have "
        f"failed, because no test imported the module. What a person sees is: "
        f"{what_a_person_typed.output.strip()!r}"
    )


def test_a_run_nobody_started_is_refused_as_a_sentence_and_not_a_traceback(
    an_empty_deployment: Path,
) -> None:
    """Continuing a run that was never begun is a decision, and it is reported as one.

    **Read out of what the command printed, and not out of what it raised.** A command that refused
    correctly by raising would pass a test that caught the exception, and a person would still get a
    traceback — **which is the one thing this command must not do**, because the person it is for
    has just lost a terminal and is looking for their work, not for a stack.

    **No register entry, because this is a fresh deployment.** The command is reached on purpose
    with a work item id that was never commissioned, which is the cheapest way to prove it says
    something rather than blowing up, and it is the same refusal a person gets when they mistype an
    id.
    """
    what_a_person_typed = CliRunner().invoke(aisdlc, ["resume", A_REPOSITORY, A_RUN_NOBODY_STARTED])

    assert what_a_person_typed.exit_code != 0, (
        f"the command was asked to continue {A_RUN_NOBODY_STARTED!r}, which nobody began, and it "
        f"exited successfully saying nothing: {what_a_person_typed.output!r}"
    )

    assert "Traceback" not in what_a_person_typed.output, (
        f"the command handed a person a traceback:\n{what_a_person_typed.output}"
    )

    assert A_RUN_NOBODY_STARTED in what_a_person_typed.output, (
        f"the command refused without naming the run it refused: {what_a_person_typed.output!r}. A "
        "refusal that does not name what it is about is a refusal a person has to guess at"
    )


def test_a_work_item_commissioned_by_a_process_can_be_carried_on(an_empty_deployment: Path) -> None:
    """Commissioning a work item is what leaves the register a resuming run reads, and nothing does.

    **The whole of the defect in one test, and it is a production path on both sides.** A process
    commissions through `the_work_item_was_commissioned`, which writes SQLite — the copy a board
    reads. A resuming run reads the **per-run `WorkItem.json`**, written by a *different* function
    of the same name in `persistence/`, and **no production path calls that one.** So a run that
    was commissioned, ran four gates and lost its terminal leaves nothing the resume path can find,
    and `aisdlc resume` refuses a work item that demonstrably exists.

    **Commissioned and resumed by the two public functions a process uses**, because a test that
    reached into `persistence/` to write the missing file would pass while the hole stayed open —
    which is precisely what the four call sites in the default suite do today, and why this was
    green for as long as it was.
    """
    from aisdlc.agents.artifact import Artifact
    from aisdlc.domain.commissioned_request import a_request_about
    from aisdlc.domain.repository import Repository
    from aisdlc.domain.role import Role
    from aisdlc.domain.work_item import a_work_item_commissioned_for_an_agent
    from aisdlc.store.what_a_run_records import the_work_item_was_commissioned
    from aisdlc.tools.a_resumed_run_of import a_resumed_run_of

    the_repository = Repository(owner="pikuniu", name="a-project")
    the_work_item_id = "a-run-that-died-at-the-third-gate"
    the_work_item_was_commissioned(
        a_work_item_commissioned_for_an_agent(
            work_item_id=the_work_item_id,
            repository=the_repository,
            accountable_role=Role.DEV,
            commissioned_by="a person in a terminal",
            requested=a_request_about("add a health endpoint", ""),
        )
    )

    the_resumed = a_resumed_run_of(
        the_repository, the_work_item_id, Path(str(an_empty_deployment / "projects"))
    )

    assert the_resumed["presented_artifact_id"] == Artifact.DISCOVERY_REPORT, (
        f"a work item this process commissioned cannot be carried on: it presents "
        f"{the_resumed['presented_artifact_id']!r} instead of refusing, which means the two "
        "registers a run keeps are not the same register and nobody writes the one a resuming run "
        "reads"
    )
