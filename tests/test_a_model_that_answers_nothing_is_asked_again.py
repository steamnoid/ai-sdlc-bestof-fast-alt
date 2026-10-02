"""That a model answering nothing does not end the run that asked.

**`propose_the_work_this_repository_shows` was the only reasoning node in this package with no
correction loop.** Every other one — `discover_the_repository`, `analyze_the_repository`,
`brief_this_repository`, `plan_the_change` — asks inside `while may_this_run_keep_asking(...)`,
catches `ValidationError`, and tells the model what was wrong. This one invoked the model once and
handed whatever came back to `model_validate`:

```python
the_answer = TheWorkARepositoryShowsAnswer.model_validate(
    ask_a_model_for(the_model, TheWorkARepositoryShowsAnswer).invoke(
        the_prompt_to_propose_the_work_this_repository_shows(report)
    )
)
```

**A real run answered `None`.** `space-bunny-free` returned a message the structured-output parser
read as nothing, and the deployment's own `.env` says so in advance:

> Ta brama potrafi zwrocic wiadomosc bez wywolania narzedzia i parser robi z tego `None`, co jest
> blednym ksztaltem a nie odmowa — wiec pytanie nalezy powtorzyc, a nie konczyc run.

`AISDLC_CORRECTION_BUDGET=0` is set on this deployment for exactly that reason, so the budget is
unlimited — and this node never consults it, so one malformed answer from the very model this
deployment is configured for ends the stage with a `ValidationError`. Four tests errored on one
run, and every other agent on that run was unaffected.

**And a retry here would have had nothing to say.** The other nodes' prompts take a
`what_was_wrong` argument and render it. This one's prompt takes only the report, so the loop is
not merely missing — the half that tells the model why its last answer was refused is missing too,
and adding a loop without it would buy retries that repeat the same question.

**A fake model, because this is plumbing and a real one would prove nothing about it.** §0.3 is
explicit that reasoning *quality* is owned by `evals/` and never by pytest; what pytest owns here
is that a malformed answer is repaired rather than propagated, and that the model is told what was
wrong when it is asked again. Both are statements about this function's shape.
"""

from __future__ import annotations

from aisdlc.agents.discovery_report import DiscoveryReport, evidence_for
from aisdlc.agents.propose_the_work_this_repository_shows import (
    TheWorkARepositoryShowsAnswer,
    propose_the_work_this_repository_shows,
)
from aisdlc.domain.repository import Repository

A_REPOSITORY = Repository(owner="paligakrzychu", name="wellbeing-tracker-public")


class _AModelThatAnswersOnceWrongly:
    """A model that answers wrongly once and properly the second time, recording both questions.

    **A sequence and not a fixed answer, because the claim is about the second question.** A model
    that always answers wrongly would be caught by the budget rather than by a retry, and one that
    always answers properly would never exercise the loop at all.
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


def _a_report_naming_one_file() -> DiscoveryReport:
    """A report a model can be asked about, holding a file it really has."""
    return DiscoveryReport(
        languages=["TypeScript"],
        frameworks=["React"],
        build_system="npm ci && npm run build",
        ci_system="GitHub Actions",
        architecture_summary="A Next.js tracker served from web-app/ and tested by vitest.",
        key_components=["web-app"],
        evidence_files=evidence_for(["web-app"], A_REPOSITORY),
        suggested_changes=[],
    )


def _a_good_answer() -> TheWorkARepositoryShowsAnswer:
    """The second answer: titles and a body, which is what the model is supposed to write."""
    return TheWorkARepositoryShowsAnswer.model_validate(
        {
            "requests": [
                {
                    "title": "The README names no runtime",
                    "body": "Nothing in the repository says which Node the suite is verified on, "
                    "so a contributor's install can drift off it silently.",
                }
            ],
            "judged": {
                "what_it_found": "a repository whose CI never reads the TypeScript compiler",
                "what_it_could_not_settle": "whether the gate is read by a person or a policy",
                "what_it_expects_next": "a person ruling on whether this is the work to do",
            },
        }
    )


def test_a_model_that_answers_nothing_is_asked_again_and_told_what_was_wrong(monkeypatch) -> None:
    """One malformed answer is repaired, and the second question says why the first was refused."""
    monkeypatch.setenv("AISDLC_CORRECTION_BUDGET", "0")

    the_model = _AModelThatAnswersOnceWrongly([None, _a_good_answer().model_dump(mode="json")])

    what_the_run_wrote = propose_the_work_this_repository_shows(  # type: ignore[arg-type]
        _a_report_naming_one_file(), the_model
    )

    assert len(the_model.what_it_was_asked) == 2, (
        f"the model was asked {len(the_model.what_it_was_asked)} times for one question. A model "
        "that answered nothing ended a stage that the correction budget exists to keep going"
    )
    assert "None" in the_model.what_it_was_asked[1] or "validation" in (
        the_model.what_it_was_asked[1].lower()
    ), (
        "the second question does not say the first answer was refused, so the model is being "
        f"asked the same question twice: {the_model.what_it_was_asked[1]!r}"
    )
    assert what_the_run_wrote.requests[0].title == "The README names no runtime", (
        "the run did not write down the request the model's second answer carried"
    )
