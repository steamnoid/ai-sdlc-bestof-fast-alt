"""The README's own claims about what is not built here, checked rather than trusted.

**The table of test files was the second guard for a stale claim, and this is the guard for
the section around it.** That section used to say the per-agent contracts could only be proven
in `ai-sdlc-os`, and four days after a tier that proves them landed it was still saying so —
because the guard beside it checks *names*, and a section that is entirely true about ten file
names can be entirely false about everything else it says.

**What is checked is mechanical, and no sentence in the README is.** The first version of this
file asserted that the phrase `could only be proven in ai-sdlc-os` is absent from the section —
and it failed on a paragraph recording that the section *used to* say it, which is the honest
way to write down a reversal. A check that cannot tell a claim from a record of a withdrawn
claim fires on the correct fix, so a reader learns to route around it, and a guard that is
routed around is the same hole with a green tick in it.

So the claim is not a phrase. **The claim is the tier: every collaborator a run is handed has a
file in `tests/e2e/` that proves it alone.** If that holds, a sentence denying it is wrong, and
if a sentence denying it survives, the tier is missing something and that is the finding worth
a failure. The prose is left to a reader, and the quantity it would have been checked against is
checked here.

**The stages are read out of the production code and not written out.** Which modules in
`agents/` take a model is a fact about the source, so it is computed from the source. A list
typed into this file would be a fourth place to forget a stage, and the thing being guarded is a
section that forgot one — twice, in the two ways a count can be right and the prose beside it
wrong.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

THE_README = Path(__file__).resolve().parent.parent / "README.md"
THE_TESTS = Path(__file__).resolve().parent
THE_REAL_TIER = THE_TESTS / "e2e"


def _the_test_files_in(the_tier: Path) -> set[str]:
    return {a_file.name for a_file in the_tier.rglob("test_*.py") if a_file.is_file()}


def _the_stages_that_ask_a_model() -> set[str]:
    """Every module in `agents/` that takes a model, read out of the production code.

    **Computed and not written out, which is the whole point of this file.** The first version
    of this test held a list of twelve stage names, and the list was wrong twice before it was
    checked against anything: it named a stage whose file is called `test_discovery.py` and
    reported it unproven when it was proven and sitting on disk, and it demanded a real-model
    test for the delivery node — which asks no model at all, and whose real-model question does
    not exist. A list is a fourth place to forget a stage, and a wrong list is worse than none
    because it fails on correct code and a reader stops reading it.

    **A function whose signature takes a model is the claim, read from the signature.** A module
    whose public function is handed a `BaseChatModel` is a stage that reasons, and §0.4's "an
    agent is not implemented until it has been observed producing validated output" is about
    those and only those. A stage that pushes a branch asks no model and is covered by the whole
    run, which is where a push belongs.
    """
    the_agents = Path(__file__).resolve().parent.parent / "src" / "aisdlc" / "agents"

    asking_a_model = set()
    for a_module in sorted(the_agents.glob("*.py")):
        for a_definition in ast.parse(a_module.read_text()).body:
            if not isinstance(a_definition, ast.FunctionDef):
                continue
            arguments = [
                an_argument.arg
                for an_argument in [*a_definition.args.args, *a_definition.args.kwonlyargs]
            ]
            if "model" in arguments or "the_model" in arguments:
                asking_a_model.add(a_module.stem)
                break

    return asking_a_model


def test_every_stage_that_asks_a_model_has_a_file_that_proves_it_alone() -> None:
    """Every module in `agents/` that takes a model is proven alone by a file of the real tier.

    **The file is named after the stage rather than counted, and the naming is the check.** A
    tier that grew a dozen files and proved nothing would satisfy a count. A file whose name
    mentions a stage is a file that says what it is about, so a name matching none of them is
    the case worth refusing — and a reader arriving at that file learns from its name alone.

    **`discover_the_repository` is matched on `discover`, and the exception is written down.**
    A production module is named after what it does and a test file after what a reader calls
    the thing, and for this one stage those differ. The alternative is a rename in one direction
    or the other, and a rename is a bigger change than naming the difference.
    """
    the_files = _the_test_files_in(THE_REAL_TIER)
    assert the_files, (
        f"{THE_REAL_TIER} holds no test file, so this is comparing an empty set against the "
        "stages that ask a model and would pass forever"
    )

    the_word_a_file_is_named_after = {"discover_the_repository": "discover"}

    the_stages = _the_stages_that_ask_a_model()
    assert the_stages, (
        "no module in src/aisdlc/agents/ takes a model, which means this system has no reasoning "
        "stage and this file is guarding a thing that does not exist"
    )

    not_proven_alone = sorted(
        a_stage
        for a_stage in the_stages
        if not any(
            the_word_a_file_is_named_after.get(a_stage, a_stage) in a_file for a_file in the_files
        )
    )

    assert not not_proven_alone, (
        f"{not_proven_alone} ask a model, and no file in {THE_REAL_TIER.name}/ is named after "
        "one of them. A stage wired into a pipeline with nothing proving it alone is a stage "
        "that can stop working and fail silently, because the run carries on to the next gate "
        "either way — which is the whole reason this tier exists, and the reason a README may "
        "not say these contracts are unprovable here."
    )


def test_both_tables_name_every_file_between_them() -> None:
    """The default suite and the real tier together name every test file, and name no other.

    **Both directories, and the union rather than either one.** The original guard read
    `tests/*.py` and could not see a tier in a subdirectory at all, so a whole tier landed
    undocumented with it green. Reading both tables rather than one is the same lesson applied
    a second time: the claim is about what a reader can find, and a reader follows the README
    to both places.
    """
    what_the_readme_says = THE_README.read_text(encoding="utf-8")
    the_files_the_readme_names = set(re.findall(r"`(test_[a-z0-9_]+\.py)`", what_the_readme_says))
    every_test_file = _the_test_files_in(THE_TESTS)

    undocumented = every_test_file - the_files_the_readme_names
    assert not undocumented, (
        f"{sorted(undocumented)} exist and the README does not say what they hold this "
        "repository to. Both tables are read here, so a file missing from either one is this "
        "test failing"
    )

    gone = the_files_the_readme_names - every_test_file
    assert not gone, (
        f"the README names {sorted(gone)} and there is no such file, so a reader is sent to "
        "look for something that is not there"
    )
