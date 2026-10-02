"""Two defects a real run found, and the tests that hold them there.

Both of these were invisible to a test suite that only ever ran from pytest's own `tmp_path`,
and both were found by pointing the product at a real repository from a real shell. That is the
argument for this file existing at all: it is short, and every case in it is a place where the
machine's own behaviour, rather than the code's logic, is what a test would have to be told
about.

**A symlinked projects root, because `/tmp` is one on macOS and a real deployment will use one
on Linux too.** `plan_the_change` asked the confinement check where a test's directory was, got
back a path that had been resolved, and compared it against a root that had not. On any machine
where the two spellings differ — which is every machine where the root is a link — the
comparison raised Python's own `ValueError` about a subpath, out of a stage, twenty minutes into
a run. The failure was loud and named, which is the only reason it was cheap to find; it was
still a bug, and it is the kind a unit test cannot reach.

**A security analyst shown no source code, because one inspection was doing two jobs.** The
inspection was built for discovery, whose job is a repository's *shape*, and the security analyst
was later wired to the same one. It was therefore asked to find authentication and authorization
problems while being handed a directory listing and a `package.json` — and it reasoned from
filenames, which a real run's gate refused for exactly that.
"""

from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path

import pytest

from aisdlc.agents.implementation_plan import ImplementationPlan
from aisdlc.agents.plan_the_change import _every_test_is_where_the_suite_will_look_for_it
from aisdlc.domain.repository import Repository
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import (
    an_inspection_of,
    an_inspection_of_the_code,
)
from aisdlc.tools.the_project_directory import where_projects_live

# The repository the fixture near the end of this file clones. Named here rather than built in
# each test, because the three tests that use it are about the same thing and a repository each
# invented would be one each could be wrong about.
_A_REPOSITORY = Repository(owner="an", name="owner")


@pytest.fixture
def a_symlinked_projects_root(tmp_path: Path) -> tuple[Path, Path]:
    """One directory reached two ways — once directly, once through a link — and a clone in each.

    **A real symlink, not a mocked one.** The whole defect is that `resolve()` and not
    `resolve()` produce two different strings for the same directory, and the only honest way to
    have that happen is to have a link. A test that faked the path would have tested the fake.
    """
    the_real_one = tmp_path / "the-real-projects"
    the_real_one.mkdir()
    a_link_to_it = tmp_path / "a-link-to-them"
    a_link_to_it.symlink_to(the_real_one)

    # **The same directory twice, which is what a link is.** `exist_ok` is what makes that
    # true rather than accidental: the second root resolves to the first, so the clone is built
    # once and both tests then reach it by two names.
    a_clone = the_real_one / "an" / "owner" / "a-repository" / "repository"
    (a_clone / "tests" / "unit").mkdir(parents=True, exist_ok=True)
    (a_clone / "tests" / "unit" / "test_the_existing_thing.test.ts").write_text("// one")

    return the_real_one, a_link_to_it


def _a_clone_at(a_projects_root: Path) -> ClonedRepository:
    """A clone in the place a run puts one, reached through whichever root was given."""
    return ClonedRepository(
        path=a_projects_root / "an" / "owner" / "a-repository" / "repository",
        ref="main",
        commit="d009c2cf0c233ebe9aa5ba2dccd3823c6f004ec4",
    )


def _where_the_planner_believes_a_test_belongs(a_projects_root: Path) -> str:
    """What the planner says about a test in a directory that already holds one.

    **The runner is announced as something this system cannot parse**, which is a real run's
    ordinary case and which makes the planner fall through to asking the repository. That is the
    branch the bug was on: a path is compared against a root before the repository is asked
    anything, so the comparison has to survive a symlink for the question to be reached at all.
    """
    a_plan = ImplementationPlan(tests_to_add=["tests/unit/test_a_new_thing.test.ts"])
    _every_test_is_where_the_suite_will_look_for_it(
        _a_clone_at(a_projects_root), a_plan, "the runner announced nothing this system can read"
    )
    return "accepted"


