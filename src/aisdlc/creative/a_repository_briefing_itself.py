"""A repository briefs itself, a person picks, and the picks become work on the board.

**Two endpoints and a hold in between, and the hold is a person.** The other half of this product
takes a sentence somebody typed; this half takes a repository and asks what it should be given.
A briefing is a proposal about somebody else's work, and a proposal that becomes a ticket without
anybody choosing it is a backlog this system invented — so the answer is a list to read, and the
filing is a second call carrying the indices a person picked.

**The briefing clones read-only and forks nothing.** Every other clone in this system forks
first, because the run that follows pushes a branch. A briefing reads and proposes; a fork would
be a copy of somebody's repository created for a read and left behind by it.

**Filing is idempotent, and that is the whole of what a retry has to mean here.** An issue opened
twice is two tickets a person will each have to rule on, and a briefing retried because its
answer was slow is a briefing retried for a reason that happens. The filing is remembered
against the opportunity's own words, which a second process recomputes from the report on disk
rather than being told what the first one did.

**A briefing that found nothing is a 200 with an empty list.** "This repository has nothing
worth doing" is a true sentence about a repository and the most useful thing a briefing can
conclude. It is not a fault, it is not routed anywhere, and it is not a reason to invent three
opportunities so the board is not empty.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator

from aisdlc.agents.brief_this_repository import (
    Brief,
    cloning_a_repository_to_read_only,
    the_briefing_using_the_configured_model,
)
from aisdlc.creative.an_opportunity import AnOpportunity
from aisdlc.creative.filing_what_the_briefing_found import (
    AnIssueThatWasOpened,
    OpenTheIssue,
    filing_what_the_briefing_found,
)
from aisdlc.creative.holding_a_briefing import ARepositoryBriefedItself
from aisdlc.creative.is_creative_mode_on import (
    ACreativeSettingThatIsNotOnError,
    is_creative_mode_on,
    what_the_environment_allows,
)
from aisdlc.creative.the_opportunities_this_repository_offers import (
    TheOpportunitiesThisRepositoryOffers,
)
from aisdlc.domain.repository import Repository
from aisdlc.store.the_record_of_a_run import a_note_was_left
from aisdlc.store.what_a_run_records import something_the_run_said
from aisdlc.store.where_the_register_lives import holding_the_register
from aisdlc.tools.github_client import a_github_client, the_credential
from aisdlc.tools.github_clone_repository import RepositoryToClone, clone_repository
from aisdlc.tools.github_list_open_issues import (
    AnOpenIssue,
    ReadWhichIssuesAreOpen,
    the_issues_this_deployment_can_read,
)
from aisdlc.tools.github_open_an_issue import an_issue_for, open_an_issue
from aisdlc.tools.the_project_directory import where_projects_live

# A briefing's clone lives in a directory named after the briefing, under a root of its own, so
# it never shares a directory with a run's artefacts. `briefings` and not the repository's own
# `owner/name` shape: a briefing is not a work item and putting it in the work-item tree would
# make a board that reads that tree show a briefing as though it were something somebody asked for.
WHERE_A_BRIEFING_LIVES = "briefings"


# How a briefing's clone is fetched. **The same seam `the_lifecycle` has and the same default
# shape**, because a briefing is a run of reasoning over a clone and the two want the same thing:
# a place to change where a repository comes from without changing anything that reads it.
PlanTheBriefingsClone = Callable[[Repository, Path], RepositoryToClone]


class ABriefingSomebodyAskedFor(BaseModel):
    """A repository to brief, named by its two halves.

    **Two fields and not one `repository` string**, for the same reason `ARequestSomebodyMade`
    has two: a repository is two halves, and a single string would be `owner/name`, which is a
    shape `Repository` deliberately refuses to hold.
    """

    model_config = ConfigDict(extra="forbid")

    repository_owner: str
    repository_name: str

    @field_validator("repository_owner", "repository_name")
    @classmethod
    def _refuse_a_blank(cls, written: str) -> str:
        """Refuse a blank before anything tries to clone it.

        A blank owner names `github.com`, and a briefing of `github.com` is a briefing of
        nothing at all — a run that produces a plausible list of work for a repository that does
        not exist.
        """
        if not written.strip():
            raise ValueError(
                "a briefing needs a repository to read. A blank half names github.com, and a "
                "briefing of github.com is a briefing of nothing."
            )
        return written.strip()


class APicksSomebodyMade(BaseModel):
    """Which opportunities a person chose, by their position in the briefing.

    **A list of whole numbers and nothing else**, and the numbers are positions rather than
    identity: a briefing's opportunities are renumbered every time it is asked for, so an
    identifier here would be a thing that has to be minted, kept and expired. A position is a
    number a browser already had.

    **The words are not accepted here, and that is the point.** A browser that could send an
    opportunity back could choose what it says by editing it, and the ticket that became would be
    one nobody read. This endpoint chooses; the briefing writes.
    """

    model_config = ConfigDict(extra="forbid")

    which: list[int] = []

    @field_validator("which")
    @classmethod
    def _refuse_a_negative_position(cls, which: list[int]) -> list[int]:
        """Refuse a negative number, because no briefing has one and it is an off-by-one.

        A `-1` in a list of positions is either a "last one" convention that was never stated or
        an index computed by subtracting from a length, and either way the person did not choose
        anything — so this refuses rather than reading it as the last opportunity.
        """
        if any(a_position < 0 for a_position in which):
            raise ValueError(
                "these are positions in a briefing, counted from zero, and a negative one names "
                "nothing. A `-1` is a 'the last one' convention that was never stated or a "
                "length subtracted somewhere — and a person who meant the last opportunity can "
                "name it, because the list they were looking at had a number on it"
            )
        return which


class WhatABriefingFound(BaseModel):
    """What the briefing concluded, in the shape a browser and a person both need.

    **The opportunities and the note, and nothing about the run.** A briefing is a proposal, and
    the proposal is the whole of it. Carrying the run's stage or its agent here would make a
    briefing look like a work item on a board, and it is not one until a person picks it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    briefing_id: str
    about: Repository
    what_this_repository_is: str
    opportunities: list[AnOpportunity]
    what_the_briefing_could_not_settle: list[str]
    agent_judgement: str | None = None
    what_was_already_tracked: list[AnOpenIssue] = []


