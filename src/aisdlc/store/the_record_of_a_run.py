"""Everything a run says and leaves behind, in tables a browser and a supervisor can both read.

**Events are appended and never edited, because a board is a reading of them.** Every stage,
every artifact, every refusal and every gate goes in as it happens. A board that computed its own
state from the run would be a second source of truth, and a second source of truth is one that can
disagree with the first — which is the shape of the bug a sibling project shipped, where a
register and the run it was recording told two different stories and nothing in the run looked
wrong.

**A decision and an approval are two tables and a run's history is both.** A refusal leaves no
`Approval` — a refusal is a decision and not a gap — so a record built from approvals alone cannot
show a gate somebody answered "no" to, and one built from decisions alone would ignore which
answers earned a record. A run answered "no" at the requirements gate is one of the most common
things that happens here, and it is exactly what a record has to be able to show.

**The card is a table and not a file, because a supervisor is handed notes and a browser cannot
read a file.** Every agent that reasons leaves a note saying what it found, what it could not
settle and what it expects next. The repair supervisor is given those notes *whole* as its
evidence — a supervisor handed a summary is a supervisor guessing — and the run story shows them
too, because a decision nobody can find later is a claim.

**The presented artifact is cleared when it is answered.** A gate still holding a question after
it was answered would re-ask it on a resume, and a resumed run asking a person the same question
twice is worse than a run that stopped.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from aisdlc.approval.approval_decision import ApprovalDecision
from aisdlc.approval.approval_gate import the_record_left_by_a_decision
from aisdlc.domain.approval import Approval

_THE_TABLES = (
    """
CREATE TABLE IF NOT EXISTS artifacts (
    work_item_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    artifact_version INTEGER NOT NULL,
    written_by TEXT NOT NULL,
    written_at TEXT NOT NULL
)
    """,
    """
CREATE TABLE IF NOT EXISTS events (
    work_item_id TEXT NOT NULL,
    what_happened TEXT NOT NULL,
    happened_at TEXT NOT NULL
)
    """,
    """
CREATE INDEX IF NOT EXISTS events_by_work_item ON events (work_item_id)
    """,
    """
CREATE TABLE IF NOT EXISTS notes (
    work_item_id TEXT NOT NULL,
    said_by TEXT NOT NULL,
    what_was_said TEXT NOT NULL,
    said_at TEXT NOT NULL
)
    """,
    """
CREATE INDEX IF NOT EXISTS notes_by_work_item ON notes (work_item_id)
    """,
    """
CREATE TABLE IF NOT EXISTS decisions (
    work_item_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    artifact_version INTEGER NOT NULL,
    approved INTEGER NOT NULL,
    decided_by TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    reason TEXT NOT NULL
)
    """,
    """
CREATE INDEX IF NOT EXISTS decisions_by_work_item ON decisions (work_item_id)
    """,
    """
CREATE TABLE IF NOT EXISTS approvals (
    work_item_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    artifact_version INTEGER NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    reason TEXT NOT NULL
)
    """,
    """
CREATE INDEX IF NOT EXISTS approvals_by_work_item ON approvals (work_item_id)
    """,
    """
CREATE TABLE IF NOT EXISTS what_a_gate_is_asking_about (
    work_item_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL,
    artifact_version INTEGER NOT NULL
)
    """,
)



class WhatARunSaid(BaseModel):
    """One thing a run said it was doing, in the order it said it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    what_happened: str
    happened_at: datetime

    @field_validator("what_happened")
    @classmethod
    def _refuse_an_event_that_says_nothing(cls, what_happened: str) -> str:
        """Refuse a blank event.

        An event with nothing in it is a row a board has to render, and a board rendering
        nothing is indistinguishable from a run that stopped without saying why.
        """
        if not what_happened.strip():
            raise ValueError(
                "an event is something a run said it was doing. A blank one is a row a board has "
                "to render, and a board rendering nothing looks exactly like a run that stopped "
                "without saying why"
            )
        return what_happened


class AComment(BaseModel):
    """One note on the card, by an agent that reasoned, in the order it was left."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    said_by: str
    what_was_said: str
    said_at: datetime


def _prepared(connection: sqlite3.Connection) -> None:
    """Make sure the tables are there, and commit nothing while saying so.

    **One statement per `execute`, and not `executescript`, for the reason the register's own
    `_prepared` says.** Every caller runs this — including the readers — and `executescript`
    commits whatever transaction was open before the script, so a board reading a card made a
    run's half-recorded decision durable. `execute` does not commit, which is why the schema is a
    tuple of statements rather than one string: a string would need splitting, and the only reason
    to split it would have been to hand it back to `executescript`.
    """
    for a_statement in _THE_TABLES:
        connection.execute(a_statement)


class AnArtifactWasWritten(BaseModel):
    """One artifact at one version, by the agent that wrote it, at the moment it was written."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    work_item_id: str
    artifact_id: str
    artifact_version: int
    written_by: str
    written_at: datetime


