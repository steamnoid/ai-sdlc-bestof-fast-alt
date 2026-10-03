"""That a conflict this model cannot answer once is asked again rather than ended.

**This node invokes the model once and hands whatever came back to `model_validate`:**

```python
def _the_decision_a_model_made(a_model, the_question) -> WhatToDoAroundAConflict:
    try:
        return WhatToDoAroundAConflict.model_validate(
            ask_a_model_for(a_model, WhatToDoAroundAConflict).invoke(the_question)
        )
    except ValidationError as no_repair_was_named:
        raise AnAnswerThatIsNotADecisionError(...)
```

**Every other reasoning node in this repository asks again**, through `may_this_run_keep_asking`,
and `tests/test_a_model_that_answers_nothing_is_asked_again.py` records why that rule exists for
one of them: *a real model answered `None`, and the deployment's own `.env` says so in advance* -
this provider can return a message the structured-output parser reads as nothing, **which is a
malformed shape and not a refusal.**

**And this deployment's own run says the same about this node.** Across six full real-tier runs,
the three tests in `test_settle_a_conflict_in_this_run.py` fail **two at a time, always the same
two**, which is one fault seen twice rather than two faults:

```text
FAILED test_settle_a_conflict_in_this_run.py::
    test_a_real_model_names_one_of_the_two_repairs_and_says_why
FAILED test_settle_a_conflict_in_this_run.py::
    test_the_repair_sent_the_run_to_a_node_this_graph_holds
```

and the reason in one of the logs is the shape itself:

```text
Input should be a valid dictionary or instance of WhatToDoAroundAConflict
[type=model_type, input_value=None, input_type=NoneType]
```

**A node that dies on one malformed answer is effectively dead on this deployment**, and it dies
while the run is holding an open conflict - the one place a run most needs a second attempt, since
the alternative is a delivery nobody can merge.

**A model that answers wrongly once and properly the second time, and recording both questions.**
A model that always answered wrongly would be caught by the budget rather than by a retry, and one
that always answered properly would never exercise the loop at all.
"""

from __future__ import annotations

import pytest

from aisdlc.agents.what_to_do_when_a_pull_request_will_not_merge import WhatToDoAroundAConflict
from aisdlc.graph.settle_a_conflict_node import (
    AnAnswerThatIsNotADecisionError,
    _the_decision_a_model_made,
)

THE_CONFLICT_AS_GITHUB_REFUSED_IT = (
    "HTTP 409. Merge conflict between main and aisdlc/sqlite-sidecars-in-version-control"
)
THE_REPAIR = "rebase it and try again"


class _AModelThatAnswersOnceWrongly:
    """A model that answers wrongly once and properly the second time, recording both questions.

    **A sequence and not a fixed answer, because the claim is about the second question.**
    """

    def __init__(self, what_it_answers: list[object]) -> None:
        self._what_it_answers = what_it_answers
        self.what_it_was_asked: list[str] = []

    def with_structured_output(self, *arguments: object, **keywords: object) -> object:
        """LangChain's entry point, and the answers are already decided, so this is the model."""
        return self

    def invoke(self, the_question: str) -> object:
        """Hand back the next answer in the sequence, and keep the question for the test to read."""
        self.what_it_was_asked.append(the_question)
        return self._what_it_answers.pop(0)


def _a_decision_this_model_can_still_take() -> WhatToDoAroundAConflict:
    """One of the two repairs, named by the exact text `WhatToDoAroundAConflict` accepts."""
    return WhatToDoAroundAConflict(
        the_repair="rebase it and try again",
        why=(
            "the merge conflict is in a file this change wrote, and rebasing "
            "puts it on top of main"
        ),
    )


def test_a_malformed_answer_is_asked_again_and_the_second_one_is_taken() -> None:
    """One malformed answer does not end a run that is holding an open conflict.

    **`None` and not a wrong value**, because `None` is the shape this deployment's provider
    actually produces: a message the structured-output parser reads as nothing. **A test that used
    a wrong-but-well-formed answer would prove the loop exists and say nothing about this.**
    """
    a_model = _AModelThatAnswersOnceWrongly([None, _a_decision_this_model_can_still_take()])

    the_decision = _the_decision_a_model_made(a_model, THE_CONFLICT_AS_GITHUB_REFUSED_IT)

    assert the_decision.the_repair == THE_REPAIR, (
        f"the run took {the_decision.the_repair!r} rather than the repair the model named on its "
        f"second answer, so the retry did not use what it was given"
    )
    assert len(a_model.what_it_was_asked) == 2, (
        f"the model was asked {len(a_model.what_it_was_asked)} times and the first answer was "
        f"malformed, so the node has no retry and a run holding an open conflict is ended by one "
        f"message the parser read as nothing"
    )


def test_the_second_question_says_why_the_first_answer_was_refused() -> None:
    """A retry that repeats the question unchanged is not a repair, and this says why.

    **The half a counter cannot see.** Asking twice is the loop; **telling the model why its answer
    was refused is the other half**, and without it the loop is a second chance at the same question
    rather than a repair. This repository has a shared rule for that wording - one rule for six
    agents - so this asserts the second question carries it rather than that it was asked at all.
    """
    a_model = _AModelThatAnswersOnceWrongly([None, _a_decision_this_model_can_still_take()])

    _the_decision_a_model_made(a_model, THE_CONFLICT_AS_GITHUB_REFUSED_IT)

    the_second_question = a_model.what_it_was_asked[1]

    assert len(the_second_question) > len(a_model.what_it_was_asked[0]), (
        "the second question is the first one and nothing more. A retry that repeats a question "
        "unchanged is not a repair, and the model has no way of knowing its first answer was the "
        "reason for the second"
    )
    assert WhatToDoAroundAConflict.__name__ in the_second_question, (
        "the second question does not name the shape the answer has to have, so the model is asked "
        "again without being told what shape it got wrong. The error a run actually gets names it"
    )


def test_a_model_that_never_answers_is_still_refused_by_name() -> None:
    """The retry is bounded, and the refusal a person reads is the one this node always raised.

    **Without this, a loop that never ends would be green.** And the refusal must survive: a run
    whose model can name no repair at all is a run that delivered a merge nobody can merge, and
    saying so is the last useful thing this node can do.
    """
    a_model = _AModelThatAnswersOnceWrongly([None, None, None, None, None, None])

    with pytest.raises(AnAnswerThatIsNotADecisionError) as it_raised:
        _the_decision_a_model_made(a_model, THE_CONFLICT_AS_GITHUB_REFUSED_IT)

    assert WhatToDoAroundAConflict.__name__ in str(it_raised.value), (
        f"the refusal does not say what shape it wanted, so whoever holds it has to go and look "
        f"up what the node validates. It says: {it_raised.value}"
    )
