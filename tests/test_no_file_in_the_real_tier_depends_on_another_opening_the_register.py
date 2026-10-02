"""That no file in the real tier depends on another file having opened the register.

**Two of fourteen files open it; twelve inherit it.** Both openers do it in a `scope="module"`
fixture against their own temporary directory, so when the module ends the directory is cleaned and
**the process-wide connection is left open on a path that no longer exists.** The next file that
touches the register gets that one, and nothing says so.

**The resource is process-wide and its scope is a module, and that is the whole defect.**
`the_register_lives_at` assigns a module global, so *"each file opens its own"* is not available —
a second call closes the first connection. The two shapes that *are* available are a register per
session, where every file in the tier shares one deliberately, and a register per test, where none
share. **The second is what this demands**, because a shared register means one file's work items
are visible to the next, which is cross-talk of exactly the kind the sharing was meant to remove.

**And the symptom this caused was not the four errors.** Those were the environment, fixed in the
cycle before and measured: `4 errors → 0`, and the run went from 21 minutes to 9. **This is a
separate hazard, found while looking for a second cause that turned out not to exist** — so it is
recorded as what it is, a latent trap, rather than dressed up as the explanation for something else.

**The assertion is one line and it is deliberately blunt:** the register is opened in exactly one
place in this tier, and that place is the conftest every test gets. A file that opens it itself has
chosen a scope, and the scope is a property of the process rather than of the file.

**Parsed rather than imported**, for the reason every guard in this repository is parsed: the claim
is about what the files *do*, and a double could only prove the double was used.
"""

from __future__ import annotations

import ast
from pathlib import Path

THE_TIER = Path(__file__).parent / "e2e"
WHERE_THE_REGISTER_MAY_BE_OPENED = "conftest.py"
"""The one file allowed to open it, and the reason is scope rather than convenience.

**A conftest fixture every test gets, rather than a helper every file remembers to call.** The
alternative — a documented helper imported by twelve files — is twelve places to forget, and the
twelfth is discovered by a file that fails only when it runs after one of the other eleven.
"""

WHAT_OPENS_THE_REGISTER = "the_register_lives_at"


def _the_files_that_open_the_register() -> list[str]:
    """Every file in the real tier that opens the register, by name.

    **The name is read off the call rather than an import**, because a file that imports the
    function without calling it is not opening anything, and a file that reaches it by another
    route still is. A guard keyed on imports would miss the second and flag the first.
    """
    what_opens: list[str] = []

    for a_file in sorted(THE_TIER.rglob("*.py")):
        for a_node in ast.walk(ast.parse(a_file.read_text(encoding="utf-8"))):
            if not isinstance(a_node, ast.Call):
                continue
            called = getattr(a_node.func, "id", None) or getattr(a_node.func, "attr", None)
            if called == WHAT_OPENS_THE_REGISTER:
                what_opens.append(a_file.name)
                break

    return what_opens


def test_the_register_is_opened_in_one_place_and_not_by_a_test_file() -> None:
    """A file that opens it has chosen a scope, and the scope is the process."""
    what_opens = _the_files_that_open_the_register()

    opened_by_a_test_file = [
        a_name for a_name in what_opens if a_name != WHERE_THE_REGISTER_MAY_BE_OPENED
    ]

    assert not opened_by_a_test_file, (
        f"{opened_by_a_test_file} open the register themselves. The connection is process-wide, so "
        "whichever of them ran last owns it for the whole tier, and the other twelve files inherit "
        "a path from a temporary directory that belonged to a module which has since ended. A file "
        "that passes alone and fails in a suite is the symptom, and it is why this guard exists: "
        f"the register should be opened by {WHERE_THE_REGISTER_MAY_BE_OPENED}, for every test, "
        "and by nobody else"
    )


def test_the_register_is_opened_for_every_test_and_not_only_once_per_session() -> None:
    """A register shared by the whole tier is cross-talk wearing the name of isolation.

    **Asserted because the two shapes look equally correct from the outside.** One register for the
    tier means a work item one file commissioned is visible to every file after it, and a test that
    counts what a register holds would then be counting another file's. One per test costs a
    `sqlite3.connect` and closes the previous connection by opening this one — **which is what
    `the_register_lives_at` already does**, so the isolation is free and the sharing is a choice.
    """
    the_conftest = THE_TIER / WHERE_THE_REGISTER_MAY_BE_OPENED
    what_it_declares = [
        a_definition
        for a_definition in ast.parse(the_conftest.read_text(encoding="utf-8")).body
        if isinstance(a_definition, ast.FunctionDef)
        and WHAT_OPENS_THE_REGISTER in ast.unparse(a_definition)
    ]

    assert what_it_declares, (
        f"{the_conftest.name} does not open the register, and the two files that used to open it "
        "themselves have been stopped by the guard above. **So there is nothing that opens it at "
        "all**, and every test in this tier now depends on whichever test ran first — which is the "
        "defect the guard was written to end, moved rather than fixed"
    )

    opening = what_it_declares[0]
    decorators = " ".join(ast.unparse(one) for one in opening.decorator_list)

    assert "autouse=True" in decorators, (
        "the fixture that opens the register is not autouse, so a test that does not ask for it by "
        "name gets whatever the last one opened. **The whole point is that no file has to "
        "remember**, and an autouse fixture is the only shape that guarantees it"
    )