def test_a_symlinked_projects_root_is_answered_exactly_as_a_real_one(
    a_symlinked_projects_root: tuple[Path, Path],
) -> None:
    """The same plan, the same repository, and the same answer whether the root is a link.

    **The two answers are compared to each other, not to a list.** "A symlink does not raise
    Python's `ValueError`" is a weaker claim than "a symlink and a real path are
    indistinguishable", and only the second one would notice a fix that made the linked case
    pass by refusing everything.
    """
    the_real_one, a_link_to_it = a_symlinked_projects_root

    what_a_real_root_says: object
    what_a_linked_root_says: object

    for a_root, into in ((the_real_one, "real"), (a_link_to_it, "linked")):
        try:
            what_the_planner_said = _where_the_planner_believes_a_test_belongs(a_root)
        except Exception as a_problem:
            what_the_planner_said = f"{type(a_problem).__name__}: {a_problem}"
        if into == "real":
            what_a_real_root_says = what_the_planner_said
        else:
            what_a_linked_root_says = what_the_planner_said

    assert what_a_linked_root_says == what_a_real_root_says, (
        "a projects root reached through a symlink is the same directory and must be answered "
        "the same way. It is not: the confinement check resolves the path it is given and the "
        "comparison used the root unresolved, so on any machine where the two spellings differ "
        "the stage raised Python's own ValueError about a subpath — which is what a real run on "
        "macOS did, where /tmp is a link to /private/tmp. No unit test could find it, because "
        "every one of this repository's tests ran from an already-resolved tmp_path."
    )

    assert "is not in the subpath of" not in str(what_a_linked_root_says), (
        "the linked root produced a raw ValueError out of a stage rather than one of this "
        "system's named refusals. A refusal is a decision somebody can act on; a ValueError "
        "about a subpath is a bug wearing a decision's clothes."
    )


def test_the_security_analyst_is_shown_the_code_and_not_only_the_manifests(
    a_symlinked_projects_root: tuple[Path, Path],
) -> None:
    """The inspection a security analyst gets contains code the one a discovery gets does not.

    **Two inspections and one of them is bigger, which is the whole claim.** A discovery report
    is a summary of a repository's shape and this module's own note that source files are not in
    that inspection is right. A security analyst is asked about authentication and authorization
    and a manifest answers neither — so the two need different things and sharing one selection
    is what made a real run's gate refuse a whole report for reasoning from filenames.
    """
    the_real_one, _ = a_symlinked_projects_root
    the_clone = _a_clone_at(the_real_one)

    # A file whose name says it may hold something risky, which is the only signal there is
    # without reading every file in the repository.
    (the_clone.path / "web-app" / "src" / "lib").mkdir(parents=True)
    (the_clone.path / "web-app" / "src" / "lib" / "auth.js").write_text(
        "const secret = process.env.JWT_SECRET || 'dev-secret-change-me';\n"
        "export const SESSION_DAYS = 7;\n",
        encoding="utf-8",
    )

    what_discovery_sees = an_inspection_of(the_clone)
    what_security_sees = an_inspection_of_the_code(the_clone)

    assert "JWT_SECRET" in what_security_sees, (
        "the security analyst's inspection did not contain the auth file it was selected for. A "
        "model asked to find authentication problems while handed a directory listing and a "
        "package.json will reason from filenames, and a real run's gate refused a report for "
        "exactly that."
    )
    assert "JWT_SECRET" not in what_discovery_sees, (
        "discovery's inspection is a repository's shape and this module says on purpose that "
        "source files are not in it — a summary of a project is not a copy of it. If this fails, "
        "the two inspections have been merged and the security analyst's evidence is now paid "
        "for by every discovery call."
    )


def test_the_security_inspection_says_what_it_did_not_show(
    a_symlinked_projects_root: tuple[Path, Path],
) -> None:
    """The inspection ends by naming its own limits, in a section a reader can find.

    **This is the half that matters more than the code it carries.** A model shown files it was
    not shown cannot tell that it was not shown them, and neither can a reader — which is how a
    report about a repository that was never read reaches a gate looking like a report about one
    that was. With the section present, the same model on the same repository reported the limit
    of its own evidence ("this is a gap in what I was shown, not a defect I observed") instead
    of filing speculation as a finding.
    """
    the_real_one, _ = a_symlinked_projects_root
    what_security_sees = an_inspection_of_the_code(_a_clone_at(the_real_one))

    assert "# What you were not shown" in what_security_sees, (
        "the inspection has to end by naming what it left out. Without it a report reasoning "
        "about a file nobody was shown is indistinguishable from one reasoning about a file "
        "somebody was, and that is the finding the real run's gate had to make by reading the "
        "report line by line."
    )
    # And it has to be a claim about the inspection, not a heading with nothing under it.
    what_follows_the_heading = what_security_sees.split("# What you were not shown")[1]
    assert what_follows_the_heading.strip(), (
        "the section is empty, which says less than saying nothing at all — a reader has to be "
        "able to tell 'nothing was withheld' from 'this was not written'"
    )


