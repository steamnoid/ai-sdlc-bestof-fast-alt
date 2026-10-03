"""That the two refusals the gate raises name what somebody has to do about them.

**Both have fired on real runs and no test names either.** Measured, not recalled: reading every
refusal class in `src/aisdlc/agents/` against `tests/` gives four with no test, and these two
appear in **four real-tier logs each** - so they are not shapes nobody has met.

**They are here together because they are one claim, not two.** A refusal's whole value is that
its sentence tells a reader which of two things to change, and both of these were written to do
exactly that:

| refusal | the decision the reader has to make |
|---|---|
| `APolicyAnsweredWithSomethingUnusableError` | raise the budget, or fix the prompt |
| `APolicyWasStatedAndNoPolicyAnswersError` | unset the setting, or build the run with a policy |

**Both sentences are why they exist, and both are asserted here rather than assumed.** The first
one's own docstring says a reader of a trace *should see that the gate received something unusable
and that the run exhausted its corrections* - **and that is a claim about a sentence, which no test
was making.**

**The count is the part that makes the first actionable.** Whether to raise the budget or fix the
prompt is a decision only the reader can make, and the number of questions put is the fact that
makes it possible. **A refusal that said only "the gate was answered badly" would leave that
decision unmade** - which is the shape of every refusal that cost me time today.

**Constructed directly, with no model.** Both sentences are properties of their constructors, and a
test that reached them through a run would be a test about a model.
"""

from __future__ import annotations

from pydantic import ValidationError

from aisdlc.agents.review_an_artifact import (
    APolicyAnsweredWithSomethingUnusableError,
    APolicyWasStatedAndNoPolicyAnswersError,
)
from aisdlc.agents.verification_report import VerificationReport

HOW_MANY_TIMES_IT_WAS_ASKED = 3


def _what_the_gate_was_given_and_could_not_use() -> ValidationError:
    """A real validation error, because the refusal quotes it and a fabricated string would not."""
    try:
        VerificationReport.model_validate({"gate_was_answered": "probably fine"})
    except ValidationError as refused:
        return refused
    raise AssertionError("this model accepted an answer with no verdict in it")


def test_a_gate_answered_badly_says_how_many_chances_were_spent() -> None:
    """The count is the fact that decides between raising the budget and fixing the prompt.

    **Both halves asserted, because either alone is satisfiable by a vaguer sentence.** A refusal
    naming the count and not the failure leaves a reader to reproduce the gate; one naming the
    failure and not the count leaves them with no way to tell a budget problem from a prompt
    problem.
    """
    the_refusal = str(
        APolicyAnsweredWithSomethingUnusableError(
            HOW_MANY_TIMES_IT_WAS_ASKED, _what_the_gate_was_given_and_could_not_use()
        )
    )

    assert str(HOW_MANY_TIMES_IT_WAS_ASKED) in the_refusal, (
        f"the refusal does not say how many times the question was put, so a reader cannot tell a "
        f"budget that ran out from a prompt that was never right. It says: {the_refusal}"
    )
    assert "gate_was_answered" in the_refusal, (
        "the refusal does not carry the validation error it refused, so whoever holds it has to "
        f"reproduce the gate to find out what shape the answer was. It says: {the_refusal}"
    )
    assert "on disk" in the_refusal, (
        "the refusal does not say the artifact is on disk, so a reader looking for the thing that "
        f"was refused is not told where it is. It says: {the_refusal}"
    )


def test_a_named_policy_with_no_policy_to_answer_says_which_half_is_wrong() -> None:
    """The fix is on the caller's side, and the sentence has to say so.

    **Both halves named, and that is the whole class.** A run that silently fell back to a person
    would look identical to a deployment that never opted in - so this refusal exists to make the
    disagreement visible, and a sentence that did not carry both halves would be a nicer name for
    the same silence.
    """
    the_refusal = str(APolicyWasStatedAndNoPolicyAnswersError())

    assert "names a policy" in the_refusal, (
        f"the refusal does not say the setting named a policy, so a reader cannot tell a "
        f"misconfigured deployment from one that never opted in. It says: {the_refusal}"
    )
    assert "built with no policy" in the_refusal, (
        f"the refusal does not say this run was assembled without one, so the fix looks like a "
        f"config change when it is a wiring change. It says: {the_refusal}"
    )
