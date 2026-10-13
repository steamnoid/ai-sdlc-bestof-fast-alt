"""Two commands, and one of them is the product.

`serve` puts the board in a browser. `run` puts a person in front of the gates in a terminal.

**Both go through the same composition root,** so a run started from a terminal and a run
started from a browser are the same run, with the same register, the same project directory and
the same eight gates. A CLI that reached past the composition root into the graph is how the
business logic would end up written twice, and the second copy would be the one nobody looks at.

**`run` prints the file to open rather than rendering the artifact.** A discovery report is
several hundred words of JSON and a plan is a list of paths; a terminal that tried to draw them
would produce a worse version of the file the run has already written, and the person deciding
is better served by the file they can read in an editor.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

import typer

from aisdlc.application.a_run_being_assembled import (
    ThisRunCannotBeAssembledError,
    a_run_beginning_at,
    the_graph_for,
)
from aisdlc.application.the_runs_this_process_is_holding import TheRunsThisProcessIsHolding
from aisdlc.approval.approval_decision import ApprovalDecision
from aisdlc.domain.commissioned_request import a_request_about
from aisdlc.domain.repository import Repository
from aisdlc.domain.work_item import a_work_item_commissioned_for_an_agent
from aisdlc.graph.agent_state import AgentState
from aisdlc.graph.lifecycle import a_config
from aisdlc.persistence.the_register_of_work_items import NoSuchWorkItemError
from aisdlc.store.the_record_of_a_run import what_the_gate_was_asking_about
from aisdlc.store.what_a_run_records import something_the_run_said, the_work_item_was_commissioned
from aisdlc.store.where_the_register_lives import holding_the_register, the_register_lives_at
from aisdlc.tools.a_resumed_run_of import a_resumed_run_of
from aisdlc.tools.the_project_directory import the_project_directory_of, where_projects_live

aisdlc = typer.Typer(no_args_is_help=True, help="An AI-native SDLC that shows its working.")

THE_PORT_THIS_SERVES_ON_BY_DEFAULT = 842
HOW_OFTEN_A_TERMINAL_LOOKS_IN_SECONDS = 1.0


def _open_the_register() -> None:
    """Open the register where this deployment keeps it, before anything asks for it."""
    from aisdlc.store.where_the_register_lives import where_the_register_should_live

    the_register_lives_at(where_the_register_should_live())


@aisdlc.command()
def serve(port: int = THE_PORT_THIS_SERVES_ON_BY_DEFAULT) -> None:
    """The board, in a browser, at http://127.0.0.1:<port>.

    **Bound to the loopback and not to every interface, and that is the whole of the
    authentication story.** There is none: anybody who can reach this address can start a run on
    a real repository and answer every gate on it. The address is the boundary, and a deployment
    that needs it exposed has to say so and put its own authentication in front of it.
    """
    import uvicorn

    from aisdlc.web.the_api import the_api_over

    _open_the_register()
    where = _the_register_file()

    typer.echo(f"the board is on http://127.0.0.1:{port}")
    typer.echo(f"the register is {where}")
    typer.echo("type a repository and a sentence on the board to start a run")

    uvicorn.run(
        the_api_over(the_register(), TheRunsThisProcessIsHolding()),
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )


@aisdlc.command()
def run(
    repository: str = typer.Argument(..., help="owner/name, the way GitHub writes it."),
    asked_for: str = typer.Argument(..., help="One sentence saying what should change."),
    any_more_detail: str = typer.Option(
        "", "--detail", help="Anything the sentence could not hold."
    ),
) -> None:
    """Run one work item in this terminal, and ask you at each of the eight gates.

    **The gates are asked here, one at a time, and nothing is approved on your behalf.** A
    deployment that wants a policy answering instead sets `AISDLC_APPROVAL_POLICY`, and then this
    command walks the whole pipeline without stopping — which is the engine's own mode and is
    recorded in the register as `autopilot:<name>`, never as you.
    """
    _open_the_register()
    the_repository = _a_repository_from(repository)
    the_work_item_id = _a_work_item_id_for(the_repository, asked_for)
    the_projects_root = where_projects_live()

    the_work_item = the_work_item_was_commissioned(
        a_work_item_commissioned_for_an_agent(
            work_item_id=the_work_item_id,
            repository=the_repository,
            accountable_role=_the_discipline_asked_for(),
            commissioned_by="a person in a terminal",
            requested=a_request_about(asked_for, any_more_detail),
        ),
        the_projects_root,
    )
    something_the_run_said(the_work_item_id, "a person asked for this")

    try:
        the_graph = the_graph_for(the_repository)
    except ThisRunCannotBeAssembledError as cannot:
        # **The sentence and not the exception.** A terminal reader is a person, and a traceback
        # is a thing a person hands to a developer rather than reads. The refusal already names
        # what is missing and which four values would fix it, so showing the class name in front
        # of it adds nothing and costs the one thing the refusal was for.
        typer.echo(f"this run cannot start: {cannot}")
        raise typer.Exit(code=2) from None

    the_config = a_config(the_work_item_id)
    the_project_directory = the_project_directory_of(the_work_item, the_projects_root)

    typer.echo(f"{the_work_item_id} · {the_repository.address}")
    typer.echo(f"everything this run writes goes in {the_project_directory}")
    typer.echo("")

    _walk(
        the_graph,
        the_config,
        the_work_item_id,
        the_work_item,
        the_project_directory,
        a_run_beginning_at(the_work_item, the_projects_root),
    )


@aisdlc.command(name="start")
def start_a_filing(
    work_item_id: str = typer.Argument(
        ..., help="The filed work item to walk, as the board names it."
    ),
) -> None:
    """Walk a work item a briefing filed, without rewording its request.

    **The terminal half of `POST /api/runs/from-work-item`.** The filing commissioned
    the work item with the opportunity's own words; this looks it up at `READY` and
    walks the same eight gates a sentence-led run walks. A run started twice, or from
    past `READY`, is refused with the register's own sentence.
    """
    from aisdlc.domain.stage import Stage
    from aisdlc.store.the_register_of_work_items import (
        NoSuchWorkItemError as NoSuchRegisteredWorkItemError,
    )
    from aisdlc.store.the_register_of_work_items import the_work_item_registered_at
    from aisdlc.store.where_the_register_lives import holding_the_register

    _open_the_register()
    the_projects_root = where_projects_live()

    with holding_the_register() as the_register:
        try:
            the_work_item = the_work_item_registered_at(the_register, work_item_id)
        except NoSuchRegisteredWorkItemError as nothing_to_start:
            typer.echo(f"{work_item_id} cannot be started: {nothing_to_start}")
            raise typer.Exit(code=2) from None
        if the_work_item.stage is not Stage.READY:
            typer.echo(
                f"{work_item_id} is at {the_work_item.stage.name}, and only a work item "
                "at READY can be started — this one has already been picked up or delivered"
            )
            raise typer.Exit(code=2)

    try:
        the_graph = the_graph_for(the_work_item.repository)
    except ThisRunCannotBeAssembledError as cannot:
        typer.echo(f"this run cannot start: {cannot}")
        raise typer.Exit(code=2) from None

    the_project_directory = the_project_directory_of(the_work_item, the_projects_root)

    typer.echo(f"{work_item_id} · {the_work_item.repository.address}")
    typer.echo(f"everything this run writes goes in {the_project_directory}")
    typer.echo("")

    _walk(
        the_graph,
        a_config(work_item_id),
        work_item_id,
        the_work_item,
        the_project_directory,
        a_run_beginning_at(the_work_item, the_projects_root),
    )


@aisdlc.command()
def resume(
    repository: str = typer.Argument(..., help="owner/name, the way GitHub writes it."),
    work_item_id: str = typer.Argument(..., help="The run to carry on, as the register names it."),
) -> None:
    """Carry on a run whose terminal closed, from what it left on disk.

    **The checkpointer is in memory, so this is the only way back into a lost run.** Everything a
    run has done is written to the register and to the artifacts beside its clone; nothing else of
    it survives the process. `a_resumed_run_of` reads both and rebuilds the state, and this command
    is the door — without it the reconstruction is correct code nobody can reach.

    **The room is filled at commission time, not at the first transition.** Commissioning writes
    both registers — the SQLite copy a board reads and the per-run `WorkItem.json` this reads —
    so even a filing that never walked is found here, and resumes at the beginning presenting
    `DiscoveryReport`. What the resume rebuilds depends on how far the run got: nothing produced
    yet means the beginning state, four artifacts means four carried channels, and nothing is
    invented to fill one.

    **The refusal is a sentence, for the reason `run` already says it out loud.** A terminal
    reader is a person and a traceback is a thing a person hands to a developer rather than reads.
    A person who has just lost a terminal is looking for their work, not for a stack.
    """
    _open_the_register()
    the_repository = _a_repository_from(repository)
    the_projects_root = where_projects_live()

    try:
        where_from = a_resumed_run_of(the_repository, work_item_id, the_projects_root)
    except NoSuchWorkItemError as nothing_to_carry_on_from:
        typer.echo(f"{work_item_id} cannot be carried on from: {nothing_to_carry_on_from}")
        raise typer.Exit(code=2) from None

    try:
        the_graph = the_graph_for(the_repository)
    except ThisRunCannotBeAssembledError as cannot:
        typer.echo(f"this run cannot continue: {cannot}")
        raise typer.Exit(code=2) from None

    the_project_directory = the_project_directory_of(where_from["work_item"], the_projects_root)

    typer.echo(f"{work_item_id} · {the_repository.address}")
    typer.echo(f"carrying on from {the_project_directory}")
    typer.echo(f"the next thing a person rules on is {where_from['presented_artifact_id']}")
    typer.echo("")

    _walk(
        the_graph,
        a_config(work_item_id),
        work_item_id,
        where_from["work_item"],
        the_project_directory,
        where_from,
    )


def _walk(
    the_graph,
    the_config,
    work_item_id: str,
    the_work_item,
    the_project_directory,
    where_from: AgentState,
) -> None:
    """Walk one run to its first gate, and then to the next one for as long as there is one.

    **The walk and the gate in one function, because they are one thing in a loop.** A terminal
    is a different kind of gate than a browser: the person is already here, so there is nothing
    to suspend and nothing to resume — a refusal simply ends the walk.

    **The starting state arrives as an argument and is not built here.** A run that is being
    continued and a run being started from nothing differ in exactly one thing, and a walk that
    built its own state could only ever do the second — which is how two hundred lines of correct
    reconstruction code sat in `tools/` with nothing able to reach it.

    **And anything a node raises ends the walk as a sentence, because this is a terminal.** The
    two commands that lead here each catch two named refusals, and the rest used to arrive as a
    LangGraph `[NOTE]` and a stack — which is precisely what their own docstrings say a terminal
    reader should not be handed. **A blanket catch is right here and wrong everywhere else**: in the
    graph a narrow clause is what keeps a run from arriving somewhere it cannot be acted on, while
    here there is nowhere further to route and one reader who is not a developer. The work item is
    named, because *this failed* leaves a person to work out which of their runs it was.
    """
    try:
        _the_updates_the_walk_goes_by(
            the_graph, where_from, the_config, work_item_id, the_work_item, the_project_directory
        )
    except Exception as it_stopped:
        typer.echo(f"{work_item_id} stops here: {it_stopped}")
        raise typer.Exit(code=2) from None


def _the_updates_the_walk_goes_by(
    the_graph,
    where_from: AgentState,
    the_config,
    work_item_id: str,
    the_work_item,
    the_project_directory,
) -> None:
    """The updates, so that the catching above wraps the walk and nothing else."""
    for update in the_graph.stream(where_from, the_config):
        for a_node in update:
            typer.echo(f"  {a_node}")

    while True:
        with holding_the_register() as the_register:
            the_question = what_the_gate_was_asking_about(the_register, work_item_id)
        if the_question is None:
            typer.echo("")
            typer.echo("the run is not waiting for anybody.")
            return

        the_answer = _ask_a_person(
            the_question, work_item_id, the_project_directory, the_work_item.stage.name
        )
        if the_answer is None:
            typer.echo("")
            typer.echo("stopped, with nothing decided. The run is still on the board.")
            return

        from langgraph.types import Command

        for update in the_graph.stream(Command(resume=the_answer), the_config):
            for a_node in update:
                typer.echo(f"  {a_node}")


def _ask_a_person(
    the_question: tuple[str, int], work_item_id: str, the_project_directory, stage: str
) -> ApprovalDecision | None:
    """Ask one gate in a terminal, and hand back what the person said — or `None` for "stop".

    **A refusal is an answer and "stop" is not**, and the two are different exits from this
    function on purpose. A refusal is a completed gate: the run stops, the decision is recorded,
    and a person can see why on the card. Quitting is not a decision about anything, so nothing
    is recorded and the run stays exactly where it was.
    """
    artifact_id, artifact_version = the_question
    typer.echo("")
    typer.echo(f"— {stage} · {artifact_id} v{artifact_version} —")
    typer.echo(f"  it is in {the_project_directory / (artifact_id + '.json')}")

    approved = typer.confirm("  approve it?", default=False)
    who = typer.prompt("  your name")
    why = typer.prompt("  why")
    if not who.strip() or not why.strip():
        typer.echo("  a decision names who decided and says why. Both are required.")
        return None

    return ApprovalDecision(
        work_item_id=work_item_id,
        artifact_id=artifact_id,
        artifact_version=artifact_version,
        approved=approved,
        decided_by=who.strip(),
        decided_at=datetime.now(UTC),
        reason=why.strip(),
    )


def _a_repository_from(written: str) -> Repository:
    """`owner/name` into a repository, or a sentence saying which half is missing.

    **Split once, here.** Every repository in this system is two halves, and a string with the
    wrong number of them is a request about a repository that cannot exist.
    """
    owner, _, name = written.strip().partition("/")
    if not owner or not name or "/" in name:
        typer.echo(
            f"{written!r} is not a repository. It is written owner/name, "
            "as https://github.com/owner/name is."
        )
        raise typer.Exit(code=2)
    return Repository(owner=owner, name=name)


def _a_work_item_id_for(repository: Repository, asked_for: str) -> str:
    """A name nobody has used, because a work item's id is a branch, a directory and a thread."""
    the_moment = datetime.now(UTC)
    the_words = "".join(
        a_character if a_character.isalnum() else "-" for a_character in asked_for.lower()
    )
    the_slug = "-".join(a_part for a_part in the_words.split("-") if a_part)[:48].strip("-")
    return f"{repository.name}-{the_slug}-{the_moment:%Y%m%d-%H%M%S}"


def _the_discipline_asked_for():
    """The developer, because a request from a person is work on a product.

    **One answer rather than a question, and this is the one place a default is right.** A
    work item's role is which discipline answers for the result, and a person asking a tool to
    change a repository is asking for a change to it. The four analysis stages each move the role
    to their own discipline as the run reaches them, so this is the role of the *first* piece of
    work and nothing after it.
    """
    from aisdlc.domain.role import Role

    return Role.DEV


def the_register():
    """The open register, for the one caller that hands a connection to the API."""
    from aisdlc.store.where_the_register_lives import the_register as _the_register

    return _the_register()


def _the_register_file():
    from aisdlc.store.where_the_register_lives import where_the_register_should_live

    return where_the_register_should_live()


if __name__ == "__main__":
    sys.exit(aisdlc())