def an_artifact_this_run_produced(
    connection: sqlite3.Connection, work_item_id: str
) -> list[AnArtifactWasWritten]:
    """Every artifact this work item has produced, in the order they were written.

    **Every version and not only the latest, because a run that was reworked is only auditable
    if the thing that was signed is still in the record next to the thing that replaced it.**
    """
    _prepared(connection)
    rows = connection.execute(
        "SELECT work_item_id, artifact_id, artifact_version, written_by, written_at"
        " FROM artifacts WHERE work_item_id = ? ORDER BY rowid",
        (work_item_id,),
    ).fetchall()
    return [
        AnArtifactWasWritten(
            work_item_id=row[0],
            artifact_id=row[1],
            artifact_version=row[2],
            written_by=row[3],
            written_at=datetime.fromisoformat(row[4]),
        )
        for row in rows
    ]


def how_many_times_this_artifact_has_been_rewritten(
    connection: sqlite3.Connection, work_item_id: str, artifact_id: str
) -> int:
    """How many versions of this artifact exist — one means nobody has reworked it.

    **Counted from the record and not from how many times an agent worked.** This project has a
    supervisor that hands a reworked artifact to a different agent, so an agent's own count does
    not move for the artifacts most likely to have been reworked — and a person who approved
    version 1 would have their approval read as covering a version they never saw.
    """
    _prepared(connection)
    how_many = connection.execute(
        "SELECT COUNT(*) FROM artifacts WHERE work_item_id = ? AND artifact_id = ?",
        (work_item_id, artifact_id),
    ).fetchone()[0]
    return int(how_many)


def a_plan_was_written(
    connection: sqlite3.Connection,
    work_item_id: str,
    artifact_id: str,
    written_by: str,
) -> AnArtifactWasWritten:
    """Write one artifact, at the version that writing makes it, and hand back what was written.

    **The version is read and then incremented, inside the same statement that writes it,** so
    two artifacts written for one work item cannot both claim to be version 1. A counter held in
    the record and a counter held on a work item disagree the moment a run resumes or two things
    write at once, and the disagreement is invisible from outside.
    """
    _prepared(connection)
    how_many_already = connection.execute(
        "SELECT COUNT(*) FROM artifacts WHERE work_item_id = ? AND artifact_id = ?",
        (work_item_id, artifact_id),
    ).fetchone()[0]
    the_written = AnArtifactWasWritten(
        work_item_id=work_item_id,
        artifact_id=artifact_id,
        artifact_version=how_many_already + 1,
        written_by=written_by,
        written_at=datetime.now(UTC),
    )
    connection.execute(
        "INSERT INTO artifacts"
        " (work_item_id, artifact_id, artifact_version, written_by, written_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            the_written.work_item_id,
            the_written.artifact_id,
            the_written.artifact_version,
            the_written.written_by,
            the_written.written_at.isoformat(),
        ),
    )
    connection.commit()
    return the_written


def an_artifact_was_written(
    connection: sqlite3.Connection, work_item_id: str, what_happened: str
) -> WhatARunSaid:
    """Say what the run is doing, and append it.

    **`what_happened` and not a level and a message.** A board asks one question — *what does this
    run say it is doing?* — and a record with a level and a message is two fields for one answer.
    """
    _prepared(connection)
    the_event = WhatARunSaid(
        what_happened=what_happened, happened_at=datetime.now(UTC)
    )
    connection.execute(
        "INSERT INTO events (work_item_id, what_happened, happened_at) VALUES (?, ?, ?)",
        (work_item_id, the_event.what_happened, the_event.happened_at.isoformat()),
    )
    connection.commit()
    return the_event


def the_events_this_run_produced(
    connection: sqlite3.Connection, work_item_id: str
) -> list[WhatARunSaid]:
    """What the run said, oldest first, as a board reads it."""
    _prepared(connection)
    return [
        WhatARunSaid(what_happened=row[0], happened_at=datetime.fromisoformat(row[1]))
        for row in connection.execute(
            "SELECT what_happened, happened_at FROM events WHERE work_item_id = ?"
            " ORDER BY rowid",
            (work_item_id,),
        )
    ]


def a_note_was_left(
    connection: sqlite3.Connection, work_item_id: str, said_by: str, what_was_said: str
) -> AComment:
    """Leave a note on the card, which is what the supervisor and the run story both read."""
    _prepared(connection)
    the_note = AComment(said_by=said_by, what_was_said=what_was_said, said_at=datetime.now(UTC))
    connection.execute(
        "INSERT INTO notes (work_item_id, said_by, what_was_said, said_at) VALUES (?, ?, ?, ?)",
        (work_item_id, the_note.said_by, the_note.what_was_said, the_note.said_at.isoformat()),
    )
    connection.commit()
    return the_note


