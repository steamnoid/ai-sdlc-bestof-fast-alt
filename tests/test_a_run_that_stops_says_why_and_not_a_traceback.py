"""That a run that stops mid-walk says why in a sentence, and does not hand a person a traceback.

**The docstring promised this and the code did not do it.** `resume` and `run` both say, in their
own words, that *a terminal reader is a person and a traceback is a thing a person hands to a
developer rather than reads* — and then each caught **two** named refusals and let everything else
through. Running the real command proved the gap in one invocation: the resume printed the run's
directory and `the next thing a person rules on is DiscoveryReport`, and then printed a LangGraph
`[NOTE] During task with name 'discover_the_repository'` and a traceback.

**A promise the code does not keep is worse than no promise**, because the reader trusts it: a
person who has just lost a terminal is looking for their work, not for a stack, and a stack hands
them to whoever is nearest and teaches them nothing about whether the work is safe.

**Through the command line and not through `_walk`, because the promise is in the command.** A test
that called `_walk` directly would prove the helper prints something; a test that invokes `aisdlc`
proves the thing a person invokes behaves as documented, and the one place that can break without
anybody noticing is a command nobody ran end to end after changing what it catches.

**And the graph is replaced rather than built, because the claim is about the reporting and not
about a real run.** Building a real graph needs a model and a repository, and a test that needed
both to learn *whether a traceback reached a terminal* would be a test that only runs when the
whole system runs — which is exactly how this gap survived. **The double raises the way a node
raises, and the assertion is on the output rather than on the call.**

**The exit code is asserted too, and that is the half people forget.** A command that prints a
sentence and exits `0` tells a script the run succeeded, and every automation above this one is
reading that code rather than the words.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from aisdlc.cli import aisdlc

A_REPOSITORY = "pikuniu/a-project"
A_RUN_THAT_CANNOT_CONTINUE = "a-run-that-lost-its-terminal"
WHERE_PROJECTS_LIVE = "AISDLC_PROJECTS_DIR"


class ARunRefusedMidWalkError(Exception):
    """A refusal shaped like the ones a node raises, and carrying the sentence a person needs."""

    def __init__(self, why: str) -> None:
        super().__init__(why)
        self.why = why


@pytest.fixture
def an_empty_deployment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A register and a projects root with one commissioned work item and nothing else.

    **The work item is commissioned the way a process commissions one**, so the run exists for
    every reason except the one under test — which is what keeps the failure about the walk rather
    than about a run nobody asked for.
    """
    from aisdlc.domain.commissioned_request import a_request_about
    from aisdlc.domain.repository import Repository
    from aisdlc.domain.role import Role
    from aisdlc.domain.work_item import a_work_item_commissioned_for_an_agent
    from aisdlc.store.what_a_run_records import the_work_item_was_commissioned
    from aisdlc.store.where_the_register_lives import (
        the_register_lives_at,
        where_the_register_should_live,
    )
    from aisdlc.tools.the_project_directory import where_projects_live

    monkeypatch.setenv(WHERE_PROJECTS_LIVE, str(tmp_path / "projects"))
    the_register_lives_at(where_the_register_should_live())

    the_work_item_was_commissioned(
        a_work_item_commissioned_for_an_agent(
            work_item_id=A_RUN_THAT_CANNOT_CONTINUE,
            repository=Repository(owner="pikuniu", name="a-project"),
            accountable_role=Role.DEV,
            commissioned_by="a person in a terminal",
            requested=a_request_about("add a health endpoint", ""),
        ),
        where_projects_live(),
    )

    return tmp_path


class AGraphThatRefusesMidWalk:
    """A graph whose first node raises, which is what every real walk eventually meets."""

    def stream(self, where_from: dict[str, Any], the_config: Any) -> Any:
        raise ARunRefusedMidWalkError(
            "GitHub answered 401 when asked which commit pull request 4 points at, and a "
            "credential nobody has is not a credential."
        )


def _a_cli_whose_walk_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the command at a graph that refuses, and leave everything else real."""
    import aisdlc.cli as the_cli

    monkeypatch.setattr(the_cli, "the_graph_for", lambda *arguments: AGraphThatRefusesMidWalk())


def test_a_run_that_stops_mid_walk_says_why_in_a_sentence(
    an_empty_deployment: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No traceback, the reason in the person's own reading, and the work item named.

    A sentence that says *this failed* leaves a person to work out which of their runs it was,
    while one that names the work item tells them what to go and look at.
    """
    _a_cli_whose_walk_is_refused(monkeypatch)

    what_a_person_typed = CliRunner().invoke(
        aisdlc, ["resume", A_REPOSITORY, A_RUN_THAT_CANNOT_CONTINUE]
    )

    assert "Traceback" not in what_a_person_typed.output, (
        f"a person asking to carry on a run was handed a stack trace:\n{what_a_person_typed.output}"
    )
    assert "[NOTE]" not in what_a_person_typed.output, (
        f"a person was handed a graph runtime's own diagnostic rather than a sentence:\n"
        f"{what_a_person_typed.output}"
    )

    assert "credential nobody has is not a credential" in what_a_person_typed.output, (
        "the run stopped and the reason was left out. A refusal that does not say why is a "
        f"question a person has to answer from somewhere else:\n{what_a_person_typed.output}"
    )

    assert A_RUN_THAT_CANNOT_CONTINUE in what_a_person_typed.output, (
        f"the run stopped without saying which run it was:\n{what_a_person_typed.output}"
    )


def test_a_run_that_stops_mid_walk_exits_with_the_codes_own_number(
    an_empty_deployment: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`1` is the harness giving up; `2` is this command saying it refused.

    **And asserting `2` rather than "not zero" is what makes this a test of this code.** Before
    the fix the exception escaped, `CliRunner` caught it, and it reported `1` on its own — so an
    assertion of *not zero* was satisfied by the harness and could never fail. **A test the harness
    can satisfy on its own is not a test of the code underneath it**, and this one was exactly
    that until the number was written down.

    **`2` is the number `run` and `resume` already use for a refusal**, so this asserts that the
    walk ends the same way the things before it do rather than inventing an exit of its own.
    """
    _a_cli_whose_walk_is_refused(monkeypatch)

    what_a_person_typed = CliRunner().invoke(
        aisdlc, ["resume", A_REPOSITORY, A_RUN_THAT_CANNOT_CONTINUE]
    )

    assert what_a_person_typed.exit_code == 2, (
        f"the run was refused mid-walk and the command exited {what_a_person_typed.exit_code}. "
        "`1` here is the test harness reporting an exception it caught, not a decision this "
        "command made — and every script above this one reads the code rather than the words"
    )
