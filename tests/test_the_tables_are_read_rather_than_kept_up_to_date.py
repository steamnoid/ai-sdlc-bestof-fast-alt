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

**The agents are read out of the production model and not written out.** `TheAgentsThisRun` is
the one place that says which collaborators a run is given, so a stage wired into a pipeline and
a stage proved alone are compared by construction. A list typed into this file would be a fourth
place to forget a stage, and the thing being guarded is a section that forgot one.
"""

from __future__ import annotations

import re
from pathlib import Path

from aisdlc.graph.the_agents_this_run import TheAgentsThisRun

THE_README = Path(__file__).resolve().parent.parent / "README.md"
THE_TESTS = Path(__file__).resolve().parent
THE_REAL_TIER = THE_TESTS / "e2e"


def _the_test_files_in(the_tier: Path) -> set[str]:
    return {a_file.name for a_file in the_tier.rglob("test_*.py") if a_file.is_file()}


THE_STAGE_A_RUN_WALKS_AND_THE_MODULE_THAT_IS_IT = {
    "discover_the_repository",
    "analyze_the_repository",
    "analyze_the_requirements",
    "analyze_the_architecture",
    "inspect_for_security_risk",
    "plan_the_change",
    "implement_the_plan",
    "supervise_a_repair",
    "brief_this_repository",
    "propose_the_work_this_repository_shows",
    "review_an_artifact",
    "open_the_delivery",
}
"""Every stage of a run, named as the production module that is the stage.

**The module name and not the field name of `TheAgentsThisRun`, and the two are deliberately
different.** `propose_requirements` is what the product analyst is *asked for* — §10's question
for that discipline — and `analyze_the_repository` is the module implementing it. A guard
matching file names against field names would fail on that difference and be quietly loosened
until it passed, which is how a guard stops guarding. So the stages are named as modules here,
and the count is cross-checked against the production model so a stage added there cannot be
added here without being noticed.
"""


def test_every_stage_a_run_walks_has_a_file_that_proves_it_alone() -> None:
    """Every stage listed above is proven alone by a file of the real tier named after it.

    **The file is named after the stage rather than counted, and the naming is the check.** A
    tier that grew a dozen files and proved nothing would satisfy a count. A file whose name
    mentions a stage is a file that says what it is about, so a name matching none of them is
    the case worth refusing — and a reader arriving at that file learns from its name alone.

    **The count is checked against production, so this list cannot quietly fall behind.** A
    collaborator added to `TheAgentsThisRun` changes the number of fields, and this is where
    that becomes a failure rather than a note in a document nobody diffs.
    """
    the_files = _the_test_files_in(THE_REAL_TIER)
    assert the_files, (
        f"{THE_REAL_TIER} holds no test file, so this is comparing an empty set against the "
        "stages a run walks and would pass forever"
    )

    not_proven_alone = sorted(
        a_stage
        for a_stage in THE_STAGE_A_RUN_WALKS_AND_THE_MODULE_THAT_IS_IT
        if not any(a_stage in a_file for a_file in the_files)
    )

    assert not not_proven_alone, (
        f"{not_proven_alone} are stages a run walks, and no file in {THE_REAL_TIER.name}/ is "
        "named after one of them. A stage wired into a pipeline with nothing proving it alone "
        "is a stage that can stop working and fail silently, because the run carries on to the "
        "next gate either way — which is the whole reason this tier exists, and the reason a "
        "README may not say these contracts are unprovable here."
    )

    how_many_collaborators_a_run_is_handed = len(TheAgentsThisRun.model_fields)
    assert how_many_collaborators_a_run_is_handed == 8, (
        f"{TheAgentsThisRun.__name__} now hands a run {how_many_collaborators_a_run_is_handed} "
        f"collaborators and it used to hand it 8. This file names the stages a run walks, so a "
        "collaborator added there has to be added here and given a file of its own — otherwise "
        "the new stage is the one nothing proves alone, which is the gap this repository is "
        f"closing. The collaborators are {sorted(TheAgentsThisRun.model_fields)}."
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
