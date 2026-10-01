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
    (QaPlan, {"scenarios": ["A user opening the page sees the entry form."]}),
    (
        Requirements,
        {
            "requirements": ["The repository's README must name a Node version."],
            "acceptance_criteria": ["A line in the README names it."],
        },
    ),
    (
        DiscoveryReport,
        {
            "languages": ["TypeScript"],
            "architecture_summary": "A web application with an API beside it.",
            "evidence_files": [{"path": "README.md", "link": "https://example.invalid/README.md"}],
        },
    ),
)


@pytest.mark.parametrize(
    ("the_artifact", "the_fields_it_was_given"),
    THE_ARTIFACTS_THAT_REFUSE_AN_ANSWER_THAT_SAID_NOTHING,
    ids=[
        an_artifact.__name__
        for an_artifact, _ in THE_ARTIFACTS_THAT_REFUSE_AN_ANSWER_THAT_SAID_NOTHING
    ],
)
def test_a_field_holding_only_whitespace_is_read_as_absence(
    the_artifact: type, the_fields_it_was_given: dict[str, object]
) -> None:
    """A field of `" "` means the same as a field of `""`, or the artifact is not honest.

    **Every field of every artifact, and per field rather than per artifact.** A rule asked of
    the artifact as a whole is the rule that let this through: the plan said something, so the
    plan was accepted, and the field that said nothing rode along inside it.
    """
    the_answer = the_artifact(**{**the_fields_it_was_given, "test_strategy": "   "})

    for a_field, what_it_holds in the_answer.model_dump().items():
        assert a_value_that_says_something(what_it_holds) or str(what_it_holds).strip() == "", (
            f"{the_artifact.__name__}.{a_field} is {what_it_holds!r}. That is neither an answer "
            "nor an absence: this artifact carries a field that says nothing as though it said "
            "something, and a person at a gate reading it cannot tell the two apart. The "
            "emptiness rule strips whitespace — so a field that said nothing has to be absent in "
            "the way this system represents absence, which is what it means everywhere else."
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