def test_the_analyst_is_told_about_the_files_it_was_not_shown() -> None:
    """The prompt names the section, so the instruction is not only in the data.

    **A rule in an assertion rather than in prose that asks for it.** The prompt already forbade
    inventing paths, and a real run spent eight attempts on a test directory that did not exist
    because the prompt forbade it — the reason this repository treats a rule a prompt has to
    forbid as a rule a test has to assert. This is that test, and the wording in the prompt is
    left in place because it is the same rule said twice in two registers, one of which a reader
    of the report can check.
    """
    from aisdlc.agents.inspect_for_security_risk import the_prompt_to_inspect_for_security_risk

    the_prompt = the_prompt_to_inspect_for_security_risk(
        "# What you were not shown\n\nnothing",
        _a_repository_for_the_prompt(),
    )

    assert "NOT shown" in the_prompt or "not shown" in the_prompt, (
        "the analyst is not told that its evidence has limits. It is handed an inspection whose "
        "last section says so and a prompt that does not mention it, and a model weighs the two."
    )


def _a_repository_for_the_prompt() -> Repository:
    return Repository(owner="an", name="owner")


def test_the_projects_root_setting_is_the_only_reader_of_its_own_variable() -> None:
    """`AISDLC_PROJECTS_DIR` is read in one place, and a deployment change is one edit.

    **Parsed and not grepped, because a grep finds the word.** This file's own prose quotes the
    setting's name, a comment explaining a symlink quotes the path a deployment would set, and a
    substring search reports both as readers — which is how the first version of this test failed
    on a comment three lines above it. What it is after is a subscript of `os.environ` or a call
    to `os.getenv`, which is what "reading a variable" means.

    A second reader would be a second answer to "where do runs go", and the two would agree until
    a deployment pointed them at different directories — at which point a run's clone is in one
    place and its register in another, and neither is wrong.
    """
    the_readers: list[str] = []
    for a_module in Path(__file__).resolve().parents[1].joinpath("src", "aisdlc").rglob("*.py"):
        if _this_module_reads_the_setting(ast.parse(a_module.read_text(encoding="utf-8"))):
            the_readers.append(a_module.name)

    assert the_readers == ["the_project_directory.py"], (
        f"AISDLC_PROJECTS_DIR is read by {the_readers}, and the rule is that "
        "the_project_directory.py is the only one."
    )

    # And that one reader does answer, rather than only being the only candidate.
    os.environ["AISDLC_PROJECTS_DIR"] = "/somewhere/specific"
    try:
        assert where_projects_live() == Path("/somewhere/specific")
    finally:
        del os.environ["AISDLC_PROJECTS_DIR"]


def _this_module_reads_the_setting(the_tree: ast.AST) -> bool:
    """Whether any line of this module actually reads the setting, rather than naming it.

    **Both spellings, and matched on the object rather than the method name.** Python has
    `os.environ["X"]` and `os.environ.get("X")`, and the second one's AST puts `get` on the outer
    attribute and `os.environ` on its value — so a check that looks for the string `environ` in
    the method's own name finds neither spelling and reports a module that reads the setting as
    one that does not. That is the same class of mistake as the grep this replaced, one level
    down, and the only way to see it is to run the test that came out of it.
    """
    for a_node in ast.walk(the_tree):
        if (
            isinstance(a_node, ast.Subscript)
            and _is_the_environment(a_node.value)
            and _is_the_setting(a_node.slice)
        ):
            return True

        if (
            isinstance(a_node, ast.Call)
            and a_node.args
            and _is_the_setting(a_node.args[0])
            and _reads_the_environment(a_node.func)
        ):
            return True

    return False


def _is_the_setting(a_node: ast.AST | None) -> bool:
    """Whether this expression is the setting's name."""
    return isinstance(a_node, ast.Constant) and a_node.value == "AISDLC_PROJECTS_DIR"


def _is_the_environment(a_node: ast.AST | None) -> bool:
    """Whether this expression is `os.environ` and nothing else.

    **The one on the left of a subscript.** `os.environ["X"]` puts the environment on the
    subscript's value, and there is no method to allow for.
    """
    return (
        isinstance(a_node, ast.Attribute)
        and a_node.attr == "environ"
        and isinstance(a_node.value, ast.Name)
        and a_node.value.id == "os"
    )


