"""A plan that adds a file is a plan, and its own emptiness rule did not think so.

**`files_to_add` was added to the artifact for a real run and the guard that reads the artifact
was never updated.** The comment beside the field list says the second list answers a different
question from the first and the third: `files_to_change` is what exists and is modified in
place, `files_to_add` is what the change brings into being, and `tests_to_add` are tests that
do not exist yet. Three lists, three questions, written down.

`ImplementationPlan.everything_it_says()` returns two of the three. So a plan whose entire
content is a new file — **the ordinary shape of "add an endpoint"** — raises `EmptyPlanError`,
with a message that names four things the plan did not do wrong. The message is the worst part:
it tells a reader *"returned a plan that names no file to change, no test to add, no dependency
and no migration"*, which is a list of the four ways a plan can be empty and which a reader
checks one by one, never finding the one that was actually named. **A refusal that names the
wrong thing is worse than no refusal**, because it sends whoever reads it looking in the four
wrong places.

**And the prompt says something the guard contradicts.** The planner's own question ends *"Name
something in at least one of these four lists"* — while the artifact beside it has five fields
and the guard reads four. So the model is asked for a thing the validator then refuses, and a
model that answers correctly loses a correction from a budget meant for wrong answers.

**The finding came from the real tier, and specifically from a check written there.** A plan
naming a file that already exists is refused by `PlannedFileToAddFoundError`, a plan naming a
file that is not there is refused by `PlannedFileNotFoundError` — and the path between those two
answers, where the file is new and correct, is a path the emptiness rule closed.
"""

from __future__ import annotations

import pytest

from aisdlc.agents.implementation_plan import EmptyPlanError, ImplementationPlan

A_FILE_THE_CHANGE_BRINGS_INTO_BEING = "src/api/health.ts"
"""The whole of a plan, and the shape of the request that produced this finding: *add an
endpoint*. A repository has no such route, so the plan is one new file and nothing else — and
that is a complete plan, not an empty one."""


def test_a_plan_whose_whole_change_is_a_new_file_is_a_plan() -> None:
    """A plan naming one new file and nothing else is the plan a person can approve.

    **One field, and no stand-in in the other four.** A test that gave the plan a
    `dependencies` entry as well would pass on code that reads only two of the three lists,
    because the plan would then be non-empty either way — which is exactly the shape of a
    guard that cannot fail.
    """
    a_plan = ImplementationPlan(files_to_add=[A_FILE_THE_CHANGE_BRINGS_INTO_BEING])

    assert a_plan.files_to_add == [A_FILE_THE_CHANGE_BRINGS_INTO_BEING], (
        "the plan does not carry the file it was built to carry, so this test is not exercising "
        "the shape the finding is about"
    )


def test_every_field_a_plan_may_name_is_read_by_its_emptiness_rule() -> None:
    """Whatever a plan may carry, the rule that decides it is empty has to be able to see.

    **Asked of the model's own field list rather than of the artifact's fields.** The two can
    disagree — and they do, right now, in the direction that makes a real plan unrepresentable
    — and a guard that compared the artifact against itself would say they agree.
    """
    from aisdlc.agents.plan_the_change import THE_FIELDS_THE_PLAN_MAY_NAME

    the_fields_the_rule_reads = {
        a_field
        for a_field, a_value in ImplementationPlan(files_to_add=["x"]).everything_it_says()
        if a_value or a_value == []
    }

    unread = set(THE_FIELDS_THE_PLAN_MAY_NAME) - the_fields_the_rule_reads

    assert not unread, (
        f"{sorted(unread)} may be named in a plan and `everything_it_says` does not return them, "
        "so a plan whose only content is one of them raises `EmptyPlanError` with a message "
        "listing four things the plan never claimed to do. The prompt asks the model to fill all "
        f"{len(THE_FIELDS_THE_PLAN_MAY_NAME)} fields, so the model is asked for a thing the "
        "validator refuses — and a model that answered correctly spends a correction from a "
        "budget meant for wrong answers."
    )


def test_the_refusal_names_what_the_plan_actually_left_out() -> None:
    """An empty plan's message names the lists it read, so a reader knows where to look.

    **Read out of the refusal rather than asserted against a string, because the string is
    what a person acts on.** The message currently enumerates the fields the rule *does* read,
    and a plan that left a list the rule cannot see out is described as though it had left
    those four alone — which sends a reader to check four things that were fine.
    """
    with pytest.raises(EmptyPlanError) as what_was_refused:
        ImplementationPlan()

    the_message = str(what_was_refused.value)

    from aisdlc.agents.plan_the_change import THE_FIELDS_THE_PLAN_MAY_NAME

    not_named = [a_field for a_field in THE_FIELDS_THE_PLAN_MAY_NAME if a_field not in the_message]

    assert not not_named, (
        f"the refusal does not name {not_named}, so a reader who just watched a plan be refused "
        "has no way to know it was refused for a field it cannot see. "
        f"The message says: {the_message}"
    )