def the_notes_on_the_card(connection: sqlite3.Connection, work_item_id: str) -> list[AComment]:
    """Every note on the card, oldest first.

    **Sorted by when and not by the order the database happens to return**, so two runs that got
    to the same place read the same way. The only order a reader would find wrong is the
    accidental one.
    """
    _prepared(connection)
    return [
        AComment(
            said_by=row[0], what_was_said=row[1], said_at=datetime.fromisoformat(row[2])
        )
        for row in connection.execute(
            "SELECT said_by, what_was_said, said_at FROM notes WHERE work_item_id = ?"
            " ORDER BY rowid",
            (work_item_id,),
        )
    ]


def a_decision_was_recorded(
    connection: sqlite3.Connection, decision: ApprovalDecision
) -> Approval | None:
    """Record the answer, and the record it earned if it approved something.

    **Returns the `Approval` and not `None` always,** so a caller can put the record where it goes
    without asking twice. A refusal returns `None` and *that is the finding* — see the module
    docstring.
    """
    _prepared(connection)
    connection.execute(
        "INSERT INTO decisions"
        " (work_item_id, artifact_id, artifact_version, approved, decided_by, decided_at, reason)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            decision.work_item_id,
            decision.artifact_id,
            decision.artifact_version,
            1 if decision.approved else 0,
            decision.decided_by,
            decision.when_it_was_decided().isoformat(),
            decision.reason,
        ),
    )

    the_record = the_record_left_by_a_decision(decision)
    if the_record is not None:
        connection.execute(
            "INSERT INTO approvals"
            " (work_item_id, artifact_id, artifact_version, approved_by, approved_at, reason)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                the_record.work_item_id,
                the_record.artifact_id,
                the_record.artifact_version,
                the_record.approved_by,
                the_record.approved_at.isoformat(),
                the_record.reason,
            ),
        )

    _the_gate_stopped_asking(connection, decision.work_item_id)
    connection.commit()
    return the_record


def _the_gate_stopped_asking(connection: sqlite3.Connection, work_item_id: str) -> None:
    """Forget the question once it has been answered.

    A gate still holding a question after it was answered re-asks it on a resume, and a resumed
    run asking a person the same question twice is worse than a run that stopped.
    """
    connection.execute(
        "DELETE FROM what_a_gate_is_asking_about WHERE work_item_id = ?", (work_item_id,)
    )


def the_decisions_this_run_collected(
    connection: sqlite3.Connection, work_item_id: str
) -> list[ApprovalDecision]:
    """Every answer this run got, refusals included, oldest first."""
    _prepared(connection)
    return [
        ApprovalDecision(
            work_item_id=row[0],
            artifact_id=row[1],
            artifact_version=row[2],
            approved=bool(row[3]),
            decided_by=row[4],
            decided_at=datetime.fromisoformat(row[5]),
            reason=row[6],
        )
        for row in connection.execute(
            "SELECT work_item_id, artifact_id, artifact_version, approved, decided_by,"
            " decided_at, reason FROM decisions WHERE work_item_id = ? ORDER BY rowid",
            (work_item_id,),
        )
    ]


def the_approvals_this_run_earned(
    connection: sqlite3.Connection, work_item_id: str
) -> list[Approval]:
    """Every record this run earned, which is fewer than the number of gates it passed.

    **Fewer, and that is the finding rather than a defect.** A refusal is a decision and leaves no
    record, so a run answered "no" at the first gate has one decision and no approvals — and a
    board showing that is showing the truth.
    """
    _prepared(connection)
    return [
        Approval(
            work_item_id=row[0],
            artifact_id=row[1],
            artifact_version=row[2],
            approved_by=row[3],
            approved_at=datetime.fromisoformat(row[4]),
            reason=row[5],
        )
        for row in connection.execute(
            "SELECT work_item_id, artifact_id, artifact_version, approved_by, approved_at, reason"
            " FROM approvals WHERE work_item_id = ? ORDER BY rowid",
            (work_item_id,),
        )
    ]


def what_the_gate_is_asking_about(
    connection: sqlite3.Connection, work_item_id: str, artifact_id: str, version: int
) -> None:
    """Record which artifact the gate is asking about, so a resumed run can ask again.

    **The one fact a killed run cannot rebuild.** Everything else it can replay by reading the
    artifacts it already wrote to disk; which artifact it was in the middle of asking about, and
    at which version, is the question it had not yet got answered.
    """
    _prepared(connection)
    connection.execute(
        "INSERT OR REPLACE INTO what_a_gate_is_asking_about"
        " (work_item_id, artifact_id, artifact_version) VALUES (?, ?, ?)",
        (work_item_id, artifact_id, version),
    )
    connection.commit()


def what_the_gate_was_asking_about(
    connection: sqlite3.Connection, work_item_id: str
) -> tuple[str, int] | None:
    """Which artifact and version the gate is asking about, or `None` when it is not asking."""
    _prepared(connection)
    found = connection.execute(
        "SELECT artifact_id, artifact_version FROM what_a_gate_is_asking_about"
        " WHERE work_item_id = ?",
        (work_item_id,),
    ).fetchone()
    if found is None:
        return None
    return found[0], found[1]
