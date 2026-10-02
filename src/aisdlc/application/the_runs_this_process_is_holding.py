"""The runs this process is holding, and the one door a decision comes through.

**A run lives in a thread, and the thread's name is the work item's id.** LangGraph suspends a
run by raising out of the node that asked, so a run standing at a gate is a graph with a
checkpoint and no thread running — it is parked, and nothing about it is alive until somebody
resumes it. This module is what holds the compiled graph between those two moments, because the
checkpointer is inside the compiled graph and a graph rebuilt for the resume would be a graph
with no memory of being asked.

**Starting and answering are the same shape, and that is the whole bridge.** A run starts by
walking the graph until it parks; an answer resumes it and walks until it parks again. One
function walks a graph, and the two callers differ only in what they hand it. A version with
two walkers is a version where one of them grows a second stopping rule.

**Every answer enters here, whoever wrote it.** A person's POST from a browser and a policy
that answers its own gate both end up in the same tables, and the gate's own rules run before
either of them is recorded. There is no path from a decision to the record that does not go
through `record_the_decision`, which is what makes "a policy gets no shortcut past the version
check" a property of the wiring rather than a claim about it.

**A crash is written onto the card and not printed.** A run that dies four minutes in has
produced a traceback nobody is watching a terminal for, and a card that stops advancing with no
explanation is indistinguishable from a run that is still thinking. So the exception's own words
go into the run's story, next to the last thing it did, and the board shows it.
"""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from pathlib import Path

from langgraph.types import Command

from aisdlc.application.a_run_being_assembled import a_run_beginning_at, the_graph_for
from aisdlc.approval.approval_decision import ApprovalDecision
from aisdlc.domain.repository import Repository
from aisdlc.domain.work_item import WorkItem
from aisdlc.graph.lifecycle import a_config
from aisdlc.store.what_a_run_records import (
    something_the_run_said,
    the_work_item_was_commissioned,
)

# How a run's graph is built from a repository and, optionally, a model. **A callable and not a
# `Protocol` class**, because there is exactly one production implementation and a class would be
# a file of ceremony around a type annotation. The model is `object` because the production
# builder's model is a LangChain class and a test's is `None`; neither this registry nor the walk
# ever looks at it — it is handed straight to the builder and forgotten.
BuildTheGraph = Callable[[Repository, object], object]


class NoSuchRunIsBeingHeldError(Exception):
    """Something asked this process to act on a run it is not holding.

    **Raised rather than ignored.** A decision posted to a work item id this process has never
    heard of is one of three things: a run from a process that has since died, a typo, or a
    request aimed at somebody else's board. All three are worth saying out loud, and the first
    is the one that matters — an in-memory checkpointer means a restart loses every parked run,
    and a run silently forgotten at a gate looks exactly like a run nobody answered.
    """

    def __init__(self, work_item_id: str) -> None:
        """Name the id, and say what holding it means."""
        super().__init__(
            f"{work_item_id!r} is not a run this process is holding. A run is held in memory "
            "while it stands at a gate, so a process that has restarted is holding none of "
            "them: a decision posted to a run this process does not hold has nobody to wake up. "
            "The work item and everything it wrote are on disk — commissioning it again picks "
            "up where it got to"
        )