def _reads_the_environment(a_node: ast.AST | None) -> bool:
    """Whether this expression is a lookup on the environment, whatever the method is called.

    **`os.environ.get` and `os.getenv` both answer here.** The method's own name is not what
    makes it an environment read, and keying on it is how `os.environ.get` gets missed by a
    check written for `os.getenv` — which is what happened the first two times this test ran.
    """
    if isinstance(a_node, ast.Name):
        return a_node.id == "os.environ"

    if not isinstance(a_node, ast.Attribute):
        return False

    if isinstance(a_node.value, ast.Name) and a_node.value.id == "os":
        return a_node.attr == "getenv"

    return _is_the_environment(a_node.value)


def test_a_card_says_how_long_a_run_has_been_on_the_step_it_is_on() -> None:
    """A card carries the step and the minutes on it, and a run that says nothing carries neither.

    **A real run spent twenty minutes inside one node and the board said "working" for all of
    it.** A run's own record carries a timestamp on every line, so the answer was in the store
    the whole time; what was missing was a card that read it. A person who can see "20 minutes on
    the planner" can decide whether that is slow or wrong, and a person shown the word "working"
    can decide neither — which is the only reason this is on a card rather than in a log.

    **Both fields are `None` together, and never one without the other.** A step with no time is
    a step from a run that has not moved since it started, and a time with no step is a number
    against nothing.
    """
    from aisdlc.store.the_board_reads import _how_long_on_this_step, _the_step_it_is_on
    from aisdlc.store.the_record_of_a_run import WhatARunSaid

    def an_event(what_happened: str, seconds_ago: int) -> WhatARunSaid:
        from datetime import UTC, datetime, timedelta

        return WhatARunSaid(
            what_happened=what_happened,
            happened_at=datetime.now(UTC) - timedelta(seconds=seconds_ago),
        )

    assert _the_step_it_is_on([]) is None
    assert _how_long_on_this_step([]) is None

    the_events = [
        an_event("a person asked for this", 900),
        an_event("ran offer_the_work_item_to_discover", 880),
        an_event("wrote DiscoveryReport", 860),
        an_event("ran apply_the_pickup", 840),
    ]

    assert _the_step_it_is_on(the_events) == "apply_the_pickup", (
        "the step is the last `ran <node>` line and not the last line of any kind: a run that "
        "wrote an artifact and is now inside the next node is on the node, and a card saying "
        "'wrote DiscoveryReport' for nine minutes is a card that cannot answer what it is asked"
    )

    how_long = _how_long_on_this_step(the_events)
    assert how_long is not None
    # Polling twice reads the clock twice; the band is generous enough to hold both.
    assert 800 <= how_long <= 900, f"a run 840s into its step reported {how_long}s on it"

    # A record of only sentences — no node has run yet — has no step and therefore no duration.
    only_sentences = [an_event("a person asked for this", 10)]
    assert _the_step_it_is_on(only_sentences) is None
    assert _how_long_on_this_step(only_sentences) is None


def test_a_card_never_names_a_framework_node_as_a_step() -> None:
    """`__interrupt__` is LangGraph's internal name and a card must not show it.

    **It appeared on a real card, reading "on `__interrupt__`".** The run's record says a node
    ran; when a run parks at a gate, the node that "ran" is the framework's own, and a double
    underscored name is the one signal this system has that the name is not about this system's
    work. A card names steps a person could act on, and says nothing rather than showing a
    framework's spelling to the one reader who cannot do anything with it.
    """
    from datetime import UTC, datetime

    from aisdlc.store.the_board_reads import _the_step_it_is_on
    from aisdlc.store.the_record_of_a_run import WhatARunSaid

    def an_event(what_happened: str) -> WhatARunSaid:
        return WhatARunSaid(what_happened=what_happened, happened_at=datetime.now(UTC))

    the_events = [
        an_event("ran offer_the_work_item_to_discover"),
        an_event("ran discover_the_repository"),
        an_event("ran __interrupt__"),
    ]

    assert _the_step_it_is_on(the_events) == "discover_the_repository", (
        "a framework's own node was shown to a person as the step this run is on. A run parked at "
        "a gate has `__interrupt__` as its last node and a card that says so is naming "
        "LangGraph's internals to the one reader who cannot do anything with them"
    )
    assert _the_step_it_is_on([an_event("ran __interrupt__")]) is None


