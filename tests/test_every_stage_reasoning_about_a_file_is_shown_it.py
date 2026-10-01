"""Every stage that reasons about what a file *contains* is shown the file's contents.

**A real run found this, in a different repository, and the fix was made where the bug was found
rather than where the rule is.** A run's policy refused its own requirements with this:

> The artifact itself records that neither `src/aisdlc/tools/run_command.py` nor
> `src/aisdlc/agents/inspect_for_security_risk.py` had its contents in the inspection, yet
> requirements 3, 4, 6 and 7 state what those files catch, where the boundary is enforced, and
> that nothing escapes the project directory.

**A model wrote four requirements about two files nobody in that stage had read.** Discovery,
the security analyst and the briefing were handed `an_inspection_of_the_code` — the one carrying
file contents and naming what it left out — while the product analyst, the architecture analyst
and the planner were handed `an_inspection_of`: a directory listing, the manifests, a README and
the CI configuration. The fix had been made for discovery. Nobody checked the stages after it.

**So a product analyst reasons about what a repository lacks from its shape.** That is not a
small gap: §10 gives the product analyst `analyze requirements` and the glossary has it
answering for what should be built, and the shape of a repository is a poor guide to what is
missing from it. A `Dockerfile` carries **no extension**, and the source-suffix filter used to
exclude exactly the files that carry none — so for this repository a `Dockerfile` and a
`Makefile` were invisible to every stage in this system, and a real gate refused a security
report for reasoning from one.

**The list is derived from the production code, not written here**, for the reason this file
exists. A test holding a list of module names is a fourth place to forget a stage, and this
repository has had that shape of guard go green while a whole tier was undocumented. So the
stages are found by reading every module in `agents/` that takes a `model` and looking at which
inspection it calls — and a new stage is covered the day it is written rather than the day
somebody remembers this file.

**Parsed rather than imported, because a double could answer either way.** The claim is about
what the production code calls. A test that replaced the inspection could only prove that the
replacement was used, and a guard satisfied by a comment is the third of those this repository
has now had.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

THE_AGENTS = Path(__file__).resolve().parent.parent / "src" / "aisdlc" / "agents"

AN_INSPECTION_THAT_CARRIES_FILE_CONTENTS = "an_inspection_of_the_code"
"""The inspection that shows a model what is *inside* the files, and names what it left out.