def where_a_briefings_clone_lives(briefing_id: str) -> Path:
    """Where this briefing's clone is, under a root of its own.

    **Its own directory and not the repository's own tree.** A run's artefacts live at
    `<root>/<owner>/<name>/<work item id>/`, and a briefing placed there would be a directory a
    board reading that tree could mistake for a work item. This one is a sibling of the whole
    tree, so the two kinds of thing cannot be confused by either a reader or a query.
    """
    return where_projects_live() / WHERE_A_BRIEFING_LIVES / briefing_id / "repository"


def a_briefing_id_for(repository: Repository) -> str:
    """A name for this briefing, from the repository and the moment, to the microsecond.

    **Microseconds and not seconds, and the idempotence test is why.** The name is a directory
    the clone is written into, and a briefing takes seconds rather than the twenty minutes a run
    takes — so two briefings of one repository inside the same second landed in the same directory
    and the second raised `DestinationNotEmptyError` on a directory it had made itself. A run's id
    can be a second-resolution timestamp precisely because a run is slow; a briefing's cannot,
    and the two ids are not interchangeable because they are not the same kind of thing.
    """
    return f"{repository.name}-{datetime.now(UTC):%Y%m%d-%H%M%S-%f}"


def a_repository_briefed_itself(
    repository: Repository,
    a_briefing: Brief | None = None,
    plan_the_clone: PlanTheBriefingsClone | None = None,
    read_which_issues_are_open: ReadWhichIssuesAreOpen | None = None,
) -> WhatABriefingFound:
    """Read this repository and say what work it could be given.

    **Cloned here and nowhere else, and read-only.** A briefing proposes; it does not write, so
    it forks nothing and needs no credential — which is why a machine with no `GITHUB_TOKEN` can
    still be asked what a public repository should be given.

    **The report is proved against the clone before it is returned**, so an opportunity naming a
    file the repository does not have is refused here and the model is asked again, rather than
    becoming a ticket a person is asked to rule on.

    **The repository's open issues are read here and shown to the briefing agent**, because a
    briefing that proposes work somebody has already filed is the most likely wrong answer this
    node can give — and it is paid for by a stranger, in a queue they cannot easily ignore. They
    are recorded on the report so that filing can refuse a duplicate against the same list the
    model was shown. **The list is what the model was shown, which is a limit**: an issue filed
    between the briefing and the pick is not in it, and that is a window worth naming rather than
    closing.

    **The briefing agent and the clone planner are both parameters, and both default.** The
    agent is the same shape the composition root closes over for the planner and the implementer
    — one callable, built from the deployment's model when the caller does not bring one — and the
    clone planner is `the_lifecycle`'s own `plan_the_clone`, because a briefing's clone is the one
    clone in this system that has a seam rather than being hard-wired. A test handing in a
    prepared briefing and a local address reaches the same code a real run does, and a reader
    comparing the three agents finds the same shape in all three.
    """
    if not is_creative_mode_on():
        raise ACreativeSettingThatIsNotOnError(
            "absent, which means this deployment was not asked to brief repositories"
        )

    the_briefing_id = a_briefing_id_for(repository)
    where = where_a_briefings_clone_lives(the_briefing_id)

    planning = plan_the_clone or cloning_a_repository_to_read_only()
    the_clone = clone_repository(planning(repository, where))

    what_was_already_tracked = (
        read_which_issues_are_open or the_issues_this_deployment_can_read()
    )(repository)

    the_briefing = a_briefing or the_briefing_using_the_configured_model()
    the_report = the_briefing(
        the_clone, repository, what_the_environment_allows(), what_was_already_tracked
    )

    _the_briefing_was_said(the_briefing_id, repository, the_report)

    return WhatABriefingFound(
        briefing_id=the_briefing_id,
        about=repository,
        what_this_repository_is=the_report.what_this_repository_is,
        opportunities=the_report.opportunities,
        what_the_briefing_could_not_settle=the_report.what_the_briefing_could_not_settle,
        agent_judgement=the_report.agent_judgement.the_text_of_the_note_this_is(),
        what_was_already_tracked=what_was_already_tracked,
    )


