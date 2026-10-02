"""The domain reaches nothing that could be replaced, restarted, or argued with.

**This is the guard, and it is in the default suite because nothing else is watching.** Ten
modules live in `src/aisdlc/domain` and every one of them is a rule: the stages, the roles, the
biconditional, the transition table. A rule is only a rule while the thing that evaluates it cannot
be swapped for one that answers differently — and `aisdlc.store`, `aisdlc.tools` and `aisdlc.llm`
are all replaceable by a test double in a single line, silently, with no assertion failing
anywhere else.

**What the domain may reach: the standard library, `pydantic`, and its own layer.** Not pydantic
because it is unimportant — it is the boundary every model in this repository crosses and the
domain is full of models — so the rule is stated as what it is rather than dressed up as a
restriction that happens to be true.

**And the second segment is what is read, not the first.** `from aisdlc.llm.x import y` and
`from aisdlc.domain.x import y` both begin with `aisdlc`, so a guard that looked at the first
segment would call a domain module reaching a sibling layer perfectly clean. The layers are named
in the second segment, so that is the segment this keeps.

**Two of the four tests exist to prove the guard can refuse, and that is the whole of them.** A
guard that has only ever agreed is not known to hold — a sibling project built by eleven workers in
parallel shipped fourteen gates of which **eight were green because there was nothing for them to
judge**, written before the domain they policed. A refusal fixture that lives only in a test's
body is the same shape of claim, so these are held as source strings and run through the same
function the real modules go through.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

WHERE_THE_DOMAIN_IS = Path(__file__).resolve().parent.parent / "src" / "aisdlc" / "domain"

# Every layer beside the domain. `application` and `observability` are here because they were
# here when the guard was written, and a layer added tomorrow would be caught by the test that
# reads this set from `src/aisdlc` rather than by a reader noticing this list go stale.
THE_LAYERS_BESIDE_THE_DOMAIN = {
    "agents",
    "application",
    "approval",
    "creative",
    "graph",
    "llm",
    "observability",
    "persistence",
    "store",
    "tools",
    "web",
}

# A third-party package this repository owns, and the only one the domain is allowed to reach.
# A domain that imports `httpx` or `openai` can open a socket or spend money in a place where
# the only rule anyone should be trusting is a transition table.
THE_PACKAGES_THE_DOMAIN_MAY_REACH = {"pydantic"}


def every_domain_module() -> list[Path]:
    """Every module in the domain, in a stable order so a failure reads the same twice."""
    return sorted(WHERE_THE_DOMAIN_IS.glob("*.py"))


def what_a_module_imports(source: str) -> set[str]:
    """Every module an import names, as the dotted path it was written as.

    **The full path and not the first segment, for the reason the module's docstring gives.**
    """
    imported: set[str] = set()

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)

    return imported


def what_a_module_reaches_forbiddenly(source: str) -> set[str]:
    """The names a module in the domain may not name, and only those."""
    forbidden: set[str] = set()

    for name in what_a_module_imports(source):
        segments = name.split(".")

        if segments[0] == "aisdlc":
            if len(segments) > 1 and segments[1] in THE_LAYERS_BESIDE_THE_DOMAIN:
                forbidden.add(name)
            continue

        if segments[0] in sys.stdlib_module_names:
            continue

        if segments[0] in THE_PACKAGES_THE_DOMAIN_MAY_REACH:
            continue

        forbidden.add(name)

    return forbidden


# A module the guard must refuse, held as source so the refusal is exercised and not asserted
# about. It reaches a sibling layer and a package this repository does not own, and it reaches
# the standard library, which the guard must not flag — a guard that flagged `pathlib` would be
# refused by every module it is meant to hold.
A_MODULE_THAT_A_GUARD_REFUSES = '''
"""A module the guard must refuse, held here so the guard has been seen to refuse one."""

from __future__ import annotations

from pathlib import Path

from aisdlc.llm.model_factory import a_model_for
from openai import OpenAI
'''

# The other direction: a domain module importing its own layer, the standard library and pydantic
# is the whole point of the package, and a guard that could not tell that from a reach into
# `aisdlc.store` would have to be moved somewhere a person has to remember it.
A_MODULE_THE_DOMAIN_MAY_IMPORT = '''
"""A module the guard must accept, held here so the guard has been seen to agree with one."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from aisdlc.domain.stage import Stage
'''


def test_the_domain_is_not_empty_because_a_guard_over_nothing_is_green() -> None:
    """A rule with nothing under it is a wish that costs a cycle to discover.

    This is the lesson of the sibling project, written as an assertion rather than told: a guard
    is green over an empty directory for exactly the same reason it is green over a clean one, and
    the two are indistinguishable from the outside.
    """
    how_many = len(every_domain_module())

    assert how_many >= 5, (
        f"the domain holds {how_many} modules, and this guard has very little to judge. Either "
        "the domain is barely started or its rules are somewhere else — and both are the same "
        "failure seen from inside this file"
    )


def test_no_module_in_the_domain_reaches_anything_it_may_not() -> None:
    """The rule itself, over every module there is rather than over a hand-picked one."""
    offending = {
        a_module.name: what_a_module_reaches_forbiddenly(a_module.read_text(encoding="utf-8"))
        for a_module in every_domain_module()
    }
    reached_forbiddenly = {name: reached for name, reached in offending.items() if reached}

    assert reached_forbiddenly == {}, (
        f"these domain modules reach something they may not: {reached_forbiddenly}. A domain "
        "that can import a store, a model, a filesystem or a graph is a domain whose rules a "
        "caller can change the answer to, and the rule that is supposed to stop that is the one "
        "crossed"
    )


def test_a_module_the_domain_may_import_is_not_refused() -> None:
    """The other direction, because a guard that refuses everything refuses the domain too."""
    refused = what_a_module_reaches_forbiddenly(A_MODULE_THE_DOMAIN_MAY_IMPORT)

    assert refused == set(), (
        f"a domain module may import the standard library, pydantic and its own layer, and this "
        f"fixture is refused for: {refused}. A rule that cannot tell `aisdlc.domain.stage` from "
        "`aisdlc.store` has to live somewhere a person remembers it instead"
    )


def test_the_guard_refuses_a_module_that_reaches_both_ways() -> None:
    """A guard that has only ever agreed is not known to hold, and this is where it agrees.

    **Both refusals are asserted separately** because they are two different mistakes: a package
    this repository does not own, and a sibling layer of its own. A guard holding only one of them
    lets the other through, and the one it lacks is the one nobody thinks of.
    """
    reached = what_a_module_reaches_forbiddenly(A_MODULE_THAT_A_GUARD_REFUSES)

    assert "aisdlc.llm.model_factory" in reached, (
        "the fixture must reach a sibling layer, or this test is not testing that half"
    )
    assert "openai" in reached, (
        "the fixture must reach a package this repository does not own, or this test is not "
        "testing that half either"
    )
    assert "pathlib" not in reached, (
        "and the fixture reaches the standard library too, which the guard must NOT flag — a "
        "guard that flagged a stdlib import would be refused by the modules it exists to hold"
    )