Chosen over `an_inspection_of` for every stage that reasons about contents, and the reason is in
`inspect_the_repository`: the shape-only inspection's own note says source files are deliberately
absent from it, which is right for a summary of a repository and wrong for anything reasoning
about what a file does.
"""


def _the_stages_that_read_a_repository() -> dict[str, str | None]:
    """Every stage that asks a model, with the inspection it hands that model — and nothing for
    a stage that is never shown a repository at all.

    **A stage is only in scope if it is handed a clone, and that is what keeps this rule from
    being a rule about everything.** There are two kinds of stage this file must not confuse:

    * one that reads a repository for itself — discovery, the security analyst, the briefing,
      the product analyst, the architect, the planner. These choose what a model sees, and a
      listing where the code was wanted is the defect below.
    * one that reasons over a *document* — the QA analyst, handed approved `Requirements`; the
      policy at a gate, handed one artifact; the proposer, handed one report. **These are
      shown nothing from the repository on purpose.** §10 gives the QA analyst
      `analyze requirements` and its own prompt says so out loud, telling the model that
      anything it says about a file by name is a guess. Handing one an inspection would make its
      scenarios true about exactly one repository, which is the one nobody here has seen.

    And a third kind is neither: the implementer and the stage that runs the suite around it.
    Both are handed a clone and a model, and both reach file contents by a *different* road —
    the implementer reads exactly the files an approved plan named, and every one of them was
    already refused by `plan_the_change` if it was not a file of the clone. **A stage that reads
    the files its own plan names is not a stage that needs an inspection**, and a rule that
    demanded one of it would be a rule pushing a 46,000-character question at a stage whose
    whole job is to write one file.
    """
    every_stage: dict[str, str | None] = {}

    for a_module_path in sorted(THE_AGENTS.glob("*.py")):
        the_source = a_module_path.read_text()
        the_tree = ast.parse(the_source)

        for a_definition in the_tree.body:
            if not isinstance(a_definition, ast.FunctionDef):
                continue
            if a_definition.name.startswith("_"):
                continue
            arguments = [an_argument.arg for an_argument in a_definition.args.args]
            if "model" not in arguments and "the_model" not in arguments:
                continue

            if "clone" not in arguments:
                continue

            # A stage that reads the files a plan named reads them itself, and the plan's own
            # refusals are what makes those reads safe. It is not choosing what a model is shown
            # over a whole repository, so an inspection is not its missing half.
            if "plan" in arguments:
                continue

            the_calls = [
                a_call.func.id
                for a_call in ast.walk(the_tree)
                if isinstance(a_call, ast.Call) and isinstance(a_call.func, ast.Name)
            ]
            the_inspections = [
                a_name for a_name in the_calls if a_name.startswith("an_inspection_of")
            ]
            every_stage[a_module_path.stem] = the_inspections[0] if the_inspections else None
            break

    return every_stage


def _the_inspection_a_stage_hands_its_model(a_stage: str) -> str | None:
    """The inspection function this stage calls, read from its own source by parsing it.

    **Parsed and not imported, because a double could answer either way.** The claim is about the
    call the production code makes; substituting the inspection would only prove the substitute
    was used.
    """
    importlib.import_module(f"aisdlc.agents.{a_stage}")
    the_source = (THE_AGENTS / f"{a_stage}.py").read_text(encoding="utf-8")

    the_calls = [
        a_call.func.id
        for a_call in ast.walk(ast.parse(the_source))
        if isinstance(a_call, ast.Call) and isinstance(a_call.func, ast.Name)
    ]
    the_inspections = [a_name for a_name in the_calls if a_name.startswith("an_inspection_of")]

    assert len(the_inspections) <= 1, (
        f"{a_stage} calls {the_inspections}, so there is no single inspection to check and a "
        "reader has to work out which one the model is actually given"
    )
    return the_inspections[0] if the_inspections else None


def test_there_is_a_stage_reading_a_repository_for_this_rule_to_apply_to() -> None:
    """The set is not empty, or every assertion below is a comparison with nothing.

    A guard over an empty set is the shape this repository has been bitten by three times: a
    README table, a count, and a `glob` that could not see a directory. The claim has to be about
    stages that exist, and it has to be about the right ones.
    """
    the_stages = _the_stages_that_read_a_repository()

    assert the_stages, (
        f"no module in {THE_AGENTS} is handed both a clone and a model, so this file is checking "
        "a rule against nothing and would pass forever"
    )

    a_stage_that_looks_at_a_repository = [
        a_stage for a_stage in the_stages if (THE_AGENTS / f"{a_stage}.py").is_file()
    ]
    assert len(a_stage_that_looks_at_a_repository) >= 6, (
        f"only {len(a_stage_that_looks_at_a_repository)} stages are handed a clone and a model, "
        f"and a rule over that few is not the rule this file states. They are "
        f"{sorted(a_stage_that_looks_at_a_repository)}"
    )


@pytest.mark.parametrize("a_stage", sorted(_the_stages_that_read_a_repository()))
def test_every_stage_that_reads_a_repository_is_shown_what_is_inside_it(a_stage: str) -> None:
    """No stage is handed a listing and asked what the files in it do.

    **The whole set, in one assertion, and the message names each offender.** Three stages in
    this repository are handed `an_inspection_of` today, and each of them will write findings
    about files nobody in that stage has read — which is what the refusal above was, and what a
    policy reading an artifact against its own evidence list catches. A policy caught it. No test
    asked.
    """
    the_inspection = _the_inspection_a_stage_hands_its_model(a_stage)

    assert the_inspection == AN_INSPECTION_THAT_CARRIES_FILE_CONTENTS, (
        f"{a_stage} hands its model {the_inspection or 'no inspection at all'}, which does not "
        f"show what is inside the files. A stage given a listing will write findings about files "
        "nobody in it has read, and a person reading a gate cannot tell — a security report that "
        "reasons from a `Dockerfile` looks exactly like one that reasoned from what is in it. "
        f"Use {AN_INSPECTION_THAT_CARRIES_FILE_CONTENTS}, which carries the code and names what it "
        "left out, so a finding about a file that was not shown is visibly a finding about nothing."
    )