class TheRunsThisProcessIsHolding:
    """Every run this process has started, and whether each one is still walking.

    **The composition root is a constructor argument, and the default is the real one.** This
    class is a registry: it holds compiled graphs, walks them and resumes them, and none of that
    requires knowing which model reasoned. A run that builds its own graph here would make this
    the one place in the repository that names a model, which is the mistake the composition root
    was written to fix — and it would make a run untestable without a credential, because the
    refusal "this deployment has no model configured" would arrive before anything could be
    proven about the pipeline that does not need one.

    **A lock, because two people clicking two gates at once is the ordinary case** rather than
    an edge case — a board polls every two seconds and every button on it is live. The lock is
    held for the length of a start or an answer and never for the length of a walk, because a
    walk is minutes long and holding it would make the board unreadable.
    """

    def __init__(self, build_the_graph: BuildTheGraph | None = None) -> None:
        """Nothing is held until a run is started, and that is the honest initial state.

        **The production builder when none is given, wrapped rather than named directly.** The
        real one is typed `(Repository, BaseChatModel | None) -> CompiledStateGraph` and this
        parameter is typed more loosely, because a test's builder is a plain function over a
        repository and nothing. Naming the real signature as the default would make every test
        declare a model it does not have, and loosening the real one would lose the type that
        says what a run is built from.
        """
        self._build_the_graph = build_the_graph or _the_production_graph
        self._the_graphs: dict[str, object] = {}
        self._the_work_items: dict[str, WorkItem] = {}
        self._walking_right_now: set[str] = set()
        self._how_a_run_finished: dict[str, str] = {}
        self._lock = threading.Lock()

    def a_run_was_started(
        self, work_item: WorkItem, projects_root: Path, the_model: object = None
    ) -> None:
        """Commission this work item and start walking it, in a thread of its own.

        **The walk is in a thread because it takes minutes and the caller is a request.** A
        person typing a repository into a browser must not hold that connection open for the
        twenty minutes a run spends reasoning, and must not be told the run failed because the
        browser gave up waiting.

        **The graph is built once and kept**, because the checkpointer is inside it. A resume
        that rebuilt the graph would be talking to a graph that had never been asked anything.
        """
        with self._lock:
            if work_item.work_item_id in self._the_graphs:
                raise AWorkItemIsAlreadyBeingHeldError(work_item.work_item_id)
            the_graph = self._build_the_graph(work_item.repository, the_model)
            self._the_graphs[work_item.work_item_id] = the_graph
            self._the_work_items[work_item.work_item_id] = work_item
            self._walking_right_now.add(work_item.work_item_id)

        something_the_run_said(work_item.work_item_id, "picked up the request")

        self._in_a_thread_of_its_own(
            work_item.work_item_id,
            the_graph,
            lambda a_graph: self._walk(
                work_item.work_item_id, a_graph, a_run_beginning_at(work_item, projects_root)
            ),
        )

    def a_gate_was_answered(self, decision: ApprovalDecision) -> None:
        """Hand this decision to the run it is about and walk it on to the next gate.

        **Refused when the run is not parked**, which is a person clicking approve twice, a
        board replaying an answer it already sent, or a run that has already moved on. Each of
        those is a decision about a version of an artifact that is no longer the one in front of
        the person, and the gate's own check would catch it — but catching it here means the
        second click does not look like a working system that ignored them.
        """
        with self._lock:
            if decision.work_item_id not in self._the_graphs:
                raise NoSuchRunIsBeingHeldError(decision.work_item_id)
            if decision.work_item_id in self._walking_right_now:
                raise AWorkItemIsStillWorkingError(decision.work_item_id)
            the_graph = self._the_graphs[decision.work_item_id]
            self._walking_right_now.add(decision.work_item_id)

        self._in_a_thread_of_its_own(
            decision.work_item_id,
            the_graph,
            lambda a_graph: self._walk(
                decision.work_item_id, a_graph, Command(resume=decision)
            ),
        )

    def _walk(self, work_item_id: str, the_graph: object, where_from: object) -> None:
        """Walk a graph until it parks or ends, and say how it went on the card either way.

        **`stream` and not `invoke`,** because `invoke` returns one value at the end and a run
        that takes twenty minutes gives a person nothing to look at for all of it. `stream`
        hands back each node as it finishes, which is what makes a board that says what it is
        doing possible at all.
        """
        try:
            for what_happened in the_graph.stream(  # type: ignore[attr-defined]
                where_from, a_config(work_item_id)
            ):
                for a_node in what_happened:
                    something_the_run_said(work_item_id, f"ran {a_node}")
        except Exception as a_problem:
            _how_a_run_failed(work_item_id, a_problem, self)
        finally:
            with self._lock:
                self._walking_right_now.discard(work_item_id)

    def _in_a_thread_of_its_own(self, work_item_id: str, the_graph: object, the_walk) -> None:
        """A daemon thread, so this process can exit with a run still parked at a gate.

        **Daemon and not joined.** A parked run holds no resources a shutdown needs to reclaim —
        its work is on disk and its checkpoint is in memory this process is about to drop — and
        a process that waited for twenty-minute runs to finish would make `Ctrl-C` a lie.
        """
        the_thread = threading.Thread(
            target=the_walk, args=(the_graph,), daemon=True, name=work_item_id
        )
        the_thread.start()

    def is_this_run_still_walking(self, work_item_id: str) -> bool:
        """Whether this run is mid-stage right now, as opposed to parked or finished."""
        with self._lock:
            return work_item_id in self._walking_right_now

    def this_run_is_held_here(self, work_item_id: str) -> bool:
        """Whether this process has ever started this run, parked or not."""
        with self._lock:
            return work_item_id in self._the_graphs

    def how_this_run_ended(self, work_item_id: str) -> str | None:
        """The sentence this run ended with, or `None` while it is still going or parked."""
        with self._lock:
            return self._how_a_run_finished.get(work_item_id)


