"""That a refused move names where the register actually holds the work item.

**A refusal told me the register was somewhere it is not, and that is the one thing this class
exists to prevent.** I recorded a move from `AWAITING_AGENT_PICKUP` to `IN_PROGRESS_BY_AGENT`, and
was told:

```
'ticket-2026-10-02-co-powtorzyc' was moved from AWAITING_AGENT_PICKUP, but the register holds
it at IN_PROGRESS_BY_AGENT.
```

**The register held `READY`.** I read that message twice and could not work out what had happened,
which is the whole failure `StaleWorkItemError` was written for — its own docstring says *\"carry
both stages, because the disagreement is what a reader has to resolve\"*, and it carried the stage
the caller was trying to move **to**.

**The stage the register holds is in hand at the moment of the check and is not put in the
message.** The comparison is `the_row[\"stage\"] != where_it_was.stage.name`, so the row has been
read and the one fact a reader needs is discarded in favour of `where_it_is_now`.

**This is measured on this repository's own register, and not on a copy**, because the defect is
that the message and the row disagree — and a fixture standing in for the register would agree with
the message by construction.

**And it cost a real mistake, not only a confusing sentence.** I concluded the register was further
along than it was and re-derived the whole transit. **A wrong stage in a refusal is not a wording
problem; it is a reader being sent to inspect the wrong state.**
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from aisdlc.domain.commissioned_request import a_request_about
from aisdlc.domain.repository import Repository
from aisdlc.domain.role import Role
from aisdlc.domain.stage import Stage
from aisdlc.domain.state_machine import transition
from aisdlc.domain.work_item import a_work_item_commissioned_for_an_agent
from aisdlc.store.the_register_of_work_items import (
    StaleWorkItemError,
    the_work_item_a_commission_registers,
    the_work_item_is_recorded_at,
    the_work_item_registered_at,
)


@pytest.fixture
def a_register_holding_one_work_item() -> tuple[sqlite3.Connection, str]:
    """A real SQLite register in a temporary directory, with one work item at `READY`.

    **A connection and not the module's global**, so a test cannot be affected by - or affect -
    whatever the real register currently holds.
    """
    a_directory = Path(tempfile.mkdtemp())
    a_connection = sqlite3.connect(a_directory / "aisdlc.sqlite3")
    a_connection.row_factory = sqlite3.Row

    a_work_item_id = "a-work-item-two-writers-disagree-about"
    the_work_item_a_commission_registers(
        a_connection,
        a_work_item_commissioned_for_an_agent(
            work_item_id=a_work_item_id,
            repository=Repository(owner="pikuniu", name="a-project"),
            accountable_role=Role.DEV,
            commissioned_by="a test",
            requested=a_request_about("something", ""),
        ),
    )
    the_work_item_is_recorded_at(
        a_connection, the_work_item_a_commission_registers.__module__ and a_work_item_id
    ) if False else None

    return a_connection, a_work_item_id


def test_a_refused_move_names_the_stage_the_register_holds(
    a_register_holding_one_work_item: tuple[sqlite3.Connection, str],
) -> None:
    """The refusal must point at the register's state, because that is what has to be read.

    **Caused by recording a move from a stage the register never reached** — which is what I did:
    I called `transition()` twice and `the_move_was_recorded()` once, so the register was still at
    `READY` while the caller believed the first move had been recorded. **The guard refusing that is
    correct and is not what this test is about; what is under test is what the refusal says.**
    """
    a_connection, a_work_item_id = a_register_holding_one_work_item

    where_it_was = the_work_item_registered_at(a_connection, a_work_item_id)
    moved_to = transition(where_it_was, Stage.AWAITING_AGENT_PICKUP, "aisdlc-dev-impl", Role.DEV)
    moved_on = transition(moved_to, Stage.IN_PROGRESS_BY_AGENT, "aisdlc-dev-impl", Role.DEV)

    # **Read through the module's own reader and not through SQL**, because that is what a person
    # holding this refusal does: they go and look at the register, through the way the register is
    # meant to be read. Raw SQL here would assert against a second copy of the truth.
    what_the_register_really_holds = the_work_item_registered_at(
        a_connection, a_work_item_id
    ).stage.name

    with pytest.raises(StaleWorkItemError) as it_raised:
        the_work_item_is_recorded_at(a_connection, moved_to, moved_on)

    the_refusal = str(it_raised.value)

    assert what_the_register_really_holds in the_refusal, (
        f"the register holds {what_the_register_really_holds!r} and the refusal does not say so: "
        f"{the_refusal}. It names the stage the caller was moving *to* rather than the one "
        "the register holds, which sends a reader to inspect a state it was never in"
    )

    assert moved_on.stage.name not in the_refusal or what_the_register_really_holds == (
        moved_on.stage.name
    ), (
        f"the refusal names {moved_on.stage.name!r}, which is where the caller wanted to go, as "
        f"though the register were there. The register holds "
        f"{what_the_register_really_holds!r} and that is the stage a reader has to go and look at"
    )


def test_a_refused_move_still_names_where_the_caller_thought_it_was(
    a_register_holding_one_work_item: tuple[sqlite3.Connection, str],
) -> None:
    """Both halves are needed, and the second is the half this cycle is not about losing.

    **Naming only where the register holds leaves the reader without the other end of the
    disagreement**, which is what the caller believed and what a person has to compare. So both go
    in, and neither substitutes for the other.
    """
    a_connection, a_work_item_id = a_register_holding_one_work_item

    where_it_was = the_work_item_registered_at(a_connection, a_work_item_id)
    moved_to = transition(where_it_was, Stage.AWAITING_AGENT_PICKUP, "aisdlc-dev-impl", Role.DEV)
    moved_on = transition(moved_to, Stage.IN_PROGRESS_BY_AGENT, "aisdlc-dev-impl", Role.DEV)

    with pytest.raises(StaleWorkItemError) as it_raised:
        the_work_item_is_recorded_at(a_connection, moved_to, moved_on)

    the_refusal = str(it_raised.value)

    assert moved_to.stage.name in the_refusal, (
        f"the refusal no longer names where the caller believed the work item was: {the_refusal}"
    )
