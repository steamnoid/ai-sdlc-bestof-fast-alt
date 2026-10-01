"""A field holding whitespace is not absence, and three artifacts disagreed about that once.

**A real model returned `test_strategy` as a single space, and the plan it was in passed
every check this repository had.** The emptiness rule is one module —
`a_value_that_says_something`, written because three artifacts had each got it wrong with a
bare `any()` and a string of spaces is truthy. That rule strips whitespace and says such a
field said nothing, and it is applied by the validator that asks *does any field say
something*.

**The rule is applied to the wrong question.** The plan is asked whether it says anything
*at all*, and it did: the scenarios were real. So `test_strategy` — which said nothing — was
carried into a `QaPlan` that a gate then presents to a person, and on a card a field holding
`" "` is indistinguishable from a field holding a strategy. Nothing in the pipeline failed,
so the run delivered a QA plan with three real fields and one that was not.

**The rule is asserted here per field, on all three artifacts, and that is what makes it a
rule rather than a fix to one shape.** The three artifacts that share the emptiness rule are
the three a real model has now filled wrongly in this repository, and a fix written against
`QaPlan` alone would be the third instance of a fix made where the bug was found rather than
where the rule is — which is the recurring shape in this repository's own history.

**Not refused, and that is the design.** A repository with nothing ambiguous about it has no
edge cases to name, and the honest artifact says so with three filled fields and one empty
one. So a field saying nothing becomes *absent* rather than refused: `QaPlan.test_strategy`
defaults to `""`, and `""` is what this system means by absence. Refusing the whole plan over
one blank field would force a model to invent a boundary condition to fill a list, which is
the guess the artifact's own emptiness rule exists to prevent.
"""

from __future__ import annotations

import pytest

from aisdlc.agents.a_value_that_says_something import a_value_that_says_something
from aisdlc.agents.discovery_report import DiscoveryReport
from aisdlc.agents.qa_plan import QaPlan
from aisdlc.agents.requirements import Requirements

THE_ARTIFACTS_THAT_REFUSE_AN_ANSWER_THAT_SAID_NOTHING = (
    (
        "QaPlan",
        QaPlan,
        "test_strategy",
        "   ",
        "scenarios",
        ["A user opening the page sees the entry form."],
    ),
    (
        "Requirements",
        Requirements,
        "acceptance_criteria",
        ["   "],
        "requirements",
        ["The repository's README must name a Node version."],
    ),
    (
        "DiscoveryReport",
        DiscoveryReport,
        "suggested_changes",
        ["   "],
        "languages",
        ["TypeScript"],
    ),
)
"""Each artifact, the field to blank, and the field to keep real so the artifact is not empty.

**The blank is shaped like the field, and both shapes are here because a model produces
both.** A QA plan's `test_strategy` is one string and a model filled it with one space; a
discovery report's `suggested_changes` is a list and a model put one blank entry in it, which
is the shape a reader counts. Handing a list field a bare string would not reach the rule at
all — Pydantic refuses the shape before any validator runs, and the test would be reporting a
type error rather than an empty field.

**The field is named per artifact, and that is a correction to the first version.** It handed
`"   "` to `test_strategy` on all three, and Pydantic drops a keyword the model has no field
for — so two of the three cases were green on code carrying the bug. A shell that accepts the
absence cannot prove it, and the test below now checks the field is one before using it.
"""


THE_WAYS_THIS_SYSTEM_WRITES_THAT_A_FIELD_SAID_NOTHING = ("", [], None)
"""Absence is three shapes here, and all three are already in use.

`""` for a field where nothing was said, `[]` for a collection nothing was added to — every
collection field in every artifact defaults to it — and `None` for a thing that may not exist
rather than a thing nobody filled in. A field holding whitespace is none of the three, and
that is the whole claim: it is a fourth way of saying nothing that a reader cannot recognise.
"""


