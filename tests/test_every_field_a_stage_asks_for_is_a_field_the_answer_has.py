"""Every judgement a stage is asked to name is a field it has, and one of them had a typo.

**The planner's prompt asks the model for `what_it_expectes_next` and no such field exists.**
Four of the five stages that reason about a repository ask for the same three judgements and
spell the third correctly; the planner asks for a field with a transposed pair of letters, and
the schema the model is then held to — `WhatAnAgentJudged` — does not have it.

**So the model is asked for two things at once that disagree.** The tool's schema names
`what_it_expects_next` and the prose inside the prompt names `what_it_expectes_next`, and a
model that obeys the prose returns a key the schema does not declare. The forced tool call
`ask_a_model_for` hands binds, so the answer is data rather than an artifact until it
validates — and a key the type does not declare is a `ValidationError` under
`extra="forbid"`, or a silently dropped field, depending on which shape the provider returns.
**Either way the third judgement is the one at risk, and it is the one a person reads on a
card to learn what the planner concluded.**

**Why it survived every test in this repository.** It is a prompt string. A prompt is not
covered by a type, so nothing complained: the artefact type is right, the node's repair loop
is right, and a real run's plan was still produced — because this deployment's model
apparently follows the schema over the prose. **That is luck, not correctness**, and it is
why the rule is asserted over the whole set rather than over the one field: four correct
spellings and one wrong is a finding a reader would otherwise have to diff five constants to
see.

**The check is a set difference, so a stage that renames a field is caught too.** Asking
"is the planner's list right" would pass the moment somebody corrected the typo and would keep
passing if the schema changed under it. Asking "does every stage ask only for fields the type
has" is a property of the pair, and both halves moving is the case worth failing on.
"""

from __future__ import annotations

from types import ModuleType

import pytest

from aisdlc.agents.what_an_agent_judged import WhatAnAgentJudged

THE_JUDGEMENTS_EVERY_AGENT_MAY_NAME = (
    "what_it_found",
    "what_it_could_not_settle",
    "what_it_expects_next",
)
"""Spelled here once, correctly, and the whole of this file is that every stage agrees.

Written out rather than imported from one of the stages, because importing the planner's would
make this test agree with whatever the planner says — which is the defect, restated as the
oracle.
"""

A_STAGE_THAT_REASONS_ABOUT_A_REPOSITORY = (
    "aisdlc.agents.discover_the_repository",
    "aisdlc.agents.analyze_the_repository",
    "aisdlc.agents.analyze_the_requirements",
    "aisdlc.agents.analyze_the_architecture",
    "aisdlc.agents.plan_the_change",
)
"""The five stages that ask the same question, and the five constants that answer it.

Named by module path and imported, so a stage added to the pipeline is added here by name and
not by discovering it — and so this file fails with the stage's own name in the message rather
than with an index.
"""


def _the_judgements_a_stage_asks_its_model_for(a_module_path: str) -> tuple[str, ...]:
    """The constant that stage's prompt names, whatever the stage chose to call it.

    **Found by meaning rather than by name, because the name is not uniform** and normalising it
    would be a rename in five places to make a check shorter. A stage that renamed its constant
    would still be caught here, and that is the point: a test that had to know the name in
    advance would pass vacuously on a stage that stopped using it.
    """
    import importlib

    a_module: ModuleType = importlib.import_module(a_module_path)

    for a_name, a_value in vars(a_module).items():
        if a_name.startswith("THE_JUDGEMENTS") and isinstance(a_value, tuple):
            return a_value

    raise AssertionError(
        f"{a_module_path} has no constant naming the judgements it asks its model for, so this "
        "test cannot check that they are the ones the artefact has — and a stage whose question "
        "stopped asking is a stage whose card stopped carrying a note"
    )


@pytest.mark.parametrize("a_stage", A_STAGE_THAT_REASONS_ABOUT_A_REPOSITORY)
def test_every_field_a_stage_asks_its_model_for_is_a_field_the_answer_has(a_stage: str) -> None:
    """The prose inside a stage's question and the schema it is held to name the same fields.

    **The failure is a field name and nothing else**, because that is what the mismatch is: a
    model told to answer `what_it_expectes_next` and bound to a schema with
    `what_it_expects_next` is in two arguments at once, and the third judgement is the one that
    gets lost — it is the one a person reads to learn what the stage concluded.
    """
    what_the_stage_asks_for = _the_judgements_a_stage_asks_its_model_for(a_stage)
    what_the_answer_has = tuple(WhatAnAgentJudged.model_fields)

    asked_for_but_not_answered = [
        a_field for a_field in what_the_stage_asks_for if a_field not in what_the_answer_has
    ]

    assert not asked_for_but_not_answered, (
        f"{a_stage} asks its model for {asked_for_but_not_answered}, and "
        f"`{WhatAnAgentJudged.__name__}` has {list(what_the_answer_has)}. The prose inside the "
        "prompt and the tool schema the model is bound to disagree, so a model that obeys the "
        'prose returns a key the schema does not declare — and with `extra="forbid"` that is a '
        "ValidationError consuming a correction, or a dropped field, depending on the provider. "
        "This is a prompt string, which is why no type in this system complained: a prompt is not "
        "covered by a type, and a real run got through on a model that happened to follow the "
        "schema over the prose."
    )


def test_a_stage_may_not_ask_for_fewer_judgements_than_the_answer_carries() -> None:
    """The other direction, and it is the one a typo in a removal would cause.

    A stage that asked for two of the three would leave the third carrying the type's default
    — and a default is a sentence nobody wrote, which on a card reads as a judgement. So the
    set is compared both ways, and a stage that adds a field to the artefact and forgets this
    constant fails here.
    """
    asked_for_but_never = [
        a_field
        for a_field in WhatAnAgentJudged.model_fields
        if a_field not in THE_JUDGEMENTS_EVERY_AGENT_MAY_NAME
    ]

    assert not asked_for_but_never, (
        f"`{WhatAnAgentJudged.__name__}` carries {asked_for_but_never}, and this file — which is "
        "the oracle every stage's constant is compared against — does not know about them. A "
        "judgement this file cannot name is a judgement a stage could be asked for by accident "
        "and leave at its default, and a default is a sentence nobody wrote"
    )
