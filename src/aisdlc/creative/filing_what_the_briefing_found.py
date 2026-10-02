"""Turning the opportunities a person chose into issues, and issues into work items.

**Filing is an external write, so it is gated — and a gate on the whole report is not a gate on
which five issues get opened.** `chosen` is what a person picked, and this function files exactly
that and nothing else. A briefing that proposed five and had three chosen opens three.

**Filing is idempotent, because it writes to the outside world.** §26 of the specification: a
retry must not create duplicate work items, and an issue opened twice is two tickets a person will
each have to rule on. A briefing retried because its answer was slow is a briefing retried for a
reason that happens. So the filing is remembered against the opportunity that produced it, and a
second attempt finds the first and does not open anything.

**The work item is born at `READY` carrying the number and the address GitHub returned.** `READY`
because nothing in the table of legal moves targets it, so a briefing cannot put a ticket in its
own queue. The filing because a request out of an issue and a request out of a sentence are
different evidence, and the delivery names the filing twice — once in the branch and once in the
pull request's body.

**The report's own findings are not handed to the work it created.** A work item is given the
opportunity's own words as its request and nothing else, and it runs its own discovery. A run that
inherits its predecessor's analysis is a run whose analysis was never checked by the gate that
approved the plan built on it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from aisdlc.creative.an_opportunity import AnOpportunity
from aisdlc.creative.the_opportunities_this_repository_offers import (
    TheOpportunitiesThisRepositoryOffers,
)
from aisdlc.domain.commissioned_request import CommissionedRequest
from aisdlc.domain.repository import Repository
from aisdlc.domain.role import Role
from aisdlc.domain.the_issue_this_answers import TheIssueThisAnswers
from aisdlc.domain.work_item import a_work_item_commissioned_for_an_agent
from aisdlc.store.what_a_run_records import the_work_item_was_commissioned
from aisdlc.store.where_the_register_lives import holding_the_register
from aisdlc.tools.github_list_open_issues import AnOpenIssue, the_issues_listed_as_tracked
from aisdlc.tools.the_project_directory import where_projects_live

# The name a filing is remembered under. **A hash of the opportunity's own words and not a
# counter**, because a counter is a thing a retry has to carry and a hash is a thing it can be
# recomputed from — so a briefing resumed in a second process finds the same filings without
# having been told what the first process did.
_THE_TABLE_OF_FILINGS_MADE = """
CREATE TABLE IF NOT EXISTS what_a_briefing_filed (
    a_run_of_this_briefing TEXT NOT NULL,
    what_was_filed TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    issue_address TEXT NOT NULL,
    work_item_id TEXT NOT NULL,
    PRIMARY KEY (a_run_of_this_briefing, what_was_filed)
);
"""

# The role an opportunity names, as a `Role`. A briefing writes a word for a person to read; a work
# item's role is a field the state machine reads, and this is where the two meet.
_THE_ROLE_A_WORD_NAMES = {
    "PO": Role.PO,
    "DEV": Role.DEV,
    "QA": Role.QA,
    "SEC": Role.SEC,
    "ARCH": Role.ARCH,
}


@dataclass(frozen=True)
class AnIssueThatWasOpened:
    """A GitHub issue that exists, with the number and the address GitHub answered with.

    **The address is the remote's own answer and never a composition.** A repository that was
    transferred keeps its issues where they were, so `…/issues/N` is a link to a page that has
    not been confirmed to exist — and this is the one fact a delivery later puts in a pull
    request's body.
    """

    number: int
    address: str


OpenTheIssue = Callable[[AnOpportunity, Repository], AnIssueThatWasOpened]


def filing_what_the_briefing_found(
    the_report: TheOpportunitiesThisRepositoryOffers,
    chosen: Sequence[AnOpportunity],
    open_the_issue: OpenTheIssue,
    what_was_already_tracked: Sequence[AnOpenIssue] = (),
) -> list[str]:
    """File each chosen opportunity as an issue and commission a work item for it.

    **Returns the work item ids, in the order the opportunities were chosen**, and each filing is
    skipped if this briefing has already made it. An empty list is the right answer when a person
    chose nothing, and it is not a refusal — a person who looked at five opportunities and picked
    none has made a decision.

    **The register is the process's, and not a parameter.** It is a single SQLite file holding
    every work item, and this repository reaches it through one connection guarded by one lock —
    see `where_the_register_lives`. A second `sqlite3.Connection` passed in beside it would be a
    second connection to the same file, and two connections are two writers, which is the exact
    failure the single lock exists to prevent.

    **No projects root, because filing does not touch the disk.** It writes to GitHub and to the
    register, and a parameter it does not read would be a claim about this function that is false.

    **A duplicate is refused before anything is opened, and that is the reason the list is here at
    all.** The briefing agent is shown the repository's open issues and told not to propose them
    again; a prompt is not a check, and the model may ignore the list or re-word the work it names.
    An issue that is opened and then found to be a duplicate has already landed in somebody's
    queue and can only be removed by a person closing it — so the refusal has to happen here,
    before `open_the_issue`, and not in the prompt that asked nicely.

    **The comparison is against the list the briefing was shown**, recorded on the report. An issue
    filed between the briefing and this pick is not in that list, and the window is real: the list
    is read once, at briefing time. That is a limit rather than a fix, and it is written down
    because a reader deciding whether this is safe needs to know it.
    """
    _the_table_was_prepared()
    the_work_item_ids: list[str] = []

    for an_opportunity in chosen:
        the_issues_listed_as_tracked(
            an_opportunity.what_could_be_done, what_was_already_tracked
        )

        what_was_filed = _what_identifies(an_opportunity)
        already = _the_filing_made_already(what_was_filed)

        if already is not None:
            the_work_item_ids.append(already)
            continue

        the_repository = _the_repository_this_report_is_about(the_report)
        the_issue = open_the_issue(an_opportunity, the_repository)
        the_work_item_id = _a_work_item_id_for(an_opportunity, the_issue.number)

        the_work_item_was_commissioned(
            a_work_item_commissioned_for_an_agent(
                work_item_id=the_work_item_id,
                repository=the_repository,
                accountable_role=_the_role_asked_for(an_opportunity),
                commissioned_by="aisdlc-brief",
                requested=CommissionedRequest(
                    title=an_opportunity.what_could_be_done,
                    body=an_opportunity.in_words(),
                    filed_as=TheIssueThisAnswers(
                        number=the_issue.number, address=the_issue.address
                    ),
                ),
            ),
            where_projects_live(),
        )
        _the_filing_was_remembered(what_was_filed, the_issue, the_work_item_id)
        the_work_item_ids.append(the_work_item_id)

    return the_work_item_ids


def _what_identifies(an_opportunity: AnOpportunity) -> str:
    """What a retry recomputes to find the filing this opportunity already produced.

    **The opportunity's own words and the files it shows,** and nothing about the run that filed
    it. A briefing resumed in a second process recomputes this from the report on disk and finds
    the first process's work, which is the whole of what "idempotent" has to mean for a write to
    the outside world.
    """
    return "|".join(
        [
            an_opportunity.what_could_be_done,
            an_opportunity.how_it_would_be_known_to_have_worked,
            *sorted(an_opportunity.the_files_that_show_this),
        ]
    )


def _a_work_item_id_for(an_opportunity: AnOpportunity, issue_number: int) -> str:
    """A work item id carrying the issue number, so a board can be scanned.

    **The number comes first and unqualified,** because a list of a hundred cards is read by
    scanning and a reader wants the filing's number in the same place on every line. A run's
    random suffix is not here: two briefings of one repository would collide, and a collision
    means one run reading another run's artifacts.
    """
    the_words = "".join(
        character if character.isalnum() else " "
        for character in an_opportunity.what_could_be_done
    ).lower().split()
    return f"issue-{issue_number}-{' '.join(the_words).replace(' ', '-')[:48]}"


def _the_repository_this_report_is_about(
    the_report: TheOpportunitiesThisRepositoryOffers,
) -> Repository:
    """The repository this briefing was about, which the report says by address.

    **The report carries it and not the caller passing it again.** A briefing's findings are
    about one repository, and a function that took the repository as an argument beside the report
    would be a function that could file an issue against a repository the report is not about.
    """
    return the_report.about


def _the_role_asked_for(an_opportunity: AnOpportunity) -> Role:
    """The discipline an opportunity names, or the one that would notice first.

    **Unknown words fall to `ARCH` and say so in a comment-free way — by taking the first role that
    accounts for understanding a codebase.** A briefing that names a discipline nobody recognises
    has made a work item nobody is accountable for, and a work item with no accountable discipline
    is one whose gates are being answered by whoever happened to open the board.
    """
    return _THE_ROLE_A_WORD_NAMES.get(
        an_opportunity.the_discipline_that_owns_it.strip().upper(), Role.ARCH
    )


def _the_table_was_prepared() -> None:
    """The table of filings made, created on first use — the only thing that creates the schema."""
    with holding_the_register() as a_register:
        a_register.executescript(_THE_TABLE_OF_FILINGS_MADE)


def _the_filing_made_already(what_was_filed: str) -> str | None:
    """The work item a previous attempt made for this opportunity, or `None`.

    **Keyed by the opportunity's own words and not by the briefing, so a retry in a second
    process finds the first one's work.** A briefing that was interrupted and is asked again
    recomputes this from the report on disk and recognises what it already filed, which is the
    whole of what idempotent has to mean for a write to the outside world.
    """
    with holding_the_register() as a_register:
        _the_table_was_prepared()
        found = a_register.execute(
            "SELECT work_item_id FROM what_a_briefing_filed WHERE what_was_filed = ?",
            (what_was_filed,),
        ).fetchone()
    return found[0] if found else None


def _the_filing_was_remembered(
    what_was_filed: str,
    the_issue: AnIssueThatWasOpened,
    the_work_item_id: str,
) -> None:
    """Write the filing down, so a retry finds it rather than opening a second issue."""
    with holding_the_register() as a_register:
        _the_table_was_prepared()
        a_register.execute(
            "INSERT OR IGNORE INTO what_a_briefing_filed"
            " (a_run_of_this_briefing, what_was_filed, issue_number, issue_address, work_item_id)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                what_was_filed[:80],
                what_was_filed,
                the_issue.number,
                the_issue.address,
                the_work_item_id,
            ),
        )
        a_register.commit()


def the_role_a_word_names(a_word: str) -> Role:
    """The discipline a word names, for a caller reading a briefing report rather than filing it."""
    return _THE_ROLE_A_WORD_NAMES.get(a_word.strip().upper(), Role.ARCH)

