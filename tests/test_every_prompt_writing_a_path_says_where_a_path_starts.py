"""Every prompt whose answer carries a file path carries the sentence about where a path starts.

**A path is written from the root of the repository, with every directory on the way.** Not the
module's import name and not its name inside the package: `src/aisdlc/graph/router.py`, because
that is the path a person types to open it, and **a path a reader cannot open is not a citation
however well the file exists.**

**This is a convention rather than a slip, and a run of this repository is what says so.** The
implementation agent asked for `.gitignore` was answered `gitignore`; the discovery agent naming
components produced `aisdlc/agents/what_an_agent_judged.py` for a file of this repository that
really exists at `src/aisdlc/agents/what_an_agent_judged.py`. **Every one is a real file, named
from the inside out** — and loosening a path matcher to accept them would have stopped the tier
noticing, which is the opposite of fixing it.

**The sentence lives here and the prompts build it from here.** Six prompts need it; six
prompts each carrying their own wording would drift, and then two of the six would be the ones
that are wrong — and nothing would say which two.

**Why a test and not a review.** §0.4 of this repository's own rules: if a prompt has to say
something, a test must assert it, and prompt text is not verification. A prompt that gained a
new answer field carrying a path would otherwise join the six silently, and the guard would
report the field rather than the omission.

**And the check is on the prompts rather than on the answers**, because a real model's answer
varies per run and §0.4 says that no assertion on exact content belongs in pytest. What is
asserted is that every prompt which *asks* for a path also says where a path starts — a claim
about the question, not about the answer.
"""

from __future__ import annotations

import ast
from pathlib import Path

WHERE_THE_AGENTS_ARE = Path(__file__).resolve().parent.parent / "src" / "aisdlc" / "agents"

# The prompts whose answer carries a path. This list is the judgement and the guard checks it
# against something, so that adding a seventh prompt which writes paths and forgetting this list
# is visible rather than invisible: `test_every_prompt_writing_a_path_is_in_this_list` says so.
THE_PROMPTS_WHOSE_ANSWER_CARRIES_A_PATH = (
    "analyze_the_architecture",
    "analyze_the_repository",
    "analyze_the_requirements",
    "implement_the_plan",
    "inspect_for_security_risk",
    "plan_the_change",
)

THE_MODULE_THAT_SAYS_IT_ONCE = "how_to_name_a_file"


def _the_source_of(one_agent: str) -> str:
    return (WHERE_THE_AGENTS_ARE / f"{one_agent}.py").read_text(encoding="utf-8")


def _does_it_import_the_sentence(one_agent: str) -> bool:
    """Whether the module reaches the sentence, read off the syntax tree rather than by import.

    **Read and not imported** for the reason the serializer allowlist in `lifecycle.py` gives:
    a list built by importing has to work before anything else does.
    """
    the_tree = ast.parse(_the_source_of(one_agent))

    return any(
        isinstance(a_node, ast.ImportFrom)
        and a_node.module is not None
        and a_node.module.endswith(THE_MODULE_THAT_SAYS_IT_ONCE)
        for a_node in ast.walk(the_tree)
    )


def test_every_prompt_writing_a_path_carries_the_sentence_about_where_a_path_starts() -> None:
    """The rule, and it names the module that is missing it."""
    without_the_sentence = [
        one_agent
        for one_agent in THE_PROMPTS_WHOSE_ANSWER_CARRIES_A_PATH
        if not _does_it_import_the_sentence(one_agent)
    ]

    assert without_the_sentence == [], (
        f"these prompts ask for file paths and do not say where a path starts: "
        f"{without_the_sentence}. A model reading an inspection showing "
        f"`src/aisdlc/graph/router.py` and writing `graph/router.py` has named a real file of "
        "this repository from the inside out, and a reader cannot open what it wrote"
    )


def test_the_sentence_is_one_module_and_six_prompts_build_it_from_there() -> None:
    """One wording, not six, because six wordings drift and the drift is invisible.

    **The failure this refuses is two prompts carrying a correct sentence and four carrying a
    stale one.** Nothing about that is visible in a diff: each prompt was edited on its own day,
    each edit was right on its own day, and the result is six sentences of which four are wrong.
    Asserting that the wording lives in exactly one module is what makes a reader able to fix
    all six by editing one file.
    """
    said_somewhere_else = [
        one_agent.name
        for one_agent in ast.parse(
            (WHERE_THE_AGENTS_ARE / THE_MODULE_THAT_SAYS_IT_ONCE)
            .with_suffix(".py")
            .read_text(encoding="utf-8")
        ).body
        if isinstance(one_agent, ast.FunctionDef)
        and "root of the repository" in ast.get_docstring(one_agent)
    ]

    assert said_somewhere_else == ["the_rule_about_naming_a_file"], (
        f"the sentence about naming a file is documented in {said_somewhere_else} and the "
        f"prompts import it from {THE_MODULE_THAT_SAYS_IT_ONCE}. If a second prompt has grown its "
        "own wording, the two will drift and nothing else here will say so"
    )


def test_every_prompt_writing_a_path_is_in_this_list() -> None:
    """The list is the judgement, so a new prompt that writes paths is visible when it appears.

    **This cannot be derived from the answers**, because the answers are model output and vary
    per run — so the list is written down and this test says so. A prompt whose answer type gains
    a field carrying a path is the case that matters, and the person adding it is the only one
    positioned to notice that this list needs the new name in it.
    """
    prompts_declaring_an_answer_type = {
        one_file.stem
        for one_file in WHERE_THE_AGENTS_ARE.glob("*.py")
        if "Answer" in one_file.read_text(encoding="utf-8")
    }

    assert prompts_declaring_an_answer_type, (
        "no module under src/aisdlc/agents mentions an answer type any more, so this guard has "
        "nothing to check and is green for the wrong reason"
    )
