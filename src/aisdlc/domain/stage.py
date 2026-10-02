"""Where a work item is in its lifecycle. The set of values is closed."""

from __future__ import annotations

from enum import Enum


class Stage(Enum):
    """One lifecycle position of a work item.

    A stage is never a bare string, so this deliberately does not inherit from
    `str`: RULE 2.5 requires the domain's own type at every boundary.

    Each member's value is its own name. The numbers `auto()` would produce are
    opaque in a trace and shift meaning if a member is ever inserted, which
    would silently invalidate every checkpoint already written.
    """

    IDLE = "IDLE"
    AWAITING_AGENT_PICKUP = "AWAITING_AGENT_PICKUP"
    IN_PROGRESS_BY_AGENT = "IN_PROGRESS_BY_AGENT"
    AWAITING_HUMAN_APPROVAL = "AWAITING_HUMAN_APPROVAL"
    READY = "READY"
    DONE = "DONE"

    def in_words(self) -> str:
        """This stage as a sentence a person reads on a card.

        **`AWAITING_HUMAN_APPROVAL` becomes "waiting for a person to approve"** rather than
        its name, because a card is read by somebody who did not write the state machine and
        who should not have to know the vocabulary to find out whether a ticket needs them.
        """
        return _WHAT_EACH_STAGE_SAYS[self]


_WHAT_EACH_STAGE_SAYS = {
    Stage.IDLE: "commissioned, nobody has picked it up",
    Stage.READY: "commissioned and ready to be worked on",
    Stage.AWAITING_AGENT_PICKUP: "waiting for an agent to pick it up",
    Stage.IN_PROGRESS_BY_AGENT: "an agent is working on it",
    Stage.AWAITING_HUMAN_APPROVAL: "waiting for a person to approve",
    Stage.DONE: "delivered",
}
