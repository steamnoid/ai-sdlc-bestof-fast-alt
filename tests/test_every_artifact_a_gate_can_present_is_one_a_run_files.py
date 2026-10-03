"""That every artifact a run can put in front of a person is one a run knows to write down.

**`AnArtifactARunFiles` is a union of eight classes, and the eight are written out by hand.** A new
stage gets an `Artifact` member in one place and this union is somewhere else, and **nothing
compares them** - so a ninth artifact would be presentable at a gate and absent from the run's
directory, which is exactly the failure the comment above the union records happening:

> a run finished, a `PullRequestRequest` was written, and `SecurityReport.json` was not, and the run
> *succeeded*, because every signal a run gives says success.

**The comment above the line already said what a forgotten artifact is; this line is where the
forgetting happened.** So the union is the thing the comment is about, **and it is the one list in
this package with nothing checking it.**

**Compared by name, because `Artifact`'s members *are* the class names.** `DISCOVERY_REPORT =
"DiscoveryReport"`, so the two can be read against each other directly rather than through a mapping
that could itself be wrong.

**And the guard is proved by breaking it on purpose**, because a guard that has only ever been green
has never been shown to fail. This repository has paid for that twice - the `AgentState`
completeness guard, which was a claim about runtime until a channel was added and nothing broke, and
the dangling-`goto` guard. **A test is only evidence that it can fail if somebody has watched it
fail**, and the way to arrange that is to remove a member and watch.
"""

from __future__ import annotations

import ast
from pathlib import Path

from aisdlc.agents.artifact import Artifact

WHERE_THE_UNION_LIVES = "src/aisdlc/tools/what_a_run_leaves_behind.py"
THE_UNION = "AnArtifactARunFiles"


def _the_class_names_the_union_names() -> set[str]:
    """Every class named in the union, read out of the source rather than imported.

    **Read from the source because the union is a type alias and its members are not values.** A
    test importing `AnArtifactARunFiles` gets an opaque `types.UnionType`, and unpacking it by hand
    would be a second copy of the list this test exists to check.

    **`ast.TypeAlias` and not `ast.AnnAssign`, and the first version of this asked for the wrong
    one.** A `type X = ...` statement is not an annotated assignment, and the guard failed on code
    that was correct - which is the failure mode where a test that is red is easier to believe than
    a test that is green.
    """
    the_file = Path(__file__).resolve().parent.parent / WHERE_THE_UNION_LIVES
    the_tree = ast.parse(the_file.read_text(encoding="utf-8"))
    for a_node in ast.walk(the_tree):
        if not isinstance(a_node, ast.TypeAlias):
            continue
        if a_node.name.id != THE_UNION:
            continue
        # `A | B | C` is nested `BinOp`s and not a list, so the leaves are what carries names.
        return {a_name.id for a_name in ast.walk(a_node.value) if isinstance(a_name, ast.Name)}
    raise AssertionError(f"{WHERE_THE_UNION_LIVES} defines no {THE_UNION} union to check")


def test_every_artifact_a_gate_can_present_is_one_a_run_files() -> None:
    """An artifact presentable at a gate and not written beside the clone is a run that lied.

    **Both directions, because the surplus matters too.** A class in the union that no artifact
    names is not harmless: it is a file the run writes for something nobody decided on, and the
    surplus is how a union starts accumulating entries nobody can account for.
    """
    what_a_run_files = _the_class_names_the_union_names()
    what_a_gate_can_present = {an_artifact.value for an_artifact in Artifact}

    missing = sorted(what_a_gate_can_present - what_a_run_files)
    surplus = sorted(what_a_run_files - what_a_gate_can_present)

    assert not missing, (
        f"these artifacts can be put in front of a person at a gate and are not in "
        f"{THE_UNION}, so a run that produced one would write no file for it and every signal the "
        f"run gives would say it succeeded: {missing}. The union and the Artifact enum are two "
        f"lists written by hand in two files, and a stage added to one is not added to the other."
    )
    assert not surplus, (
        f"these classes are in {THE_UNION} and no artifact names them, so a run writes a file for "
        f"something nobody decided on: {surplus}. That is how a list of names starts accumulating "
        f"entries nobody can account for."
    )