def test_a_run_this_process_has_forgotten_is_said_to_have_been_forgotten(
    tmp_path: Path, monkeypatch
) -> None:
    """A card from a run whose process is gone says so, and answering it is refused.

    **A parked run is a graph with a checkpoint in memory, so a restart forgets it while the
    register keeps the card and the pending question.** Everything the store holds survives —
    the work item, the question, the decisions, the clone, the artifacts — and everything the
    process held does not. Before this, the API answered "not working, not ended, has a
    question" for both a run that is parked and a run nobody is in any more, and the board
    rendered the first as *waiting for you*.

    **The state is built rather than raced.** A test that starts a run and waits for it to reach
    a gate is a test with a timeout in it, and this case is about two processes and one register
    — which is a fact about the wiring and can be had by asking the store directly.
    """
    from fastapi.testclient import TestClient

    from aisdlc.application.the_runs_this_process_is_holding import TheRunsThisProcessIsHolding
    from aisdlc.domain.commissioned_request import a_request_about
    from aisdlc.domain.repository import Repository
    from aisdlc.domain.role import Role
    from aisdlc.domain.stage import Stage
    from aisdlc.domain.state_machine import transition
    from aisdlc.domain.work_item import a_work_item_commissioned_for_an_agent
    from aisdlc.store.the_record_of_a_run import what_the_gate_is_asking_about
    from aisdlc.store.the_register_of_work_items import the_work_item_a_commission_registers
    from aisdlc.store.what_a_run_records import the_move_was_recorded
    from aisdlc.store.where_the_register_lives import the_register, the_register_lives_at
    from aisdlc.web.the_api import the_api_over

    monkeypatch.setenv("AISDLC_PROJECTS_DIR", str(tmp_path / "projects"))
    the_register_lives_at(tmp_path / "the-register.sqlite3")

    # A run that walked to its first gate and parked there, built by hand.
    a_repository = Repository(owner="an", name="owner")
    the_work_item = the_work_item_a_commission_registers(
        the_register(),
        a_work_item_commissioned_for_an_agent(
            work_item_id="issue-7",
            repository=a_repository,
            accountable_role=Role.DEV,
            commissioned_by="a person",
            requested=a_request_about("add a health endpoint"),
        ),
    )
    # READY -> AWAITING_AGENT_PICKUP -> IN_PROGRESS_BY_AGENT -> AWAITING_HUMAN_APPROVAL, which
    # is the walk a run really makes, because the table is the only door and a state built by
    # assigning `.stage` would not be a state this system can be in. **Every move is recorded in
    # the register as it is made**, because a run that reached a gate without the register
    # knowing would be refused by the gate for a different reason than the one this test is
    # about — and a test that passes for the wrong reason is a test that has proved nothing.
    where_it_was = the_work_item
    for a_stage, an_agent in (
        (Stage.AWAITING_AGENT_PICKUP, "aisdlc-discover"),
        (Stage.IN_PROGRESS_BY_AGENT, "aisdlc-discover"),
        (Stage.AWAITING_HUMAN_APPROVAL, None),
    ):
        where_it_is_now = transition(where_it_was, a_stage, an_agent, Role.DEV)
        the_move_was_recorded(where_it_was, where_it_is_now)
        where_it_was = where_it_is_now

    what_the_gate_is_asking_about(the_register(), "issue-7", "DiscoveryReport", 1)

    # A process that has never heard of it. That is the whole case: a restart, not a failure.
    the_board = TestClient(the_api_over(the_register(), TheRunsThisProcessIsHolding()))

    what_it_says = the_board.get("/api/runs/issue-7").json()

    assert what_it_says["the_question"] is not None, (
        "the pending question is in the store and survived, which is the premise: everything the "
        "store holds is still true after a restart, and everything the process held is not"
    )
    assert what_it_says["is_this_process_holding_it"] is False, (
        "this process never started this run, so it is not holding it. Without this the board "
        "cannot tell a run that is parked from a run nobody is in any more — and it renders the "
        "first as waiting for you, which invites a decision the server will then refuse"
    )
    assert what_it_says["is_still_working"] is False

    the_answer = the_board.post(
        "/api/runs/issue-7/decisions",
        json={"approved": True, "decided_by": "a person", "reason": "it is right"},
    )
    assert the_answer.status_code == 410, (
        f"answering a run nobody is holding returned {the_answer.status_code} rather than 410, "
        "and a board that offers a button and then discards what is pressed into it is worse "
        "than one that does not offer it. The decision here is *admissible* — the work item is "
        "at its gate in the register and the question is pending — so nothing but the missing "
        "run can refuse it, and a refusal for any other reason would be blaming the wrong thing"
    )


