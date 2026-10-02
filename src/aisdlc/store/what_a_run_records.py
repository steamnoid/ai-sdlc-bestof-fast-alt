"""The five moments a run happens, written into the register so a board can read it.

**Five functions, and there are exactly five places in this system where something becomes a
fact.** The engine already has a function for each — the node that moves a work item, the one
that files an artifact beside the clone, the one that leaves a note, the one that records a
decision, and the one that asks the gate. None of them knew about a board, and none of them
needed to: they write files, and a board is a reading of what a run wrote.

So this module is the write-through half, and it is deliberately not a second place any of
those five facts is *decided*. Each function here takes a value an engine function has already
computed and puts it in a table. A move is still a move because `transition` said so; a
decision is still a decision because the gate said so; a note is still a note because an agent
left one.

**Each one takes the register's lock and gives it back.** See `where_the_register_lives` for why
that lock is not optional.

**A failure to record is a failure to run.** A run that reasons for four minutes and then
cannot write what it did has produced a delivery nobody can audit, and the board showing the
wrong thing is worse than the board showing nothing — so nothing here swallows an error. The
alternative, a recorder that logs and carries on, is a register that disagrees with the run,
which is the exact bug this whole store was written to make impossible.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from aisdlc.approval.approval_decision import ApprovalDecision
from aisdlc.domain.work_item import WorkItem
from aisdlc.persistence.the_register_of_work_items import (
    a_work_item_is_left_where_its_run_happens,
)
from aisdlc.store.the_record_of_a_run import (
    a_decision_was_recorded,
    a_note_was_left,
    an_artifact_was_written,
    what_the_gate_is_asking_about,
)
from aisdlc.store.the_register_of_work_items import (
    the_work_item_a_commission_registers,
    the_work_item_is_recorded_at,
)
from aisdlc.store.where_the_register_lives import holding_the_register


def the_work_item_was_commissioned(work_item: WorkItem, projects_root: Path) -> WorkItem:
    """Put a new work item in both registers, and hand back the one that is there.

    **Two registers, one value, written from the same object in the same breath** — the SQLite
    copy a board reads, and the per-run `WorkItem.json` a resuming run reads. The docstring used to
    say the second *is* written, *by the composition root*, and **no composition root did it**: a
    run that was commissioned and then died before its first transition left nothing for `resume`
    to find, and the refusal said the work item was not registered when it plainly was.

    **A transition always wrote it, so the hole was only ever at the start** — which is why this
    looked right from inside a run that had moved. `the_work_item_is_recorded_at` writes
    unconditionally, so from the first transition on the file existed; what was missing was the
    moment a work item comes into being.

    **And the projects root is required rather than defaulted**, because where a run's register
    lives is a fact about this deployment, and a default would be a second place it could be.
    """
    with holding_the_register() as register:
        commissioned = the_work_item_a_commission_registers(register, work_item)

    a_work_item_is_left_where_its_run_happens(commissioned, projects_root)

    return commissioned


def the_move_was_recorded(where_it_was: WorkItem, where_it_is_now: WorkItem) -> WorkItem:
    """Record a move, and hand back what the register then says.

    **The register's answer and not the work item the caller passed in**, so everything after
    this reads the register and a run cannot hold a second version of where it is. That is the
    bug this shape exists to prevent: a register frozen at `AWAITING_AGENT_PICKUP` while a real
    run went through eight gates, with nothing in the run looking wrong.
    """
    with holding_the_register() as register:
        return the_work_item_is_recorded_at(register, where_it_was, where_it_is_now)


def something_the_run_said(work_item_id: str, what_happened: str) -> None:
    """Append one line to the run's story, in the order it happened.

    **A file captured by nothing.** Four real runs in the family this was built from printed
    their progress to a stream the test runner swallowed and showed only on failure, which is
    the one case a heartbeat exists for. The stream a board reads is the same story, and this
    is where it is written.
    """
    with holding_the_register() as register:
        an_artifact_was_written(register, work_item_id, what_happened)


def the_artifact_was_recorded(work_item: WorkItem, artifact_id: str) -> None:
    """Say on the story that this artifact now exists on disk, and nothing more.

    **A line in the story and not a row in an artifacts table.** A run already files every
    artifact beside its own clone, named after the artifact's own class, and that file is the
    record — a table beside it would be a second copy that could disagree with the first, and a
    board reading the table would be reading a copy. The name is the artifact's class, which is
    the one thing the file itself is named after, so the two cannot disagree about what exists.

    **The author is not recorded here and that is deliberate.** A file named `DiscoveryReport`
    does not say which agent wrote it, and a recorder that put `aisdlc-discover` next to it would
    be putting a fact in a field that no caller had. Whoever wants to know who wrote it reads the
    run's story, which says it at the moment the agent picked the work item up.
    """
    something_the_run_said(work_item.work_item_id, f"wrote {artifact_id}")


def the_note_was_recorded(work_item: WorkItem, said_by: str, what_was_said: str) -> None:
    """Record a note an agent left on the card.

    **The same three sentences the supervisor is handed**, so what a person reads on a card and
    what the supervisor reasons over are the same words. "What it could not settle" is the
    valuable one: it is the sentence a person would have asked for and did not.
    """
    with holding_the_register() as register:
        a_note_was_left(register, work_item.work_item_id, said_by, what_was_said)


def the_gate_started_asking(work_item_id: str, artifact_id: str, version: int) -> None:
    """Record which artifact the gate is asking about, before the question is put.

    **The one fact a killed run cannot rebuild.** Everything else a run can replay by reading
    what it already wrote to disk; which artifact it was in the middle of asking about, and at
    which version, is the question it had not yet got answered. Recording it first means a run
    killed between the recording and the answer is a run the board knows was waiting — which is
    what makes the "waiting" column mean something rather than being a guess from the stage.
    """
    with holding_the_register() as register:
        what_the_gate_is_asking_about(register, work_item_id, artifact_id, version)
    something_the_run_said(
        work_item_id, f"asked a person about {artifact_id} v{version}"
    )


def the_decision_was_recorded(decision: ApprovalDecision) -> None:
    """Record the answer, and the record it earned if it approved something.

    **A refusal leaves one decision and no approval**, and that is the finding rather than a
    defect. A run answered "no" at the requirements gate is one of the most ordinary things
    that happens here, and a board showing it is showing the truth.
    """
    with holding_the_register() as register:
        a_decision_was_recorded(register, decision)
    something_the_run_said(
        decision.work_item_id,
        f"{decision.decided_by} {'approved' if decision.approved else 'refused'} "
        f"{decision.artifact_id} v{decision.artifact_version}: {decision.reason}",
    )


def a_run_refused_to_go_on(work_item_id: str, why: str) -> None:
    """Say on the card that this run stopped, and why, in the run's own words.

    **Written where a reader will look and not into a trace**, because a run that stopped
    without saying why is indistinguishable from a run that was killed.
    """
    something_the_run_said(work_item_id, f"stopped: {why}")


def a_run_was_delivered(work_item_id: str, where_the_pull_request_is: str | None) -> None:
    """Say that this run delivered, and where, so the card's last line is the outcome."""
    if where_the_pull_request_is is None:
        something_the_run_said(work_item_id, "delivered")
        return
    something_the_run_said(work_item_id, f"delivered: {where_the_pull_request_is}")


def now_in_utc() -> datetime:
    """The moment, for a caller that has to stamp something and imports nothing for it."""
    return datetime.now(UTC)
