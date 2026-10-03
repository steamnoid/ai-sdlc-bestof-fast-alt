"""That no function in the package is defined and never called.

**Two are, and both were left behind by changes that were otherwise correct.**

```text
src/aisdlc/graph/lifecycle.py:567              _recording_with
src/aisdlc/store/the_register_of_work_items.py:299  _version_of
```

`_version_of` is the leftover of the refusal-message fix: the refusal now reads the stage off the
row it just fetched, so the helper that rendered a stage from a `WorkItem` lost its only caller,
**and its name promises a counter while it returns a stage.** In a file that otherwise reads as
though it were about concurrency, that is a name a reader has to stop and check.

`_recording_with` builds a node that writes a record and changes no channel, and its own docstring
says *the difference from `record` is the whole point of it* - **and no node uses it**, so the
difference it exists to draw is drawn by nothing.

**Both were noticed only by reading, one at a time.** `_version_of` was written down as a known
false name and deliberately left, on the grounds that a rename is its own change;
`_recording_with` had not been noticed at all. **A thing that has to be noticed by a human reading
every file is not a practice, it is a hope** - and this repository already records that
`github.read_file` is kept with no caller for the same reason, **with the rule written down rather
than the tool deleted.**

**The scope is measured, and it is the whole design.** Counting every private function with no
caller gives **thirty**, because **twenty-eight are Pydantic validators** - called by the framework
through their decorator, never by name. A guard written on the naive count would be red on twenty-
eight positions it has no business being red on, **which is how a guard becomes a thing people
learn to `xfail`.** Excluding decorated functions is not a convenience: it is the difference
between a guard and noise.

**`ast`, and the count is a subtraction.** The helper's own definition is one occurrence of its own
name, so "called" means "named somewhere in `src/` more than once" - which is a claim about the
package, not about whether the code runs.
"""

from __future__ import annotations

import ast
from pathlib import Path

WHERE_THE_PACKAGE_LIVES = "src/aisdlc"


def _every_source_file_in_the_package(where: Path) -> list[Path]:
    """Every module under the package, because a caller may be in any of them."""
    return sorted(where.rglob("*.py"))


def _the_names_defined_in(a_file: Path) -> dict[str, ast.FunctionDef]:
    """The private functions a module defines, each with the node that knows how it is decorated.

    **Named with a single leading underscore, and not dunder.** A leading underscore is Python's own
    signal that a name is not part of a module's interface, and dunder names belong to the language
    rather than to this package - a run of `_missing_` would be a run of things `Enum` calls.
    """
    the_tree = ast.parse(a_file.read_text(encoding="utf-8"))
    return {
        a_node.name: a_node
        for a_node in ast.walk(the_tree)
        if isinstance(a_node, ast.FunctionDef)
        and a_node.name.startswith("_")
        and not a_node.name.startswith("__")
    }


def _every_undecorated_function_nobody_calls() -> list[str]:
    r"""Where each uncalled function is, and what it is called, as one list a reader can act on.

    **`\`-joined rather than a dict of lists**, because the answer a reader wants is *this name at
    this line*, and a mapping would make them join two lists to get it.
    """
    where_the_package_is = Path(__file__).resolve().parent.parent / WHERE_THE_PACKAGE_LIVES
    every_source_file = _every_source_file_in_the_package(where_the_package_is)
    every_name_in_the_package = "\n".join(
        a_file.read_text(encoding="utf-8") for a_file in every_source_file
    )

    uncalled: list[str] = []
    for a_file in every_source_file:
        for a_name, a_node in _the_names_defined_in(a_file).items():
            how_many_times_it_is_named = every_name_in_the_package.count(a_name)
            if how_many_times_it_is_named > 1:
                continue
            if a_node.decorator_list:
                continue
            uncalled.append(f"{a_file.relative_to(where_the_package_is)}:{a_node.lineno} {a_name}")

    return uncalled


def test_no_function_in_the_package_is_defined_and_never_called() -> None:
    """Every function written here is either called here or is called by a framework.

    **The exclusion is the second clause and it is measured, not argued.** Twenty-eight of the
    thirty private functions nobody names are Pydantic validators and `_missing_`; they are
    called by a decorator this package does not own. **Without the exclusion this test would be red
    on twenty-eight positions it has no business being red on**, and a guard that is wrong that
    often is a guard people learn to switch off.
    """
    uncalled = _every_undecorated_function_nobody_calls()

    assert not uncalled, (
        f"these functions are defined in the package and named nowhere else in it: {uncalled}. "
        "A private function nothing calls is not a seam, it is a class nobody instantiates - and a "
        "name that promises something other than what it returns sends a reader to stop and check. "
        "Either call it, or delete it: leaving it with a note about why it is wrong moves the "
        "decision to whoever reads the file next, which is how `_version_of` sat here for a cycle "
        "with its own docstring admitting the name was false."
    )
