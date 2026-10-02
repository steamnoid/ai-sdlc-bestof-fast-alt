"""That reading the register does not commit a write it did not make.

**The register hands every caller the same connection, so a reader holds a writer's transaction
in its hands.** `_prepared` runs on every call — including on the functions that read and write
nothing — and it runs the schema through `executescript`, and `executescript` issues a `COMMIT`
before the script runs. So a caller asking "is this work item recorded?" is asking a question and
the answer arrives having made somebody else's write durable.

**It was not found by reading it; it was found by a board test failing 6 times in 25.**
`tests/test_a_run_from_a_request_to_a_delivery.py::test_a_run_started_from_the_board_reaches_delivered`
raised `sqlite3.OperationalError: cannot commit - no transaction is active` from inside
`_prepared`, every time, on a board polling every two seconds while a run wrote a decision in the
same second. That module's own docstring already names the contended case as ordinary and names
the wrong symptom — `InterfaceError: bad parameter or other API misuse`, which is what this did
before Python 3.12 made `executescript` tolerate an empty transaction.

**The open transaction here is opened by a raw `INSERT`, and that is the whole point.** Every
recorder in this module commits its own work, so commissioning one and then reading it back
proves nothing — the writer finished before the reader arrived. What a reader must never do is
commit **a transaction it did not open**, and on a connection shared by a board thread and a run
thread the transaction it did not open is the ordinary case: the other thread is mid-write.

**Why it matters and is not a performance note.** A work item moves through stages, and this
register is what a board shows a person deciding whether to approve. A read landing mid-move makes
a stage durable that the move has not finished recording, so the board shows a stage no transition
ever produced — the disagreement this repository's state machine exists to prevent, arriving from
inside the store instead of from a wrong edge in the table.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from aisdlc.domain.commissioned_request import a_request_about
from aisdlc.domain.repository import Repository
from aisdlc.domain.role import Role
from aisdlc.domain.work_item import WorkItem, a_work_item_commissioned_for_an_agent
from aisdlc.store.the_register_of_work_items import (
    the_work_item_a_commission_registers,
    the_work_item_registered_at,
)

A_WORK_ITEM_ID = "the-work-item-a-run-is-recording"
THE_REGISTER_FILE = "the-register.sqlite3"


@pytest.fixture
def the_register(tmp_path: Path) -> sqlite3.Connection:
    """One connection to an empty register file, set up the way the register sets one up.

    **`row_factory` and not a plain connection, because that is a fact about the connection the
    register hands out.** `the_register_lives_at` sets `sqlite3.Row` when it opens the file and
    `_a_work_item_from` reads `row["repository"]`, so a test opening its own connection without it
    measures a configuration no deployment has — and fails inside the reader rather than on the
    rule being tested.
    """
    connection = sqlite3.connect(tmp_path / THE_REGISTER_FILE)
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


@pytest.fixture
def a_work_item() -> WorkItem:
    """A commissioned work item, which is the only way a run's work enters the register."""
    return a_work_item_commissioned_for_an_agent(
        work_item_id=A_WORK_ITEM_ID,
        repository=Repository(owner="paligakrzychu", name="wellbeing-tracker-public"),
        accountable_role=Role.PO,
        commissioned_by="a person in a terminal",
        requested=a_request_about("record this move without a reader finishing it"),
    )


def test_a_reader_does_not_commit_a_write_it_did_not_make(
    the_register: sqlite3.Connection, tmp_path: Path, a_work_item: WorkItem
) -> None:
    """The reader answers its question and the other thread's write stays unfinished.

    **Visibility on this connection cannot answer it, so the question is asked elsewhere.** A
    `SELECT` on the writing connection reads that connection's own uncommitted rows, so "is it
    committed?" has no answer on the connection that did the write. A second connection to the
    same file cannot see an uncommitted row, which makes it the only place the question has a
    definite answer — and it is asked with raw SQL, because asking the register's own reader would
    run `_prepared` again and measure the thing under examination.
    """
    the_work_item_a_commission_registers(the_register, a_work_item)

    the_register.execute(
        "INSERT INTO transitions (work_item_id, frm_stage, to_stage, agent, moved_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (A_WORK_ITEM_ID, "READY", "AWAITING_AGENT_PICKUP", "aisdlc-po-analyze", "2026-10-02"),
    )
    assert the_register.in_transaction, (
        "the insert did not open a transaction, so this test cannot measure whether the reader "
        "committed one. That is a change in how this sqlite3 opens transactions implicitly, and "
        "the fix for it is in this test rather than in the register"
    )

    the_work_item_registered_at(the_register, A_WORK_ITEM_ID)

    someone_else = sqlite3.connect(tmp_path / THE_REGISTER_FILE)
    try:
        what_another_connection_can_see = someone_else.execute(
            "SELECT to_stage FROM transitions"
        ).fetchall()
    finally:
        someone_else.close()

    assert what_another_connection_can_see == [], (
        "a reader committed a write it did not make. `the_work_item_registered_at` writes nothing, "
        "and answering its question made another thread's half-finished write durable from "
        f"another connection: {what_another_connection_can_see}. A board reading this would show a "
        "stage no transition ever produced"
    )