def test_a_citation_must_be_a_file_the_agent_was_shown(
    a_clone_of_a_real_repository: ClonedRepository,
) -> None:
    """A file that exists in the clone is refused when the inspection did not contain it.

    **The check that a real run's gate did by hand.** A discovery report on a change to a
    repository's Dockerfile said the Dockerfile's *"contents are not shown"* and then cited the
    Dockerfile as evidence with a blob link, and the gate refused it for exactly that
    inconsistency — *"every evidence_files entry must correspond to a file whose contents were
    inspected"*. The engine proved the citation was a file of the clone, which it was, and that
    said nothing about whether the model had read it, which it had not.

    **Both refusals are exercised here, and they are different questions.** A path that is not in
    the clone is a link to nowhere. A path that is in the clone but was not in the inspection is a
    link to somewhere the report has not been — and the report saying so in one field while
    claiming it in another is worse, because the claim is what a reader acts on.
    """
    from aisdlc.agents.discover_the_repository import (
        CitedFileNotFoundError,
        _the_cited_files_that_are_in,
        _the_paths_the_inspection_showed,
    )
    from aisdlc.tools.inspect_the_repository import an_inspection_of_the_code

    a_repository = Repository(owner="an", name="owner")
    the_clone = a_clone_of_a_real_repository
    what_was_shown = _the_paths_the_inspection_showed(an_inspection_of_the_code(the_clone))

    # A file of the clone that the inspection did not show: the dotfiles, which no name in the
    # selection matches and which no suffix in the source list carries.
    a_file_that_was_withheld = ".gitignore"
    assert (the_clone.path / a_file_that_was_withheld).is_file(), (
        "the fixture repository has to hold a file the inspection withholds, or this test is "
        "about the refusal for a file that is not there — which the other check already covers"
    )
    assert a_file_that_was_withheld not in what_was_shown, (
        "the inspection is showing this file, so there is nothing here for the new check to catch"
    )

    with pytest.raises(CitedFileNotFoundError) as refused:
        _the_cited_files_that_are_in(
            the_clone, [a_file_that_was_withheld], a_repository, what_was_shown
        )

    assert "was not shown" in str(refused.value) or "does not contain it" in str(refused.value), (
        f"the refusal names the wrong thing: {refused.value}"
    )

    # And a file that was shown is accepted, or the check would be refusing everything.
    a_file_that_was_shown = "Dockerfile"
    assert a_file_that_was_shown in what_was_shown
    assert (
        _the_cited_files_that_are_in(
            the_clone, [a_file_that_was_shown], a_repository, what_was_shown
        )
        is not None
    )


def test_a_file_named_without_an_extension_is_still_shown_to_a_model(
    a_clone_of_a_real_repository: ClonedRepository,
) -> None:
    """A `Dockerfile` carries no suffix, and the suffix filter used to exclude exactly these.

    **A real run refused an architecture report for never having opened the Dockerfile.** The
    source-suffix list exists to exclude lockfiles, images and data, and "no extension" is not a
    suffix it knows — so the two files that describe how a repository is built and run were
    invisible to every agent in this system, while a real change to one was being asked for.
    """
    from aisdlc.tools.inspect_the_repository import an_inspection_of_the_code

    the_inspection = an_inspection_of_the_code(a_clone_of_a_real_repository)

    for a_file_named_without_an_extension in ("Dockerfile",):
        assert a_file_named_without_an_extension in the_inspection, (
            f"{a_file_named_without_an_extension} is not in the inspection, so a run asked to "
            "change it is being asked to reason about a file nobody showed it — which is the "
            "refusal a real run's gate gave, and the reason it was given"
        )
    assert "HEALTHCHECK" in the_inspection, (
        "the Dockerfile is in the inspection by name but its contents are not, so the file is "
        "named and unread — the shape of a citation a report cannot back"
    )


