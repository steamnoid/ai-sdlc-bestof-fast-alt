"""That the real tier does not inherit what another file in it put into the environment.

**This is the tier's own result depending on what ran before it, and it was measured, not
suspected.** The same file, the same code, three full-suite runs and three isolated ones:

| | `test_inspect_for_security_risk.py` | `test_apply_the_plan.py` |
|---|---|---|
| in the full suite | failed **3 of 3** | errored in two runs |
| on its own | **passed 2 of 3** | **zero errors**, one known failure |

**That is not model variance — variance has the same distribution either way.** A file that passes
alone and fails in a suite is not testing what it says it is, and **the symptom it produces is
worse than any single defect**: a person re-runs the tier until it is green. That teaches exactly
the wrong lesson about the only tier that talks to a real model, and it is why four errors here
have moved between files from one run to the next.

**The mechanism is one fixture that does not give back what it took.**
`the_deployments_own_settings` calls `load_dotenv` and yields with nothing restored, so
in `os.environ` for the rest of the process — for every file after the first. **And this is not a
harness quirk**, which is the part worth asserting: a variable loaded in one test file is visible
in the next with no fixture involved at all. A tier where a test's answer depends on the file before
it cannot be used as a gate, however green it looks.

**The neighbour one function below already gets it right**, which is what makes this a rule rather
than a preference: `the_real_tier_is_being_watched` saves what it was, sets what it needs, and puts
it back. **Two session fixtures in one file, one of which gives back what it took** — and a reader
has no way to know which is which.

**Parsed and not imported**, for the reason every guard in this repository is parsed: the claim is
about what a fixture *does to the environment*, and a double that stands in for it could only prove
the double was used.
"""

from __future__ import annotations

import ast
from pathlib import Path

THE_REAL_TIER = Path(__file__).parent / "e2e" / "conftest.py"

WHAT_CHANGES_THE_ENVIRONMENT = {"load_dotenv", "setdefault", "pop"}
"""The calls that change `os.environ`, by name — because the claim is about the effect.

**`pop` is in the list because removing is giving back**, and a fixture that only pops what it set
without saving what was there first has still lost information. The assertion below asks for both
halves, so the set only has to name the calls that touch the environment at all.
"""


def _the_fixtures_that_change_the_environment() -> dict[str, ast.FunctionDef]:
    """Every fixture in the real tier's conftest that touches the environment, by name.

    **A fixture and not any function**, because a helper that loads dotenv is called *by* a
    fixture and its effect belongs to whichever fixture called it — and a guard that reported the
    helper would name something nobody can wrap in a teardown.
    """
    the_tree = ast.parse(THE_REAL_TIER.read_text(encoding="utf-8"))
    what_each_does: dict[str, ast.FunctionDef] = {}

    for a_definition in the_tree.body:
        if not isinstance(a_definition, ast.FunctionDef):
            continue
        # **Both a plain call and an attribute, and the reason is a real one.** `load_dotenv(...)`
        # is a bare name and `os.environ.setdefault(...)` is an attribute, and a guard that only
        # saw attributes would have called this file clean while it was the thing making the
        # tier depend on its neighbours.
        called: set[str] = set()
        for a_node in ast.walk(a_definition):
            if not isinstance(a_node, ast.Call):
                continue
            if isinstance(a_node.func, ast.Attribute):
                called.add(a_node.func.attr)
            if isinstance(a_node.func, ast.Name):
                called.add(a_node.func.id)
        if WHAT_CHANGES_THE_ENVIRONMENT & called:
            what_each_does[a_definition.name] = a_definition

    return what_each_does


