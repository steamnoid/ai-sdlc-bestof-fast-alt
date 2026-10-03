"""Where a work item is, as an answer two readers can trust at the same time.
**Two functions, because there are two questions.** Commissioning asks *does this exist?* and
answers once, so a retry does not duplicate a ticket and a second commission does not reset a
run that has already been through gates. Recording asks *where is it now?* and answers every
time, so a work item that has been through eight gates says so at the eighth.
That split is not tidiness. A sibling project had one function doing both, and the result was a
register frozen at `AWAITING_AGENT_PICKUP` while a real run went through eight gates and opened a
pull request — **nothing in the run was wrong, so nothing in the run looked wrong.** No test saw
it: the unit tests made one move and the end-to-end test never read the stage back. It was found
by reading the register of a run that had plainly succeeded. One function can only answer one
question, and it answers whichever was written first.
**A lookup that finds nothing raises.** A run handed a work item nobody commissioned goes on to
produce eight plausible artifacts about a delivery nobody asked for, and every one of them looks
right — a model asked for a discovery report will produce a discovery report. Inventing a row
instead would be the same failure with a row in the database, which is harder to notice and
easier to mistake for data.
**The stage is versioned, and a stale write is refused before it overwrites anything.** A run
that has gone eight gates in six minutes has more than one writer: a board, an approval, a
supervisor. Last-writer-wins on a stage column is how a register ends up disagreeing with the
run it is recording.
**The `requested` text and the filing are stored whole and read back whole,** because a delivery
names the filing twice — the branch and the pull request's body — and both are read after several
moves. A register that dropped the filing on the first move would make a run commissioned from a
filing indistinguishable from a run commissioned from a sentence, and those are evidence for
different things.
**A SQLite file and not Postgres, and the reason is in `docs/what-this-project-learned.md`.** An
MVP whose first requirement is that a person can run it with no infrastructure cannot open with a
database server. The schema is ordinary SQL and the connection is a parameter, so a deployment
that needs Postgres changes one function.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime

from aisdlc.domain.commissioned_request import CommissionedRequest
from aisdlc.domain.repository import Repository
from aisdlc.domain.role import Role
from aisdlc.domain.stage import Stage
from aisdlc.domain.the_work_each_agent_has_done import TheWorkEachAgentHasDone
from aisdlc.domain.work_item import WorkItem

# Every table, in one string, created on first use rather than by a migration.
#
# **`CREATE TABLE IF NOT EXISTS` on every call** is a decision and not a shortcut: this is the
# only thing that creates the schema, so there is no migration to fall out of step with it, and a
# register opened on a fresh deployment and a register opened on a run's second process are the
# same code path. A deployment that later needs a version table for migrations has one place to
# add it.
_THE_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS work_items (
        work_item_id   TEXT PRIMARY KEY,
        repository     TEXT NOT NULL,
        stage          TEXT NOT NULL,
        role           TEXT NOT NULL,
        commissioned_by TEXT NOT NULL,
        agent          TEXT,
        requested      TEXT NOT NULL,
        work_done      TEXT NOT NULL,
        version        INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS transitions (
        work_item_id TEXT NOT NULL,
        frm_stage    TEXT NOT NULL,
        to_stage     TEXT NOT NULL,
        agent        TEXT,
        moved_at     TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS transitions_by_work_item ON transitions (work_item_id)
    """,
)
_THE_WORK_ITEM_COLUMNS = (
    "work_item_id, repository, stage, role, commissioned_by, agent, requested, work_done, version"
)
class NoSuchWorkItemError(Exception):
    """The register does not hold a work item, and will not invent one.
    **The only safe answer, and it is raised rather than defaulted.** Every caller of a lookup
    here is a run about to do work: read the clone, plan, write files, open a pull request. A
    lookup that returned a fresh work item would let a run that was handed an identifier nobody
    commissioned produce eight plausible artifacts about a delivery nobody asked for, and nothing
    downstream would look wrong — a model asked for a plan will produce a plan.
    """
    def __init__(self, work_item_id: str) -> None:
        """Name the identifier, because that is what whoever holds it has to check."""
        self.work_item_id = work_item_id
        super().__init__(
            f"{work_item_id!r} is not in the register. A run handed a work item nobody "
            "commissioned goes on to produce artifacts about a delivery nobody asked for, and "
            "every one of them looks right — so this raises rather than returning something"
        )