def test_one_inspection_built_for_one_consumer_is_not_handed_to_another(
    a_clone_of_a_real_repository: ClonedRepository,
) -> None:
    """Every reasoning agent reads the same inspection, and it contains code rather than a listing.

    **The mistake was made twice and then a third time by the same reasoning.** The inspection
    began as a listing, a manifest and a README because a discovery report is a summary of a
    repository's *shape*. The security analyst was then wired to it and reasoned from filenames,
    and a gate refused the report. The fix named the selection after the security question and
    applied it to everyone, so a run asked to change a Dockerfile was never shown the Dockerfile,
    and a gate refused that too. **The selection is now what a *change* tends to touch**, and
    this test holds that the three agents which need code are all given it.
    """
    from aisdlc.agents import discover_the_repository
    from aisdlc.tools.inspect_the_repository import an_inspection_of, an_inspection_of_the_code

    assert discover_the_repository.an_inspection_of_the_code is an_inspection_of_the_code, (
        "the discovery agent reads a listing again, so a discovery report says a file's contents "
        "are not shown and then cites it — which is what a real run's gate refused"
    )

    with_code = an_inspection_of_the_code(a_clone_of_a_real_repository)
    shape_only = an_inspection_of(a_clone_of_a_real_repository)

    # **About the contents and not the size.** A ratio was the first version of this assertion
    # and it is a claim about a repository rather than about the selection: this fixture holds
    # three files, so the two inspections are the same size whether or not the code is in one.
    # The claim is that a file's *contents* are reachable through one and not the other.
    assert "HEALTHCHECK" in with_code, (
        "the inspection with code in it does not contain the Dockerfile's contents, so the code "
        "is not reaching anybody and the difference between the two inspections is a name"
    )
    assert "HEALTHCHECK" not in shape_only, (
        "the shape-only inspection now carries file contents, so it is the inspection with code "
        "in it under another name — and the two would have to be kept in step"
    )


@pytest.fixture
def a_clone_of_a_real_repository(tmp_path: Path):
    """A real clone of a repository made locally, with a `Dockerfile` and a dotfile.

    **Made here rather than pointed at, because these three tests are about what a model is
    shown** and the only way to know what a model is shown is to build the thing that decides and
    look at it. It carries the two kinds of file the finding was about: a `Dockerfile`, which
    carries no suffix and was invisible to the selection, and a `.gitignore`, which exists in the
    clone and is not in the inspection — so the new citation check has something to catch.
    """

    from aisdlc.tools.github_client import Addresses
    from aisdlc.tools.github_clone_repository import (
        a_repository_to_clone,
        clone_repository,
    )

    the_bare = tmp_path / "the-origin.git"
    the_bare.mkdir()
    _git(the_bare, "init", "--bare", "--initial-branch=main")

    a_working_copy = tmp_path / "a-working-copy"
    a_working_copy.mkdir()
    _git(a_working_copy, "init", "--initial-branch=main")
    _git(a_working_copy, "config", "user.email", "a-test@example.com")
    _git(a_working_copy, "config", "user.name", "a test")
    (a_working_copy / "Dockerfile").write_text(
        "FROM node:22-bookworm-slim\n"
        "EXPOSE 3000\n"
        "HEALTHCHECK --interval=30s --timeout=3s --retries=3 \\\n"
        "  CMD curl -f http://localhost:3000/ || exit 1\n"
        'CMD ["npm", "start"]\n',
        encoding="utf-8",
    )
    (a_working_copy / ".gitignore").write_text("node_modules\n", encoding="utf-8")
    (a_working_copy / "package.json").write_text('{"name": "a-project"}\n', encoding="utf-8")
    _git(a_working_copy, "add", ".")
    _git(a_working_copy, "commit", "-m", "the first commit")
    _git(a_working_copy, "remote", "add", "origin", str(the_bare))
    _git(a_working_copy, "push", "origin", "main")

    return clone_repository(
        a_repository_to_clone(
            _A_REPOSITORY,
            Addresses(fetch_from=str(the_bare), origin_of_the_code=str(the_bare)),
            tmp_path / "a-clone",
        )
    )


def _git(where: Path, *what: str) -> str:
    what_happened = subprocess.run(
        ["git", *what], cwd=where, capture_output=True, text=True, check=False
    )
    if what_happened.returncode != 0:
        pytest.fail(f"git {' '.join(what)} in {where} failed: {what_happened.stderr}")
    return what_happened.stdout
