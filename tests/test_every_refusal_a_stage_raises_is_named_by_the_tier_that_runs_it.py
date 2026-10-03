"""That a refusal the stage can raise is named by the tier that runs the stage.

**Two refusals in this repository are raised and caught by nothing at all.** Found by reading
the two stage modules against the two e2e fixtures that run them:

```text
src/aisdlc/agents/apply_the_plan.py:137     raise TheImplementerWasNeverAskedError
src/aisdlc/agents/implement_the_plan.py:349   raise FileWrittenTwiceError
```

**Neither name appears anywhere under `tests/`.** So if either fired on a real run, the
fixture running that stage has nothing to catch, the refusal leaves `pytest.raises`, and
the tier reports it as a setup error - four of them at a time, one per test sharing it.

**And that is not a shape I am predicting. It is a shape I hit three times in one cycle.**
All three were added by me, correctly, and all three broke a tier the same way:

| the refusal | the tier it broke |
|---|---|
| `TheCommitHoldsNoneOfTheFilesThePlanNamedError` | `test_apply_the_plan.py` |
| `AWriteThatChangesNothingError` narrowed | `test_apply_the_plan.py` |
| `PlannedFileNotWrittenError` on a decline | `test_implement_the_plan.py` |

**A refusal added correctly is not a refusal added completely.** It has two other places
to join, and a reader of the function that raises it has no reason to know either. **So
the two are one obligation seen from two sides, and neither place can check the other.**

**Names are read out of the source rather than imported, because the failure is that a
name is *absent* from another module** - and an import here would have to be written down
in this file, which is the very thing being checked. `ast` rather than a regex, because
a comment naming a class would otherwise read as a definition.

**Strict on purpose, and there is no list of exemptions.** The lesson is not that some
refusals should be accounted for: a tier **cannot predict** which one a model will
trigger today, so every one of them has to be. **A refusal no tier expects is a refusal
nobody has proved fires.**
"""

from __future__ import annotations

import ast
from pathlib import Path

WHERE_THE_STAGES_LIVE = "src/aisdlc/agents"
WHERE_THE_TIERS_THAT_RUN_THEM_LIVE = "tests/e2e"

THE_STAGES = ("implement_the_plan.py", "apply_the_plan.py")
THE_TIERS_THAT_RUN_THEM = ("test_implement_the_plan.py", "test_apply_the_plan.py")


def _every_refusal_a_module_defines(where: Path) -> set[str]:
    """The names of every exception class the file defines, read from its syntax tree.

    **Defined rather than raised**, because the question is whether the name is accounted
    for elsewhere; which statements raise it says nothing about whether it can happen.
    """
    the_tree = ast.parse(where.read_text(encoding="utf-8"))
    return {
        a_node.name
        for a_node in ast.walk(the_tree)
        if isinstance(a_node, ast.ClassDef) and a_node.name.endswith("Error")
    }


def _every_name_a_module_mentions(where: Path) -> set[str]:
    """Every name a module imports, catches, or subclasses.

    **Imports are read as well as handlers, and both together.** A tier may legitimately
    name a refusal only to import it and assert on its text - a unit test asking for the
    sentence - and a guard counting only `except` clauses would send a reader looking for
    a `try` the file does not need. **What this refuses is a name absent from the tier.**
    """
    the_tree = ast.parse(where.read_text(encoding="utf-8"))
    mentioned: set[str] = set()

    for a_node in ast.walk(the_tree):
        if isinstance(a_node, ast.ImportFrom):
            mentioned.update(an_alias.name for an_alias in a_node.names)
        elif isinstance(a_node, ast.ClassDef):
            mentioned.update(a_base.id for a_base in a_node.bases if isinstance(a_base, ast.Name))
        elif isinstance(a_node, ast.ExceptHandler) and a_node.type is not None:
            the_caught = a_node.type
            if isinstance(the_caught, ast.Name):
                mentioned.add(the_caught.id)
            elif isinstance(the_caught, ast.Tuple):
                mentioned.update(
                    an_element.id
                    for an_element in the_caught.elts
                    if isinstance(an_element, ast.Name)
                )

    return mentioned


def test_every_refusal_a_stage_raises_is_named_by_the_tier_that_runs_it() -> None:
    """Every refusal the two stages define is named in a tier that exercises them.

    **The claim is the weak one - the name is not absent - because that is the claim that
    was false three times.** A stricter guard demanding each one be *caught* would have
    needed an exemption list on its first day, and an exemption list is a place to forget.
    """
    where_the_repository_is = Path(__file__).resolve().parent.parent

    named_by_some_tier: set[str] = set()
    for a_tier in THE_TIERS_THAT_RUN_THEM:
        named_by_some_tier |= _every_name_a_module_mentions(
            where_the_repository_is / WHERE_THE_TIERS_THAT_RUN_THEM_LIVE / a_tier
        )

    unaccounted_for: dict[str, list[str]] = {}
    for a_stage in THE_STAGES:
        refusals = _every_refusal_a_module_defines(
            where_the_repository_is / WHERE_THE_STAGES_LIVE / a_stage
        )
        the_missing = sorted(refusals - named_by_some_tier)
        if the_missing:
            unaccounted_for[a_stage] = the_missing

    assert not unaccounted_for, (
        f"these refusals are defined by the stages and named by no tier that runs them: "
        f"{unaccounted_for}. A tier that does not expect a refusal cannot catch it, so it "
        "leaves `pytest.raises` and the run is reported as a setup error - one per test "
        "sharing the fixture, which is four at a time and reads as *the system is broken* "
        "rather than as *this run was refused for a correct reason*. Adding a refusal means "
        "adding it to the tier as well, and a reader of the function that raises it has no "
        "reason to know that."
    )
