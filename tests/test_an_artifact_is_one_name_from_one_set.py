"""That an artifact this pipeline presents is a name from one closed set, and not eight strings.

**Eight modules each declared one of these names, and the router imported all eight to spell the
same eight strings a third time.** That is one concept with nine names, which is what the domain
rules forbid outright — and it is not a style complaint, because the whole of the router's safety
property is *an artifact that is not in its mapping cannot be routed at all*, and a property that
rests on eight separately-typed strings is a property nothing checks.

**`THE_ARTIFACT_A_RUN_BEGINS_WITH = "DiscoveryReport"` was declared twice, in two modules**, which
is the same fact written in two places where one of them could have been changed without the other.
**One of the two is the only one a resumed run reads**, so a person renaming the artifact would
have changed what a fresh run presents and left what a resumed run presents alone.

**A closed set is what makes a typo a compile error rather than a run that dies at a gate.** The
state is a `TypedDict`, so it is not validated when a node writes it — nothing at runtime would have
refused `"DiscoveryRepotr"`. What refuses it is the *type*, which `mypy` reads on every push: a
module that writes a name the set does not have does not compile. **This is the difference between
a failure at the gate and a failure before the run started**, and it is the whole argument for a
domain type over a `str`.

**But the enum does not carry the pipeline, and the router's mapping is what does.** A member
added to the set with no route would be an artifact a run can produce and nobody can route — so
`test_every_artifact_a_run_can_present_has_exactly_one_route` is the assertion that keeps the two
in step, and it is the one that would have caught a ninth name appearing in a node with nowhere to
go.

**Parsed and not imported**, because a double could answer either way. Three of the four rules here
are about where a name is *written*, and the only thing that settles that is reading the sources.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from aisdlc.agents.artifact import Artifact

from aisdlc.graph.router import WHERE_AN_APPROVED_ARTIFACT_LEADS

WHERE_THE_PACKAGE_IS = Path(__file__).parent.parent / "src" / "aisdlc"

WHAT_THIS_PIPELINE_PRESENTS = frozenset(artifact.value for artifact in Artifact)


def _every_module_in_the_package() -> list[Path]:
    return sorted(path for path in WHERE_THE_PACKAGE_IS.rglob("*.py"))


def _the_artifact_names_a_module_assigns(a_module: Path) -> list[str]:
    """The artifact names a module *assigns*, not the ones its prose merely mentions.

    **Assignments only, and that is what keeps a docstring from looking like a declaration.** A
    module whose prose says *the gate presents `DiscoveryReport`* is not a second place the name
    lives — it is a place a reader looks. Reading every string in every file would report every
    explanation of the domain as a duplicate of it.
    """
    the_tree = ast.parse(a_module.read_text())
    what_is_assigned: list[str] = []

    for a_definition in the_tree.body:
        if not isinstance(a_definition, ast.Assign):
            continue
        for an_assigned_value in (
            a_definition.value.elts
            if isinstance(a_definition.value, ast.Tuple)
            else [a_definition.value]
        ):
            if isinstance(an_assigned_value, ast.Constant) and isinstance(
                an_assigned_value.value, str
            ):
                what_is_assigned.append(an_assigned_value.value)

    return what_is_assigned


def test_a_name_this_pipeline_does_not_produce_cannot_be_constructed() -> None:
    """A typo is a value error at the place that builds the name, and it names what does exist.

    **The message lists the eight, and that is the half that matters.** A refusal saying *that is
    not an artifact* leaves the writer to go and look; one listing the set turns a wrong guess into
    a right one inside the same sentence — which is the difference this whole cycle exists for.
    """
    with pytest.raises(ValueError) as it_raised:
        Artifact("DiscoveryRepotr")

    the_refusal = str(it_raised.value)

    for a_name in sorted(WHAT_THIS_PIPELINE_PRESENTS):
        assert a_name in the_refusal, (
            f"the refusal does not list {a_name!r}, so a writer who misspelled one name has to go "
            f"and find the set instead of being handed it: {the_refusal}"
        )


def test_one_artifact_is_named_in_one_module_and_nowhere_else() -> None:
    """Eight modules declared these names, and one of them declared the same name twice.

    **Every name in one module, and not merely no duplicates** — because the property that matters
    is that there is *somewhere* to look. A set of names spread across the nine nodes that produce
    them is at least consistent today; a set spread across a tenth module nobody reads is not.
    """
    where_each_name_lives: dict[str, list[str]] = {}

    for a_module in _every_module_in_the_package():
        for a_name in _the_artifact_names_a_module_assigns(a_module):
            if a_name not in WHAT_THIS_PIPELINE_PRESENTS:
                continue
            where_each_name_lives.setdefault(a_name, []).append(a_module.name)

    said_in_more_than_one_place = {
        a_name: where for a_name, where in where_each_name_lives.items() if len(where) > 1
    }

    assert not said_in_more_than_one_place, (
        f"{said_in_more_than_one_place} — one artifact named in more than one module. The router "
        "imports every one of them to spell the same string, so a name changed in one of these is "
        "a name the router will not recognise, and the run stops at a gate with a message about an "
        "artifact nobody presented"
    )

    assert set(where_each_name_lives) == WHAT_THIS_PIPELINE_PRESENTS, (
        f"the set is {sorted(WHAT_THIS_PIPELINE_PRESENTS)} and {sorted(where_each_name_lives)} is "
        "what the modules spell out, so an artifact exists that no module says the name of — and a "
        "name nothing spells is a name a gate cannot present"
    )


def test_the_router_spells_no_artifact_name_and_imports_no_node_to_learn_one() -> None:
    """The router learned the eight names from eight modules, and the mapping is the pipeline.

    **The import list is read rather than the source, because the import is the coupling.** A
    router that imports nine node modules to learn eight strings is nine modules whose names it
    cannot do without, and a node module that is not about routing is the wrong place for a name
    the router depends on. **A `KeyError` in that mapping at run time is a delivery that reached
    its last gate and stopped there**, which is the worst place a missing name can surface.
    """
    the_router = (WHERE_THE_PACKAGE_IS / "graph" / "router.py").read_text()
    the_tree = ast.parse(the_router)

    spelled_out_here = [
        a_node.value
        for a_node in ast.walk(the_tree)
        if isinstance(a_node, ast.Constant)
        and isinstance(a_node.value, str)
        and a_node.value in WHAT_THIS_PIPELINE_PRESENTS
    ]

    assert not spelled_out_here, (
        f"{spelled_out_here} spelled out inside the router. The router is the pipeline and"
        "holds no names of its own; a name it writes here is a second copy of a name a "
        "node already wrote"
    )

    what_it_imports_from_a_node = [
        a_node.module or "" for a_node in ast.walk(the_tree) if isinstance(a_node, ast.ImportFrom)
    ]

    assert not [module for module in what_it_imports_from_a_node if module.endswith("_node")], (
        f"{what_it_imports_from_a_node} — the router imports node modules. The nodes are named for "
        "what they produce, and the router's whole job is to say what each of those leads to, so "
        "the names belong in one place the two of them can both reach"
    )


def test_every_artifact_a_run_can_present_has_exactly_one_route() -> None:
    """A member added to the set with no route is an artifact a run produces and nobody can route.

    **Both directions, and the second is the one that catches work.** An artifact in the mapping
    that is not in the set is a route to nowhere, and a member in the set that is not in the
    mapping is a run that reaches a gate offering something the router has never heard of. **The
    router's own docstring says an artifact that is not there cannot be routed at all**, which is
    the safety property — and it is a property of two collections agreeing, so it is asserted here
    rather than assumed from the mapping looking complete.
    """
    what_can_be_routed = set(WHERE_AN_APPROVED_ARTIFACT_LEADS)
    what_can_be_presented = set(Artifact)

    what_can_be_routed = set(WHERE_AN_APPROVED_ARTIFACT_LEADS)
    what_can_be_presented = set(Artifact)

    assert what_can_be_presented - what_can_be_routed == set(), (
        f"{sorted(a.value for a in what_can_be_presented - what_can_be_routed)} can be presented "
        "and cannot be routed. A run that produced one would reach its gate and stop there, and "
        "the refusal would name an artifact the pipeline has a name for and no destination for"
    )

    assert what_can_be_routed - what_can_be_presented == set(), (
        f"{sorted(str(name) for name in what_can_be_routed - what_can_be_presented)} has a route "
        f"and no name, so the routing for it is unreachable. {sorted(a.value for a in Artifact)} "
        "is what this pipeline can present"
    )