def _the_briefing_was_said(
    briefing_id: str,
    repository: Repository,
    the_report: TheOpportunitiesThisRepositoryOffers,
) -> None:
    """Say on the record that this briefing happened, and what it found.

    **A briefing is a run of reasoning and is recorded as one.** It is not a work item, so it has
    no stage and no gate — but it consumed a real model call against a real repository, and a
    record that shows only the tickets a person picked would make a briefing that found four
    things and had one chosen look identical to a briefing that found one.
    """
    how_many = len(the_report.opportunities)
    something_the_run_said(
        briefing_id,
        f"{repository.owner}/{repository.name} was briefed: {how_many} "
        f"opportunit{'y' if how_many == 1 else 'ies'}",
    )
    with holding_the_register() as a_register:
        a_note_was_left(
            a_register,
            briefing_id,
            "aisdlc-brief",
            the_report.agent_judgement.the_text_of_the_note_this_is(),
        )


def filing_the_picks_a_person_made(
    briefing: WhatABriefingFound,
    which: list[int],
    open_the_issue: OpenTheIssue,
) -> ARepositoryBriefedItself:
    """File each opportunity this person picked, and commission a work item for it.

    **A list of indices and not the opportunities themselves, because the browser sent indices.**
    Sending the whole opportunity back would let a browser choose *what the opportunity says* by
    editing it, and the ticket that became would be one nobody read. An index chooses; the words
    are the report's.

    **An index that is not in the list is refused by name, and the whole filing stops.** Filing
    two of three and refusing the third is a person who believed they chose three; filing none
    and saying so is a person who has to look again.
    """
    if not is_creative_mode_on():
        raise ACreativeSettingThatIsNotOnError(
            "absent, which means this deployment was not asked to brief repositories"
        )

    the_chosen = _the_opportunities_at(briefing, which)

    the_work_item_ids = filing_what_the_briefing_found(
        _the_report_behind(briefing),
        the_chosen,
        open_the_issue,
        briefing.what_was_already_tracked,
    )

    return ARepositoryBriefedItself(
        briefing_id=briefing.briefing_id,
        repository=briefing.about,
        what_this_repository_is=briefing.what_this_repository_is,
        how_many_opportunities_were_found=len(briefing.opportunities),
        how_many_became_filings=len(the_work_item_ids),
        work_item_ids=the_work_item_ids,
    )