class StaleWorkItemError(Exception):
    """A move was recorded from a copy the register has already moved past.
    **Refused before it overwrites anything,** which is the whole point of a version. Two
    writers on one run is ordinary — a board, an approval arriving, a supervisor ruling — and
    last-writer-wins on a stage column is how a register ends up disagreeing with the run it is
    recording, which is a failure that is invisible from inside the run.
    """
    def __init__(self, work_item_id: str, said: str, held: str) -> None:
        """Carry both stages, because the disagreement is what a reader has to resolve.
        **The stages and not a counter of versions.** "You thought it was at
        AWAITING_AGENT_PICKUP and it is at IN_PROGRESS_BY_AGENT" says where the two writers
        parted company; "you had version 2" does not.
        """
        self.work_item_id = work_item_id
        super().__init__(
            f"{work_item_id!r} was moved from {said}, but the register holds it at {held}. "
            "Something else recorded a move in between, so this one is refused rather than "
            "applied — read the work item again and decide whether this move still makes sense "
            "from where it is now"
        )
def _prepared(connection: sqlite3.Connection) -> None:
    """Make sure the tables are there, and commit nothing while saying so.
    **One statement per `execute`, and not `executescript`, and the difference is the whole
    point of this function.** Every caller in this module runs it — including the five that read
    and write nothing — so whatever it does to the transaction, it does on behalf of readers. And
    `executescript` is documented to issue a `COMMIT` before it runs the script: a reader asking
    "is this work item recorded?" was making the last recorder's write durable, and a board
    polling every two seconds made a half-recorded stage durable on purpose. `execute` does not
    commit, which is why the schema is a tuple of statements rather than one string — a string
    would need splitting, and the only reason to split it would have been to hand it to
    `executescript` again.
    **And the cost of this function running on every call is paid deliberately.** It is a
    `CREATE TABLE IF NOT EXISTS` per table per call, which is not free; the alternative is
    remembering whether *this connection* prepared anything, and that is a fact two callers on one
    connection cannot both hold. Cheap and idempotent beats remembered and wrong.
    """
    for a_statement in _THE_SCHEMA:
        connection.execute(a_statement)
def _a_row_for(work_item: WorkItem, version: int) -> tuple[object, ...]:
    return (
        work_item.work_item_id,
        work_item.repository.address,
        work_item.stage.name,
        work_item.role.name,
        work_item.commissioned_by,
        work_item.agent,
        json.dumps(_the_request_on(work_item).model_dump(mode="json")),
        json.dumps(work_item.work_done.model_dump(mode="json")),
        version,
    )
class AWorkItemNobodyAskedForError(Exception):
    """A work item reached the register carrying no request.
    **The register requires one, and this is where that is said.** `WorkItem.requested` is
    optional in the domain because the engine's unit tests build work items directly and a
    request would have been noise in them. A register is the other end: a card is titled by
    the request, a run is commissioned by one, and a row whose title is nothing is a row a
    board has to render as a blank. So the register refuses it rather than inventing a title.
    """
def _the_request_on(work_item: WorkItem) -> CommissionedRequest:
    """The request this work item answers, or a refusal that it does not answer one."""
    if work_item.requested is None:
        raise AWorkItemNobodyAskedForError(
            f"{work_item.work_item_id!r} was put in the register without saying what was asked "
            "for. A card is titled by its request and a run is commissioned by one, so a row "
            "whose title is nothing is a row a board has to render as a blank — commissioning "
            "always goes through a request, and nothing else may write a work item here"
        )
    return work_item.requested
def _a_work_item_from(row: sqlite3.Row) -> WorkItem:
    owner, _, name = row["repository"].partition("/")
    return WorkItem(
        work_item_id=row["work_item_id"],
        repository=Repository(owner=owner, name=name),
        stage=Stage(row["stage"]),
        role=Role(row["role"]),
        commissioned_by=row["commissioned_by"],
        agent=row["agent"],
        requested=CommissionedRequest.model_validate(json.loads(row["requested"])),
        work_done=TheWorkEachAgentHasDone.model_validate(json.loads(row["work_done"])),
    )
def the_work_item_a_commission_registers(
    connection: sqlite3.Connection, work_item: WorkItem
) -> WorkItem:
    """Put a work item in the register if it is not there, and return what is there either way.
    **Asks *does this exist?* and answers once.** A retry must not duplicate a ticket, and a
    second commission of the same identifier must not reset a run that has already been through
    gates — which is the same shape of failure as the frozen register, wearing the other mask.
    So this never overwrites: the row that is already there is the answer, and it comes back.
    """
    _prepared(connection)
    already = connection.execute(
        f"SELECT {_THE_WORK_ITEM_COLUMNS} FROM work_items WHERE work_item_id = ?",
        (work_item.work_item_id,),
    ).fetchone()
    if already is not None:
        return _a_work_item_from(already)
    connection.execute(
        f"INSERT INTO work_items ({_THE_WORK_ITEM_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        _a_row_for(work_item, 0),
    )
    connection.commit()
    return work_item