@pytest.mark.parametrize(
    (
        "the_artifact_name",
        "the_artifact",
        "the_field_to_blank",
        "the_blank_written_in_it",
        "the_field_to_keep",
        "what_it_says",
    ),
    THE_ARTIFACTS_THAT_REFUSE_AN_ANSWER_THAT_SAID_NOTHING,
    ids=[a_name for a_name, *_ in THE_ARTIFACTS_THAT_REFUSE_AN_ANSWER_THAT_SAID_NOTHING],
)
def test_a_field_holding_only_whitespace_is_read_as_absence(
    the_artifact_name: str,
    the_artifact: type,
    the_field_to_blank: str,
    the_blank_written_in_it: object,
    the_field_to_keep: str,
    what_it_says: list[str],
) -> None:
    """Every field of every artifact says something or is absent, and there is no third state.

    **Every field of every artifact, and per field rather than per artifact.** A rule asked of
    the artifact as a whole is the rule that let this through: the plan said something, so the
    plan was accepted, and the field that said nothing rode along inside it.

    **The field really is a field of this artifact, checked rather than assumed.** A blank
    handed to a model with no such field is dropped on the way in, the case is green, and the
    artifact is one that would have carried the blank to a gate.
    """
    assert the_field_to_blank in the_artifact.model_fields, (
        f"{the_artifact_name} has no field {the_field_to_blank!r}, so handing it one proves "
        "nothing: Pydantic drops a keyword the model does not declare, and this case would be "
        "green on exactly the code it exists to catch"
    )

    the_answer = the_artifact(
        **{the_field_to_keep: what_it_says, the_field_to_blank: the_blank_written_in_it}
    )

    for a_field, what_it_holds in the_answer.model_dump().items():
        is_an_answer = a_value_that_says_something(what_it_holds)
        is_an_absence = what_it_holds in THE_WAYS_THIS_SYSTEM_WRITES_THAT_A_FIELD_SAID_NOTHING

        assert is_an_answer or is_an_absence, (
            f"{the_artifact_name}.{a_field} is {what_it_holds!r}. That is neither an answer "
            "nor an absence: this artifact carries a field that says nothing as though it said "
            "something, and a person at a gate reading it cannot tell the two apart. The "
            "emptiness rule strips whitespace — so a field that said nothing has to be one of "
            f"the {len(THE_WAYS_THIS_SYSTEM_WRITES_THAT_A_FIELD_SAID_NOTHING)} shapes this system "
            "already writes absence in, and holding whitespace is not one of them."
        )


def test_a_field_of_whitespace_is_absent_after_the_artifact_validates_it() -> None:
    """The artifact itself normalises it, so nothing downstream has to remember to.

    **Asserted on the artifact rather than on a helper, because a helper is where this was
    wrong once.** `a_value_that_says_something` already answered the question correctly and
    the artifact still carried the space, so the rule that is missing is not about detecting
    emptiness — it is about what the artifact does with it. A node handing this to a gate, to
    a board, or to a summary should not have to ask.

    **And `""` is the domain's own representation of absence, not a new one.** `QaPlan`'s
    fields default to `""` and `DiscoveryReport` uses `str | None` where absence is a fact
    about the repository; this is the same vocabulary, applied to a case where the model said
    nothing where there was something to say.
    """
    the_plan = QaPlan(test_strategy="  ", scenarios=["Something real."])

    assert the_plan.test_strategy == "", (
        f"QaPlan kept {the_plan.test_strategy!r} as a strategy. The artifact asks only whether "
        "the plan says something at all, so a plan with real scenarios carries a blank strategy "
        "into a gate, where it reads exactly like a real one"
    )

    the_report = DiscoveryReport(
        languages=["TypeScript"],
        architecture_summary="A web application.",
        evidence_files=[{"path": "README.md", "link": "https://example.invalid/README.md"}],
        suggested_changes=["   "],
    )

    assert the_report.suggested_changes == [], (
        f"DiscoveryReport kept {the_report.suggested_changes!r} as a suggested change. A reader "
        "of a discovery report counts them, and a list holding one blank entry is a report "
        "claiming a suggestion it did not make"
    )
