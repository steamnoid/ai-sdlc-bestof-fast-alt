"""The API over one run, and the board it serves.

**No agent logic here, and that is the boundary.** Every endpoint either reads the store or hands
a decision to a run that is already parked. A model is not imported by this module and a file is
not written by it — §23 of the specification says the API calls application services, and in this
repository the service *is* the store plus the walk, and this module is the thin thing in front.

**The board is served as JSON and rendered by the browser, not assembled into HTML here.** A
server that rendered the board would have two renderings of it the day somebody wanted a second
surface, and a board nobody can script against is a board nobody can test. The `ui` tier drives
the real HTML in a real browser; the default suite drives this JSON.

**The event stream is Server-Sent Events and not WebSockets, because the traffic is one-directional
and the client is a browser.** What a run *says* flows out; what a person decides flows in on a
POST. A bidirectional protocol would be the more powerful answer to a problem this does not have.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, field_validator

from aisdlc.agents.brief_this_repository import Brief
from aisdlc.application.a_run_being_assembled import ThisRunCannotBeAssembledError
from aisdlc.application.the_runs_this_process_is_holding import (
    AWorkItemIsAlreadyBeingHeldError,
    AWorkItemIsStillWorkingError,
    NoSuchRunIsBeingHeldError,
    TheRunsThisProcessIsHolding,
    a_work_item_for,
)
from aisdlc.approval.approval_decision import ApprovalDecision
from aisdlc.approval.approval_gate import (
    AgentDecidedError,
    DecisionNotApplicableError,
    NotAtTheApprovalGateError,
    record_the_decision,
)
from aisdlc.creative.a_repository_briefing_itself import (
    ABriefingSomebodyAskedFor,
    APicksSomebodyMade,
    NotAnOpportunityInThisBriefingError,
    WhatABriefingFound,
    a_repository_briefed_itself,
    filing_the_picks_a_person_made,
    the_issue_opener_this_deployment_has,
)
from aisdlc.creative.is_creative_mode_on import ACreativeSettingThatIsNotOnError
from aisdlc.domain.commissioned_request import a_request_about
from aisdlc.domain.repository import Repository
from aisdlc.store.the_board_reads import (
    AColumnOfTheBoard,
    the_board_this_register_holds,
    what_the_board_can_say_about,
)
from aisdlc.store.the_record_of_a_run import (
    WhatARunSaid,
    the_approvals_this_run_earned,
    the_decisions_this_run_collected,
    the_events_this_run_produced,
    the_notes_on_the_card,
    what_the_gate_was_asking_about,
)
from aisdlc.store.the_register_of_work_items import the_work_item_registered_at
from aisdlc.store.what_a_run_records import something_the_run_said
from aisdlc.store.where_the_register_lives import (
    holding_the_register,
    the_endpoint_touches_the_register,
)
from aisdlc.tools.the_project_directory import where_projects_live

WHERE_THE_BOARD_IS_SERVED_FROM = Path(__file__).resolve().parent / "ui"

# How often the stream checks whether the run said something new. **A second is chosen for what
# it costs and not for how fast a model answers:** a board that lags by one second behind a
# four-minute stage is not a board anybody notices being late.
HOW_OFTEN_THE_STREAM_LOOKS_IN_MILLISECONDS = 1000


class ADecisionSomebodyMade(BaseModel):
    """A decision as it arrives from a browser, before the gate's own rules have seen it.

    **A separate type and not `ApprovalDecision` on the wire,** because the two do not agree about
    what is already true. Here `decided_by` is whatever a person typed and `decided_at` is when
    they pressed the button; in `ApprovalDecision` both have been checked, and an `aisdlc-`
    identifier has been refused. Building the domain type straight from a request body would mean
    the validation ran in the right place and the *refusal* came back as a 422 with a shape nobody
    reading a browser can use.
    """

    model_config = ConfigDict(extra="forbid")

    approved: bool
    decided_by: str
    reason: str

    @field_validator("decided_by", "reason")
    @classmethod
    def _refuse_a_blank(cls, written: str) -> str:
        """Refuse a blank name or a blank reason, before anything else looks at it.

        **Both are required, and a person in a terminal may not press the button without them.**
        A decision with no grounds is a coin flip written down at the one place a coin flip is
        worst, and a decision with no name is a record of nobody having decided.
        """
        if not written.strip():
            raise ValueError(
                "a decision names who decided and says why. Both are required, and both are "
                "recorded — a decision with no name is a record of nobody having decided"
            )
        return written.strip()


class ARequestSomebodyMade(BaseModel):
    """A repository and a sentence, as a person types them into the board.

    **Two fields for the repository rather than one, because a repository is two.** A single
    `repository` string would be `owner/name`, which is a shape this system's domain type
    deliberately refuses to hold — a `/` inside a half is refused precisely so that the halves
    cannot be ambiguous. Splitting them at the edge keeps that rule where it is written.

    **The sentence is required and the detail is not.** Most requests really are one line, and a
    body is the field a model will invent if it is asked for detail it was not given.
    """

    model_config = ConfigDict(extra="forbid")

    repository_owner: str
    repository_name: str
    asked_for: str
    any_more_detail: str = ""

    @field_validator("repository_owner", "repository_name", "asked_for")
    @classmethod
    def _refuse_a_blank(cls, written: str) -> str:
        """Refuse a blank before anything tries to clone it or reason about it.

        A blank owner names `github.com` and a blank sentence names nothing — and a run
        handed nothing goes on to produce eight plausible artifacts about a delivery nobody
        asked for, which is the failure a request is the one place to stop.
        """
        if not written.strip():
            raise ValueError(
                "a run needs a repository and a sentence saying what should change. A blank one "
                "names nothing, and a run handed nothing still produces artifacts"
            )
        return written.strip()


def _a_work_item_id_for(repository: Repository, asked_for: str) -> str:
    """A name nobody has used, because a work item's id is a branch, a directory and a thread.

    **The repository's name, a slug of the request, and the moment — in that order.** The
    repository comes first so a person can scan a list of branches and tell which project each is
    for; the moment comes last so two requests for the same repository in the same minute are
    still two runs. A uuid would need letters this system's branch rule refuses to carry, and a
    timestamp alone would collide the moment two people ask for something at once.

    **The slug is cut to a length a branch name can carry**, and cut at the end rather than
    trimmed word by word: a branch name is read in a list of branches, and a long one is a line
    that wraps. The moment is what makes it unique, so nothing is lost by cutting the prose.
    """
    the_moment = datetime.now(UTC)
    the_words = "".join(
        a_character if a_character.isalnum() else "-" for a_character in asked_for.lower()
    )
    the_slug = "-".join(a_part for a_part in the_words.split("-") if a_part)[:48].strip("-")

    return f"{repository.name}-{the_slug}-{the_moment:%Y%m%d-%H%M%S}"


# Briefings this process is holding, by id. **In memory, like the runs, and for the same
# reason** — a briefing is a proposal held until a person picks from it, and nothing durable is
# written until then. Asking again re-asks the model and produces a fresh list, which is why an
# index from an earlier briefing is refused rather than silently applied to a different one.
_the_briefings: dict[str, WhatABriefingFound] = {}


def the_api_over(
    a_register: sqlite3.Connection,
    the_runs: TheRunsThisProcessIsHolding,
    a_briefing: Brief | None = None,
) -> FastAPI:
    """The API for one register and the runs this process is holding, and the board it serves.

    **The register is a parameter and not a module-level global,** so a test can hold a register in
    a temporary directory and the application in production can hold one on disk, with no branch
    that says which.

    **The runs are a parameter for the same reason, and because they are not the same thing.** A
    register is a file that survives this process; a run is a compiled graph with a checkpoint in
    this process's memory. A board can read the first after a restart and the second not at all,
    and pretending otherwise is how a person ends up looking at a full board of runs that nobody
    is going to finish.

    **One lock for the whole process, and it is the store's lock and not a second one.** A SQLite
    connection opened with `check_same_thread=False` does not stop two threads interleaving
    cursors on it; it only stops SQLite complaining about *which* thread. This API runs in
    uvicorn's threads and the run it is serving runs in a thread of its own, and both of them
    write — so there are two writers and one connection, which is the contended case rather than
    an edge case.

    The first version of this file declared a lock of its own, `touching_the_register`, and that
    is precisely the bug: two locks on one connection is the same as no lock, and the symptom is
    `InterfaceError: bad parameter or other API misuse` from a `SELECT` that worked a moment
    earlier. The decorator here takes `holding_the_register` — the same lock the recorders take —
    so a board and the run it is showing are serialised against each other by construction
    rather than by two pieces of code each being careful.
    """

    the_app = FastAPI(title="aisdlc", docs_url=None, redoc_url=None)

    @the_app.exception_handler(RequestValidationError)
    def a_refusal_a_browser_can_show(
        the_request: Request, what_was_wrong: RequestValidationError
    ) -> JSONResponse:
        """A field that failed its own rule, said as a sentence and not as a shape.

        **The first error's message, with a 400, and not FastAPI's default 422.** The default
        answers with a list of objects naming a field, a location and a line — which is the right
        answer for a machine and useless for the one reader this API has. The board shows
        `detail` as text, so a refusal this system went to the trouble of naming would reach a
        person as `{"type": "value_error", "loc": ["body", "repository_owner"], ...}` and be
        invisible.

        This is not a preference about status codes. A 422 means "your request was malformed and
        I could not parse it", and every one of these is a request this system *understood* and
        then declined on purpose, which is a 400 and a sentence.
        """
        the_first = (
            what_was_wrong.errors()[0]["msg"]
            if what_was_wrong.errors()
            else "the request was refused, and said nothing about why"
        )
        return JSONResponse(status_code=400, content={"detail": the_first})

    @the_app.get("/health")
    def health() -> dict[str, str]:
        """Whether this process is up, and nothing else.

        **A liveness answer and not a readiness one.** It says nothing about a model being
        reachable, because an answer that did would make an orchestrator restart the process every
        time a gateway hiccuped — and the run it is running would still be parked at a gate.
        """
        return {"status": "ok"}

    @the_app.get("/")
    def the_board_page() -> FileResponse:
        """The board, as one HTML file with no build step and no bundler."""
        return FileResponse(WHERE_THE_BOARD_IS_SERVED_FROM / "index.html")

    @the_app.get("/ui/{a_file_name}")
    def a_file_of_the_board(a_file_name: str) -> FileResponse:
        """One file of the board — a script or a stylesheet."""
        return FileResponse(WHERE_THE_BOARD_IS_SERVED_FROM / a_file_name)

    @the_app.get("/api/board")
    @the_endpoint_touches_the_register
    def the_board() -> dict[str, object]:
        """Every card, in the order a person reads them, with the columns to read them in.

        **The columns come from the API and not from the browser, and that is the point.** A board
        that assembled its own columns in JavaScript would have two places where a stage becomes a
        column, and the two would agree until somebody added a stage in one of them.
        """
        return {
            "columns": [column.value for column in AColumnOfTheBoard],
            "cards": [
                a_card.model_dump(mode="json")
                for a_card in the_board_this_register_holds(a_register)
            ],
        }

    @the_app.get("/api/runs/{work_item_id}")
    @the_endpoint_touches_the_register
    def one_run(work_item_id: str) -> dict[str, object]:
        """Everything one run can be asked about: its card, its gates, its notes, what it said.

        **Three facts the store cannot hold, all about the run rather than its record.** Whether
        it is walking right now, how it ended if it did, and whether this process is holding it
        at all. A card reads `AWAITING_HUMAN_APPROVAL` for a run parked at a gate *and* for a run
        that died there, and those two look identical on a board — so the things only this
        process knows are answered here, where a caller that renders a card has somewhere to put
        them.

        **The third is the one that stops the board lying.** A parked run is a compiled graph
        with a checkpoint in this process's memory, so a restart forgets it while the register
        keeps the card and the pending question. Without this the answer was "not working, not
        ended, has a question" — which a browser renders as *waiting for you*, and clicking
        approve returns 410 from a gate nobody is listening at. A board that invites a decision
        it cannot record is worse than one that says the run is gone.
        """
        the_card = what_the_board_can_say_about(a_register, work_item_id)
        if the_card is None:
            raise HTTPException(status_code=404, detail=f"{work_item_id} is not on the board")

        return {
            "card": the_card.model_dump(mode="json"),
            "the_question": _the_question_about(a_register, work_item_id),
            "gates": [
                a_decision.model_dump(mode="json")
                for a_decision in the_decisions_this_run_collected(a_register, work_item_id)
            ],
            "approvals": [
                an_approval.model_dump(mode="json")
                for an_approval in the_approvals_this_run_earned(a_register, work_item_id)
            ],
            "notes": [
                a_note.model_dump(mode="json")
                for a_note in the_notes_on_the_card(a_register, work_item_id)
            ],
            "what_it_said": [
                an_event.model_dump(mode="json")
                for an_event in what_the_run_said(a_register, work_item_id)
            ],
            "is_still_working": the_runs.is_this_run_still_walking(work_item_id),
            "how_it_ended": the_runs.how_this_run_ended(work_item_id),
            "is_this_process_holding_it": the_runs.this_run_is_held_here(work_item_id),
        }

    @the_app.post("/api/runs")
    def a_run_was_asked_for(asked_for: ARequestSomebodyMade) -> dict[str, object]:
        """Commission a work item for this repository and this sentence, and start walking it.

        **This endpoint is the product.** Everything else here reads a run somebody started; the
        two projects this was assembled from had a board that could be looked at and a run that
        could be started only from a test. A person types a repository and a sentence, and a card
        appears immediately — before the clone, before the first model call — because a request
        that gives a card immediately and a slow run afterwards is answerable, and one that gives
        nothing for four minutes is not.

        **It returns before the run has done anything, and it is not lying.** The card it returns
        is real: it was commissioned and registered before this call returned. What the run will
        *find* is four minutes away, and the board is where a person watches that happen.

        **The work item id is derived from the repository and the moment, not supplied.** The id
        is the run's branch, its project directory and its graph thread; a caller choosing it
        would be choosing all three, and a collision would push a branch somebody else created.
        """
        the_repository = Repository(
            owner=asked_for.repository_owner, name=asked_for.repository_name
        )
        the_work_item_id = _a_work_item_id_for(the_repository, asked_for.asked_for)

        the_work_item = a_work_item_for(
            the_repository,
            the_work_item_id,
            a_request_about(asked_for.asked_for, asked_for.any_more_detail),
            where_projects_live(),
        )
        something_the_run_said(the_work_item_id, "a person asked for this")

        try:
            the_runs.a_run_was_started(the_work_item, where_projects_live())
        except AWorkItemIsAlreadyBeingHeldError as already_running:
            raise HTTPException(status_code=409, detail=str(already_running)) from already_running
        except ThisRunCannotBeAssembledError as cannot:
            raise HTTPException(status_code=503, detail=str(cannot)) from cannot

        return {
            "work_item_id": the_work_item_id,
            "repository": the_repository.address,
            "asked_for": asked_for.asked_for,
        }

    @the_app.post("/api/runs/{work_item_id}/decisions")
    def a_decision_was_posted(work_item_id: str, made: ADecisionSomebodyMade) -> dict[str, object]:
        """Hand this decision to the run it is about, and let the run record it.

        **The run records it and not this endpoint, and that is the single door.** The graph's own
        `record_what_was_decided` node validates the answer against what the gate actually
        presented and then writes it — so a decision that reaches the board has been through the
        gate, whoever sent it. This endpoint builds the decision and wakes the run; it does not
        write, and there is no version of this endpoint that does.

        **A refusal is a completed gate and returns 200.** A person saying no has been answered,
        and the run will stop at the next step. Answering 4xx for a refusal would teach a browser
        that "no" is an error, and the one decision a person is most sure about would look like
        the one that broke.

        **409 when the run is not parked**, which is a person clicking twice, a board replaying an
        answer, or a run that has already moved on. The gate's own version check would catch it
        too, but a second click that appeared to work and silently did nothing is worse than one
        that says why not.
        """
        with holding_the_register() as a_register:
            the_question = what_the_gate_was_asking_about(a_register, work_item_id)
        if the_question is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{work_item_id} is not waiting for an answer. A run that has already been "
                    "answered is not asked again — a decision posted here would be a decision "
                    "about a gate that is closed"
                ),
            )

        try:
            the_decision = ApprovalDecision(
                work_item_id=work_item_id,
                artifact_id=the_question[0],
                artifact_version=the_question[1],
                approved=made.approved,
                decided_by=made.decided_by,
                decided_at=datetime.now(UTC),
                reason=made.reason,
            )
        except ValueError as unusable:
            # A blank name or a blank reason. The rule lives on the type, so it fires here.
            raise HTTPException(status_code=400, detail=str(unusable)) from unusable

        # **The gate is asked before the run is woken, and then the run asks it again.** Two
        # calls to the same check, and the duplication is the point: the engine's gate refuses an
        # `aisdlc-` identifier, but it runs inside the graph, so a run woken with one would fail
        # in a thread and this request would have already answered 200. A browser needs the
        # sentence *now*, and a person who has just been told "approved" and then finds the run
        # dead has been told a lie by a 200. So the gate is consulted here, its answer discarded,
        # and the graph consults it again when it records — which is what makes "only the gate
        # writes a decision" true rather than nearly true.
        try:
            with holding_the_register() as a_register:
                the_work_item = the_work_item_registered_at(a_register, work_item_id)
            record_the_decision(the_decision, the_work_item, the_question[0], the_question[1])
        except (
            AgentDecidedError,
            NotAtTheApprovalGateError,
            DecisionNotApplicableError,
        ) as refused:
            raise HTTPException(status_code=400, detail=str(refused)) from refused

        try:
            the_runs.a_gate_was_answered(the_decision)
        except NoSuchRunIsBeingHeldError as not_here:
            raise HTTPException(status_code=410, detail=str(not_here)) from not_here
        except AWorkItemIsStillWorkingError as still_going:
            raise HTTPException(status_code=409, detail=str(still_going)) from still_going

        return {
            "recorded": True,
            "artifact_id": the_question[0],
            "artifact_version": the_question[1],
            "approved": the_decision.approved,
        }

    @the_app.post("/api/briefings")
    def a_briefing_was_asked_for(
        asked_for: ABriefingSomebodyAskedFor,
    ) -> dict[str, object]:
        """Read this repository and say what work it could be given.

        **This is the other half of the product, and it answers a different question from
        `POST /api/runs`.** That one takes a sentence somebody typed. This one takes a repository
        and asks it what it should be given, and it clones read-only, forks nothing and needs no
        credential — so a machine with no `GITHUB_TOKEN` can be asked this and is only refused
        when somebody chooses to file something.

        **It returns a list, not a decision.** Nothing is filed and no card appears: a briefing
        that became tickets without anybody choosing would be a backlog this system invented. The
        picks are a second call, and the hold in between is a person.

        **A briefing that found nothing is a 200 with an empty list**, because "this repository
        has nothing worth doing" is a true sentence and the most useful thing a briefing can
        conclude. It is not a fault, and it is not a reason to invent three opportunities so the
        board is not empty.
        """
        the_repository = Repository(
            owner=asked_for.repository_owner, name=asked_for.repository_name
        )
        try:
            the_briefing = a_repository_briefed_itself(the_repository, a_briefing)
        except ACreativeSettingThatIsNotOnError as not_on:
            raise HTTPException(status_code=400, detail=str(not_on)) from not_on
        except Exception as it_could_not_brief:
            raise HTTPException(
                status_code=503,
                detail=f"this repository could not be briefed: {it_could_not_brief}",
            ) from it_could_not_brief

        _the_briefings[the_briefing.briefing_id] = the_briefing

        return {
            "briefing_id": the_briefing.briefing_id,
            "about": the_briefing.about.address,
            "what_this_repository_is": the_briefing.what_this_repository_is,
            "opportunities": [
                an_opportunity.model_dump(mode="json")
                for an_opportunity in the_briefing.opportunities
            ],
            "what_the_briefing_could_not_settle": the_briefing.what_the_briefing_could_not_settle,
        }

    @the_app.post("/api/briefings/{briefing_id}/picks")
    def the_picks_a_person_made_were_posted(
        briefing_id: str, picks: APicksSomebodyMade
    ) -> dict[str, object]:
        """File the opportunities this person chose, and put each one on the board as a work item.

        **Indices and not the opportunities, because choosing and writing are different acts.** A
        browser that sent the whole opportunity back could choose what the opportunity *says* by
        editing it, and the ticket that became would be one nobody read. The words are the
        briefing's; the browser chooses among them by number.

        **An index that is not in the briefing is refused by name and nothing is filed at all.**
        Filing two of three is a person who was told they chose three, and a briefing's
        opportunities are renumbered every time it is asked for — so the usual cause is an index
        carried over from an earlier briefing, and saying that is more use than a 422.
        """
        the_briefing = _the_briefings.get(briefing_id)
        if the_briefing is None:
            raise HTTPException(
                status_code=410,
                detail=(
                    f"{briefing_id} is not a briefing this process is holding. A briefing is held "
                    "in memory like a run, so a process that has restarted has none of them — ask "
                    "for the briefing again and pick from the new one"
                ),
            )

        try:
            the_filing = filing_the_picks_a_person_made(
                the_briefing, picks.which, the_issue_opener_this_deployment_has()
            )
        except NotAnOpportunityInThisBriefingError as not_one:
            raise HTTPException(status_code=400, detail=str(not_one)) from not_one

        return {
            "briefing_id": the_filing.briefing_id,
            "how_many_were_found": the_filing.how_many_opportunities_were_found,
            "how_many_became_filings": the_filing.how_many_became_filings,
            "repository": the_filing.repository.address,
        }

    @the_app.get("/api/runs/{work_item_id}/events")
    async def what_the_run_says_live(work_item_id: str) -> StreamingResponse:
        """The run's own record, pushed as it grows.

        **Server-Sent Events, and a poll of the store rather than a subscription to the run.** The
        run is a task in this process and the store is on disk, so a second connection — a browser
        that reloaded, a second tab — sees the same history a first one did. A subscription would
        make the record depend on who was watching.
        """
        return StreamingResponse(
            _the_stream_of_what_a_run_says(a_register, work_item_id),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )

    return the_app


def _the_question_about(
    a_register: sqlite3.Connection, work_item_id: str
) -> dict[str, object] | None:
    """What the gate is asking about, as the board needs it, or `None` when it is not asking."""
    the_question = what_the_gate_was_asking_about(a_register, work_item_id)
    if the_question is None:
        return None
    return {"artifact_id": the_question[0], "artifact_version": the_question[1]}


def what_the_run_said(a_register: sqlite3.Connection, work_item_id: str) -> list[WhatARunSaid]:
    """Everything this run has said, oldest first.

    **The whole history and not the new part,** which is what makes a reloaded page show a run
    that has been working rather than one that has apparently said nothing.
    """
    return the_events_this_run_produced(a_register, work_item_id)


async def _the_stream_of_what_a_run_says(
    a_register: sqlite3.Connection, work_item_id: str
) -> AsyncIterator[str]:
    """Every line the run has said, then every line it says from now on.

    **The whole history first, so a browser that connects late is not looking at an empty board.**
    A stream that only carried what happened after the connection opened is a stream that shows a
    reloaded page a run that has apparently said nothing.
    """
    what_has_been_sent = 0

    while True:
        the_events = what_the_run_said(a_register, work_item_id)
        for an_event in the_events[what_has_been_sent:]:
            yield f"event: what_it_said\ndata: {an_event.model_dump_json()}\n\n"
        what_has_been_sent = len(the_events)

        the_question = what_the_gate_was_asking_about(a_register, work_item_id)
        if the_question is not None:
            yield (
                "event: what_it_is_asking\ndata: "
                f'{{"artifact_id": "{the_question[0]}", "artifact_version": {the_question[1]}}}\n\n'
            )

        await asyncio.sleep(HOW_OFTEN_THE_STREAM_LOOKS_IN_MILLISECONDS / 1000)