def the_work_item_is_recorded_at(
    connection: sqlite3.Connection,
    where_it_was: WorkItem,
    where_it_is_now: WorkItem,
) -> WorkItem:
    """Record a move, and return what the register then says.
    **Two work items, because a move has a before and an after and the before is the whole of
    the lost-update check.** The register is asked whether it still holds `where_it_was`; if it
    does not, somebody else moved this work item while the caller was thinking, and the move is
    refused rather than applied.
    **No version counter, and that was tried first.** A version has to be *read* by the caller
    to be checked against, and a caller working from an in-memory copy does not know its own
    copy's version. Putting the version on `WorkItem` fixes it by carrying a fact about one
    particular database into every other use of a domain object. The stage the caller believes
    the work item is at is a fact the caller genuinely holds.
    """
    _prepared(connection)
    if where_it_was.work_item_id != where_it_is_now.work_item_id:
        raise StaleWorkItemError(
            where_it_is_now.work_item_id,
            f"{where_it_was.work_item_id} at {where_it_was.stage.name}",
            f"a different work item, {where_it_is_now.work_item_id}",
        )
    the_row = connection.execute(
        f"SELECT {_THE_WORK_ITEM_COLUMNS} FROM work_items WHERE work_item_id = ?",
        (where_it_is_now.work_item_id,),
    ).fetchone()
    if the_row is None:
        raise NoSuchWorkItemError(where_it_is_now.work_item_id)
    if the_row["stage"] != where_it_was.stage.name:
        # **The row's stage and not the caller's, and that was measured rather than argued.** A
        # refusal once said *"the register holds it at IN_PROGRESS_BY_AGENT"* while the register
        # held `READY`, because it named where the caller was going rather than where the register
        # was. **A refusal that names the wrong stage sends a reader to inspect a state the work
        # item was never in** — which is the one thing this class exists to prevent, and the row
        # has been read on the line above, so the fact was in hand.
        raise StaleWorkItemError(
            where_it_is_now.work_item_id,
            where_it_was.stage.name,
            the_row["stage"],
        )
    connection.execute(
        "UPDATE work_items SET stage = ?, agent = ?, work_done = ?, version = version + 1"
        " WHERE work_item_id = ?",
        (
            where_it_is_now.stage.name,
            where_it_is_now.agent,
            json.dumps(where_it_is_now.work_done.model_dump(mode="json")),
            where_it_is_now.work_item_id,
        ),
    )
    _a_move_was_recorded(connection, where_it_was, where_it_is_now)
    connection.commit()
    return the_work_item_registered_at(connection, where_it_is_now.work_item_id)
def _a_move_was_recorded(
    connection: sqlite3.Connection,
    where_it_was: WorkItem,
    where_it_is_now: WorkItem,
) -> None:
    """Append the move to the history, with the stage it came from as the caller saw it."""
    connection.execute(
        "INSERT INTO transitions (work_item_id, frm_stage, to_stage, agent, moved_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            where_it_is_now.work_item_id,
            where_it_was.stage.name,
            where_it_is_now.stage.name,
            where_it_is_now.agent,
            datetime.now(UTC).isoformat(),
        ),
    )
def the_work_item_registered_at(connection: sqlite3.Connection, work_item_id: str) -> WorkItem:
    """What the register says about one work item, or a refusal that it does not hold it."""
    _prepared(connection)
    found = connection.execute(
        f"SELECT {_THE_WORK_ITEM_COLUMNS} FROM work_items WHERE work_item_id = ?",
        (work_item_id,),
    ).fetchone()
    if found is None:
        raise NoSuchWorkItemError(work_item_id)
    return _a_work_item_from(found)
def the_work_items_this_register_holds(connection: sqlite3.Connection) -> list[WorkItem]:
    """Every work item, ordered by identifier so a board renders the same way twice."""
    _prepared(connection)
    return [
        _a_work_item_from(row)
        for row in connection.execute(
            f"SELECT {_THE_WORK_ITEM_COLUMNS} FROM work_items ORDER BY work_item_id"
        )
    ]
def the_moves_this_work_item_made(
    connection: sqlite3.Connection, work_item_id: str
) -> list[tuple[Stage, Stage, str | None, str]]:
    """Every move this work item made, oldest first, as (from, to, agent, when).
    **A history and not a column, because "where is it now?" is a question about the last of
    them.** A run that was killed and resumed asks this and then asks the board; a register that
    only held the current stage could answer the first question and not the second.
    """
    _prepared(connection)
    return [
        (Stage(row["frm_stage"]), Stage(row["to_stage"]), row["agent"], row["moved_at"])
        for row in connection.execute(
            "SELECT frm_stage, to_stage, agent, moved_at FROM transitions"
            " WHERE work_item_id = ? ORDER BY rowid",
            (work_item_id,),
        )
    ]
def the_identifiers_of_the_work_items_at(
    connection: sqlite3.Connection, stage: Stage
) -> Sequence[str]:
    """Which work items are at a stage, for a board that wants one column."""
    _prepared(connection)
    return [
        row["work_item_id"]
        for row in connection.execute(
            "SELECT work_item_id FROM work_items WHERE stage = ? ORDER BY work_item_id",
            (stage.name,),
        )
    ]
