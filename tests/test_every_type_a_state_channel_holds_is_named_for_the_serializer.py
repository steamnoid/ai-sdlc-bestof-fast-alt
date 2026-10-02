"""Every type a state channel holds is named for the checkpoint serializer.

**A comment in `lifecycle.py` claimed this guard existed and named it.** It read:

> a test refuses to let a type be added to the domain without being named here

and then, four lines later, a name that is exactly this file's. **It did not exist.** Thirty-one
types are named for the serializer and nothing was checking the thirty-second, so the comment
described a guard that had never run, and a reader looking for it would have found this sentence
instead of a test.

**Why the naming matters at all.** `JsonPlusSerializer` is built with
`allowed_msgpack_modules=TYPES_A_CHECKPOINT_MAY_HOLD`, so an unnamed type of this repository's own
is one the deserialiser refuses to construct on read. `lifecycle.py` says the consequence in its
own words: *"an unnamed type stops being readable from a checkpoint in a future version of the
runtime"* — and the day LangGraph enforces the warning it prints today, a run whose state was
written to disk **cannot be resumed**, with no error of ours in the message.

**And the rule is about this repository's classes and not about every name in an annotation.**
Splitting `list[FileToWrite] | None` yields `list` and `None` as well as `FileToWrite`, and the
first two are handled by msgpack itself — the allowlist exists for the types the runtime has to
import by name to rebuild them, which are this repository's. So a name is a violation exactly when
**a class defined under `src/aisdlc` answers to it and the allowlist does not list it**, and the
set of such classes is read off the syntax tree rather than imported: importing every module to
learn its classes is a thing that has to keep working before anything else does, **and a list
built by importing fails in exactly the situation the list exists for.**

**Annotations rather than values, and `ForwardRef` first.** A `TypedDict` keeps its annotations as
`typing.ForwardRef`, each carrying the original text in `__forward_arg__`. A reader that calls
`typing.get_args` on one gets `()` and a reader that looks for `__name__` gets `None`; **both
return an empty set without raising**, which is the failure this guard exists to catch,
reproduced inside the guard itself. It was caught by the second test in this file, which is why
that test is here.
"""

from __future__ import annotations

import ast
import typing
from pathlib import Path

from aisdlc.graph.agent_state import AgentState
from aisdlc.graph.lifecycle import TYPES_A_CHECKPOINT_MAY_HOLD

WHERE_THE_SYSTEM_IS = Path(__file__).resolve().parent.parent / "src" / "aisdlc"

# Names that appear in an annotation and are not a class this repository wrote. `None` is
# `NoneType` spelled the way people write it, and `Annotated` is the typing construct rather than
# anything a checkpoint has to import by name.
NOT_A_CLASS_THIS_REPOSITORY_WROTE = {
    "None",
    "NoneType",
    "Annotated",
    "list",
    "dict",
    "set",
    "tuple",
    "operator",
    "add",
}


def every_class_this_repository_defines() -> set[str]:
    """Every class name defined under `src/aisdlc`, read off the syntax tree.

    **Read and not imported, and the reason is the one this file exists for.** A list built by
    importing has to work before anything else does, so it fails in exactly the situation where
    the list is needed — a checkpoint that cannot rebuild its own types, at the moment the process
    is least able to start.
    """
    return {
        a_node.name
        for a_file in sorted(WHERE_THE_SYSTEM_IS.rglob("*.py"))
        for a_node in ast.parse(a_file.read_text(encoding="utf-8")).body
        if isinstance(a_node, ast.ClassDef)
    }


def every_type_a_state_channel_holds() -> dict[str, set[str]]:
    """Every class name each channel can carry, read out of the annotations."""
    held: dict[str, set[str]] = {}

    for a_channel, its_type in AgentState.__annotations__.items():
        names: set[str] = set()
        _the_names_in(its_type, names)
        held[a_channel] = names

    return held


def _the_names_in(the_type: object, into: set[str]) -> None:
    """Add every class name reachable from one annotation, however deeply nested."""
    if the_type is None or the_type is type(None):
        return

    if isinstance(the_type, typing.ForwardRef):
        _the_names_in(the_type.__forward_arg__, into)
        return

    if isinstance(the_type, str):
        into.update(
            name
            for name in _the_identifiers_in(the_type)
            if name not in NOT_A_CLASS_THIS_REPOSITORY_WROTE
        )
        return

    for an_argument in typing.get_args(the_type):
        _the_names_in(an_argument, into)

    name = getattr(the_type, "__name__", None)
    if name is not None and name not in NOT_A_CLASS_THIS_REPOSITORY_WROTE:
        into.add(name)