def _the_opportunities_at(
    briefing: WhatABriefingFound, which: list[int]
) -> list[AnOpportunity]:
    """The opportunities these indices name, or a refusal naming every index that is not one."""
    how_many = len(briefing.opportunities)
    not_there = [an_index for an_index in which if not 0 <= an_index < how_many]

    if not_there:
        raise NotAnOpportunityInThisBriefingError(not_there, how_many)

    return [briefing.opportunities[an_index] for an_index in which]


def _the_report_behind(briefing: WhatABriefingFound) -> TheOpportunitiesThisRepositoryOffers:
    """The report these opportunities came from, rebuilt for the filing.

    **Rebuilt and not carried**, because `WhatABriefingFound` is what the browser was handed and a
    briefing held in memory alongside it would be a second copy of the same findings able to
    disagree with the one the person read.
    """
    from aisdlc.agents.what_an_agent_judged import WhatAnAgentJudged

    return TheOpportunitiesThisRepositoryOffers(
        about=briefing.about,
        what_this_repository_is=briefing.what_this_repository_is,
        opportunities=briefing.opportunities,
        what_the_briefing_could_not_settle=briefing.what_the_briefing_could_not_settle,
        agent_judgement=WhatAnAgentJudged(
            what_it_found=briefing.agent_judgement or "a briefing was asked for",
            what_it_could_not_settle="; ".join(briefing.what_the_briefing_could_not_settle)
            or "nothing",
            what_it_expects_next="a person picks which opportunities become work",
        ),
    )


def the_issue_opener_this_deployment_has() -> OpenTheIssue:
    """Open an issue against a real repository, as whoever this deployment is.

    **The credential is read here and nowhere else**, and a briefing that has picked nothing never
    reaches it — so a machine with no `GITHUB_TOKEN` can be asked what a repository should be
    given, and is only refused when somebody chooses to file something.
    """
    a_client = a_github_client()
    a_credential = the_credential()

    def opening(an_opportunity: AnOpportunity, repository: Repository) -> AnIssueThatWasOpened:
        return open_an_issue(an_issue_for(an_opportunity, repository), a_client, a_credential)

    return opening


class NotAnOpportunityInThisBriefingError(Exception):
    """Somebody chose an opportunity this briefing never proposed."""

    def __init__(self, which: list[int], how_many_there_are: int) -> None:
        """Name every index that was wrong, because a person picking again needs all of them."""
        super().__init__(
            f"{which} are not opportunities in a briefing that proposed {how_many_there_are}. "
            "This briefing is not filed at all, rather than partly filed, because a person who "
            "believed they chose three and got one has been told something false — and the "
            "briefing's opportunities are renumbered every time it is asked for, so an index from "
            "an earlier one is the likely cause"
        )