def _the_production_graph(source: Repository, the_model: object = None) -> object:
    """The composition root, at the width this registry holds it.

    **A named function and not `the_graph_for` passed as a default,** because the real builder
    takes a `BaseChatModel` and this registry deliberately does not know what a model is — it
    walks graphs and resumes them. One function, typed at the width the registry uses, is the
    place that disagreement is absorbed rather than asserted away.
    """
    return the_graph_for(source, the_model)  # type: ignore[arg-type]


class AWorkItemIsAlreadyBeingHeldError(Exception):
    """Two runs were asked for the same work item id in one process.

    **The id is a run's branch, its directory and its thread.** A second run with the same id
    would push a branch the first one created, into a directory holding the first one's
    artifacts, on a checkpoint the first one is parked at — and the engine's own delivery
    refused exactly this once, correctly, eight gates into a real run.
    """


class AWorkItemIsStillWorkingError(Exception):
    """A decision arrived for a run that is mid-stage rather than parked at a gate.

    **Which is what clicking approve twice looks like.** The run is not waiting for anybody;
    it is in the middle of reading a repository, and the answer is about an artifact version the
    run has not presented yet. Recording it would be a decision about something nobody was
    shown.
    """


def _how_a_run_failed(work_item_id: str, a_problem: Exception, the_runs) -> None:
    """Put the failure on the card, in the run's own words, and remember it for the board.

    **The exception's own message and the node it happened in.** "Error: 500" on a card tells a
    person to file a bug; `a suite that went red after the change` tells them what the run
    actually hit, which is one of the three things this system's refusals are named for.
    """
    where_it_happened = _the_node_a_problem_happened_in(a_problem)
    the_words = f"{where_it_happened}: {a_problem}" if where_it_happened else str(a_problem)
    something_the_run_said(work_item_id, f"stopped with a problem — {the_words}")
    with the_runs._lock:
        the_runs._how_a_run_finished[work_item_id] = the_words


def _the_node_a_problem_happened_in(a_problem: Exception) -> str | None:
    """The last graph node that ran, read out of the traceback.

    **Read rather than passed**, because the only place that knows which node is running is the
    stack. A card saying a run failed without saying where is a card a person has to go and
    reproduce to act on.
    """
    the_frames = traceback.extract_tb(a_problem.__traceback__)
    for a_frame in reversed(the_frames):
        if a_frame.name.startswith(("analyze_", "discover_", "plan_", "implement_", "apply_")):
            return a_frame.name
    return None


def a_work_item_for(
    repository: Repository, work_item_id: str, requested: object, projects_root: Path
) -> WorkItem:
    """A commissioned work item, registered, so the board has a card before the run starts.

    **Registered before the first node runs, and not after.** A run's first act is to clone a
    repository, which is minutes; a card that appeared when the run reached its first gate would
    leave a person who typed a repository and got nothing back with no way to tell a slow run
    from a request that was dropped.
    """
    from aisdlc.domain.role import Role
    from aisdlc.domain.work_item import a_work_item_commissioned_for_an_agent

    the_work_item = a_work_item_commissioned_for_an_agent(
        work_item_id=work_item_id,
        repository=repository,
        accountable_role=Role.DEV,
        commissioned_by="a person in a browser",
        requested=requested,  # type: ignore[arg-type]
    )
    return the_work_item_was_commissioned(the_work_item, projects_root)
