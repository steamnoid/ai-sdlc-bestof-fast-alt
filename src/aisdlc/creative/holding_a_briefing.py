"""One repository that briefed itself, as a card on a board.

**A separate type from a work item, and the separation is the design.** A work item has a stage
and moves through gates. A briefing produces filings and has neither, so a board that put both on
one board would have to invent a stage for a briefing — and a stage nobody declared is a stage a
run can be moved into.

**The card says how many were found *and* how many were filed.** A card that only said what it
created cannot show a person what was passed over, and a briefing that proposed five and filed one
has told them nothing about the other four — which are the ones they might have wanted.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from aisdlc.domain.repository import Repository


class ARepositoryBriefedItself(BaseModel):
    """One repository, briefed, and what came of it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    briefing_id: str
    repository: Repository
    what_this_repository_is: str
    how_many_opportunities_were_found: int
    how_many_became_filings: int
    work_item_ids: list[str] = []

    def how_many_were_filed(self) -> int:
        """How many of the opportunities became issues on the outside world.

        **Fewer than were found, and the difference is the interesting number.** A briefing whose
        findings all became filings is a briefing nobody ruled on, and a briefing whose none did
        is a briefing that produced no work and said why.
        """
        return self.how_many_became_filings

    def in_words(self) -> str:
        """The card, in a sentence a person reads in a column."""
        return (
            f"{self.repository.address} — {self.how_many_opportunities_were_found} "
            f"opportunit{'y' if self.how_many_opportunities_were_found == 1 else 'ies'} found, "
            f"{self.how_many_became_filings} filed as issues"
        )