def test_every_fixture_that_changes_the_environment_gives_it_back() -> None:
    """A session fixture that loads a deployment's settings must not leave them loaded.

    **Yielding is required and is not enough**, because a fixture that yields and does nothing
    afterwards has still taken and not returned. So the fixture has to do one of two things after
    the yield: put a saved value back, or remove what it added — and the difference between those
    two is what a deployment that set a variable deliberately is relying on.
    """
    what_each_does = _the_fixtures_that_change_the_environment()

    assert what_each_does, (
        f"{THE_REAL_TIER.name} changed nothing this guard can see, so every rule below is "
        "satisfied "
        "by a conftest that has stopped loading a deployment's settings at all. That would be a "
        "different defect and this assertion could not notice it"
    )

    never_given_back: list[str] = []

    for a_name, a_definition in what_each_does.items():
        what_it_does_after_the_yield = _what_a_fixture_does_after_its_yield(a_definition)

        if not _gives_the_environment_back(what_it_does_after_the_yield):
            never_given_back.append(a_name)

    assert not never_given_back, (
        f"{never_given_back} change the environment and never give it back. Every variable in a "
        "deployment's `.env` is then in the process for every file that follows, which is how a "
        "test file passes on its own and fails in the suite — and a person who has seen that twice "
        "re-runs the tier until it is green, which is the one lesson this tier must never teach. "
        "The fixture beside this one already saves what it was and puts it back"
    )


def _what_a_fixture_does_after_its_yield(a_definition: ast.FunctionDef) -> list[ast.stmt]:
    """The statements after the `yield`, and an empty list when the fixture never yields.

    **An empty list is the answer that fails**, and that is deliberate: a fixture that changes the
    environment and returns without yielding has no teardown at all, and reporting it as "did
    nothing afterwards" says exactly what is wrong with it.
    """
    for a_statement in a_definition.body:
        if isinstance(a_statement, ast.Expr) and isinstance(a_statement.value, ast.Yield):
            return list(a_definition.body[a_definition.body.index(a_statement) + 1 :])
        if isinstance(a_statement, ast.Yield):
            return list(a_definition.body[a_definition.body.index(a_statement) + 1 :])

    return []


def _gives_the_environment_back(what_it_does_afterwards: list[ast.stmt]) -> bool:
    """Whether these statements put the environment back — either a saved value, or a removal.

    **Two shapes and both are accepted**, because a variable that was absent before needs removing
    and a variable that was set needs restoring, and a fixture that handles only one of them is
    correct for half the deployments and wrong for the other half.
    """
    for a_statement in what_it_does_afterwards:
        if not isinstance(a_statement, ast.Assign):
            continue
        for a_target in a_statement.targets:
            if isinstance(a_target, ast.Subscript) and _is_the_environment(a_target.value):
                return True

    for a_statement in what_it_does_afterwards:
        if not isinstance(a_statement, ast.If):
            continue
        for a_nested in ast.walk(a_statement):
            if (
                isinstance(a_nested, ast.Call)
                and isinstance(a_nested.func, ast.Attribute)
                and a_nested.func.attr == "pop"
            ):
                return True

    return False


def _is_the_environment(a_node: ast.expr) -> bool:
    return (
        isinstance(a_node, ast.Attribute)
        and a_node.attr == "environ"
        and isinstance(a_node.value, ast.Name)
        and a_node.value.id == "os"
    )


def test_a_variable_loaded_in_one_test_file_reaches_the_next_one() -> None:
    """The harness behaviour this conftest leans on, asserted so it cannot be forgotten.

    **Asserted because it is what makes the defect invisible.** If pytest isolated the environment
    between files, the missing teardown in `conftest.py` would be harmless and this whole cycle
    would be a style argument. **It does not isolate**, so the teardown is the only thing standing
    between a deployment's `.env` and the next file's results — and that is a fact about this
    repository's tooling worth writing down rather than assuming.
    """
    import os

    a_variable_this_test_invented = "AISDLC_A_VARIABLE_ONLY_THIS_FILE_MADE"
    os.environ[a_variable_this_test_invented] = "1"
    try:
        from dotenv import load_dotenv

        assert load_dotenv is not None, (
            "the real tier loads its deployment's settings with load_dotenv, and this file"
            "asserts what that call does to the environment rather than assuming it"
        )
        assert os.environ.get(a_variable_this_test_invented) == "1", (
            "the environment this test set is not visible to it, so a fixture that changes the "
            "environment and never restores it would leave nothing behind and this whole rule "
            "would be about nothing"
        )
    finally:
        os.environ.pop(a_variable_this_test_invented, None)