def _the_identifiers_in(written: str) -> list[str]:
    """The identifiers in a written annotation, and nothing else."""
    name = ""
    names: list[str] = []

    for a_character in written:
        if a_character.isalnum() or a_character == "_":
            name += a_character
            continue
        if name:
            names.append(name)
        name = ""

    if name:
        names.append(name)

    return names


def test_every_type_a_state_channel_holds_is_named_for_the_serializer() -> None:
    """The rule, and it names the channel as well as the type.

    **The channel is in the message because the type alone is not enough to act on.** Thirty-one
    names on a list and a hundred-odd classes in the package means "this type is unnamed" is one
    of many sentences a reader could be handed; "this channel carries a type the serializer cannot
    read back" is one they can go and fix.
    """
    named = {getattr(a_type, "__name__", str(a_type)) for a_type in TYPES_A_CHECKPOINT_MAY_HOLD}
    this_repository_defines = every_class_this_repository_defines()

    not_named = {
        a_channel: sorted(
            a_name
            for a_name in a_names
            if a_name in this_repository_defines and a_name not in named
        )
        for a_channel, a_names in every_type_a_state_channel_holds().items()
    }
    unnamed = {a_channel: names for a_channel, names in not_named.items() if names}

    assert unnamed == {}, (
        f"these state channels carry a type of this repository that the checkpoint serializer is "
        f"not allowed to rebuild: {unnamed}. A type left off the allowlist stops being readable "
        "from a checkpoint, and the day the runtime enforces that a run whose state was written "
        "to disk cannot be resumed. The names live in TYPES_A_CHECKPOINT_MAY_HOLD in "
        "src/aisdlc/graph/lifecycle.py"
    )


def test_the_guard_reads_annotations_and_not_only_the_first_level() -> None:
    """The two reducing channels are `Annotated[list[...], operator.add]`, and both hide a type.

    **This is the guard agreeing with itself about its own blindness.** If `_the_names_in` read
    one level it would see `Annotated` for `decisions` and `approvals` and find no class there,
    and the test above would pass on two channels it had not actually looked inside. So the two
    element types are named here explicitly: they are in the state, and a guard that cannot see
    them is a guard over part of the type.
    """
    names_in_the_reducing_channels = every_type_a_state_channel_holds()

    assert "ApprovalDecision" in names_in_the_reducing_channels["decisions"], (
        "the decisions channel carries a list of ApprovalDecision and the guard cannot see it: "
        f"{sorted(names_in_the_reducing_channels['decisions'])}"
    )
    assert "Approval" in names_in_the_reducing_channels["approvals"], (
        "the approvals channel carries a list of Approval and the guard cannot see it: "
        f"{sorted(names_in_the_reducing_channels['approvals'])}"
    )


def test_the_allowlist_holds_classes_and_not_module_prefixes() -> None:
    """Both claims the comment in `lifecycle.py` makes about this list are checked here.

    **A bare `"aisdlc."` prefix is the same promise with none of the checking**, the comment
    says, and a permissive serializer is no promise at all. Asserting that every entry is a real
    class is what makes the first half true rather than intended — a list of module prefixes
    would satisfy a reader and stop nothing.
    """
    all_classes = all(isinstance(a_type, type) for a_type in TYPES_A_CHECKPOINT_MAY_HOLD)

    assert all_classes, (
        f"TYPES_A_CHECKPOINT_MAY_HOLD holds {TYPES_A_CHECKPOINT_MAY_HOLD!r} and at least one entry "
        "is not a class. A string in that list is a claim with none of the checking, which is "
        "exactly what the comment above it says it is not"
    )


def test_the_file_this_comment_refers_to_is_this_one() -> None:
    """A comment that names a guard which does not exist is how a reader spends an hour.

    **`lifecycle.py` refers to this test by name, and the name is load-bearing.** Renaming this
    file would leave the reference in the source quietly meaning nothing — which is how the
    situation this file exists to prevent came about in the first place: the comment was written
    first, and the test it promised was never written.
    """
    where_this_file_is = Path(__file__).resolve()

    assert where_this_file_is.stem == (
        "test_every_type_a_state_channel_holds_is_named_for_the_serializer"
    ), (
        f"this file is {where_this_file_is.name!r} and src/aisdlc/graph/lifecycle.py refers to "
        "test_every_type_a_state_channel_holds_is_named_for_the_serializer by name. Rename one "
        "and the other becomes a comment about a test that does not exist, which is the failure "
        "this file is here because it already happened once"
    )
