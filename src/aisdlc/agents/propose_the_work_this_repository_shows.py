"""What a repository shows, once a person has ruled on what it is.

**A run may propose the work a repository shows, and this is the only artifact that answers to
no agent.** Every other artifact is a named agent answering a question a work item carries: a
request somebody typed, requirements a person approved. This one is a run deciding what it will
work on next, from a `DiscoveryReport` a person has already ruled on — which is why it comes
**after** the discovery gate and **before** the product analyst.

**A machine asking for work is not a new idea here, so nothing new is invented for it.**
`Commissioned by` is a string rather than a switch precisely so that an identifier in the
`aisdlc-` namespace can say *a machine was asked*, and the approval gate reads the same prefix
to tell an agent from a person. So the requests here are the ordinary `CommissionedRequest`:
the same type, and only the name that asked differs. A parallel request type would be one
concept under two names, which is the thing this repository's naming rule exists to prevent.

**The answer is a separate type because the artifact is not what the model fills.** That is the
same reason `DiscoveryAnswer` is not `DiscoveryReport`: an answer carries what the model
concluded and an artifact carries what the system holds afterwards. Here the difference is
narrower — the model writes titles and bodies, and the system turns them into requests whose
`filed_as` is whatever GitHub returned rather than anything composed from `owner/name`.
"""

from __future__ import annotations

import time

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from aisdlc.agents.discovery_report import DiscoveryReport
from aisdlc.agents.what_an_agent_judged import WhatAnAgentJudged
from aisdlc.domain.commissioned_request import CommissionedRequest
from aisdlc.llm.asking_a_model_for import ask_a_model_for
from aisdlc.llm.correction_budget import (
    how_a_model_is_told_what_was_wrong,
    may_this_run_keep_asking,
)


class AProposedRequest(BaseModel):
    """A request without an address, in the shape the model fills.

    **A separate type from `CommissionedRequest` for one reason: the address.** `filed_as` is
    what GitHub returned the last time, and a model asked to fill it would be asked for a
    string it can invent — a plausible invented host in front of an approver being worse than
    no address at all. So the model fills a title and a body, and the system turns them into a
    `CommissionedRequest` whose address is whatever GitHub says or nothing at all.

    **This is the same reason `DiscoveryAnswer` is not `DiscoveryReport`, and a real model is
    what showed it.** With `requests` typed as a list of plain dictionaries there were no field
    names for the model to fill, and it answered the whole shape as one block of text with
    `<what_it_found>` tags in it — the validation error named `judged` and said the input was a
    string. A nested model with named fields is what every other answer type in this package
    has; this one was the only place that did not, and the model noticed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    body: str

    @field_validator("body")
    @classmethod
    def _refuse_a_request_nobody_could_work_from(cls, what_was_written: str) -> str:
        """Refuse a body that says nothing, and say what it would have been.

        **The body is the whole of the work.** A title is a line in a tracker, and a product
        analyst is asked to plan from the body alone — so a request with a title and no body
        asks a planner to plan nothing, which is the shape a real implementer once read as a
        plan and changed no files.
        """
        if not what_was_written.strip():
            raise ValueError(
                "a request arrived with a body of nothing. A title is not work: the body is "
                "where a person learns what is wrong and why it matters, and the product "
                "analyst is asked to plan from the body alone."
            )
        return what_was_written


class TheWorkARepositoryShows(BaseModel):
    """The work a run read out of a repository, as requests nobody typed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requests: list[CommissionedRequest]
    judged: WhatAnAgentJudged


class TheWorkARepositoryShowsAnswer(BaseModel):
    """The titles and bodies the model wrote, with nothing derived.

    **`filed_as` is absent and that is the point.** An address composed from `owner/name` is a
    link to a page that may not exist, which is why `CommissionedRequest` takes the address
    GitHub sent instead — so nothing here may fill it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    requests: list[AProposedRequest] = []
    judged: WhatAnAgentJudged

    @field_validator("requests")
    @classmethod
    def _refuse_a_run_that_proposed_nothing(
        cls, what_was_written: list[AProposedRequest]
    ) -> list[AProposedRequest]:
        """Refuse an empty list and an empty body, and say what each one would have meant.

        **An empty list is an outcome and has to be in words.** A plan with
        `tests_to_add: []` was read by a real implementer, who then changed nothing; an empty
        list here reads the same way to a product analyst who is asked to plan from it. Either
        there is nothing to do — which is an answer somebody has to read and agree with — or the
        model was asked the wrong question.
        """
        if not what_was_written:
            raise ValueError(
                "a run that has just read a repository was asked what work it shows and named "
                "none. Either there is nothing to do, which is an answer somebody has to read "
                "and agree with, or the model was asked the wrong question -- and an empty "
                "list reads as the first of those to whoever reads it next."
            )

        return what_was_written


def the_prompt_to_propose_the_work_this_repository_shows(
    report: DiscoveryReport,
    what_was_wrong_about_the_last_answer: str | None = None,
) -> str:
    """Show the repository as it was found, and ask what work that shows.

    **The report goes in whole, and the test says so.** A prompt carrying the report's name
    rather than the report would satisfy every other test in this file while proposing work
    about a summary of what the repository is rather than about what is wrong with it.

    **And the correction is part of the question rather than an apology before it.** This
    function used to take only the report, which meant the loop below could not exist: a model
    asked the same question twice with no word about why the first answer was refused answers it
    the same way twice. Every other reasoning node in this package has carried this argument since
    the first one of them needed it.
    """
    correction = (
        ""
        if what_was_wrong_about_the_last_answer is None
        else (
            "\nYour last answer was wrong, and this is what was wrong with it:\n"
            f"{what_was_wrong_about_the_last_answer}\n"
        )
    )

    return (
        "You have read a repository and written what it is. Read that report below and say "
        "what work this repository shows.\n\n"
        f"## {report.__class__.__name__}\n\n"
        f"architecture: {report.architecture_summary}\n"
        f"languages: {', '.join(report.languages) or 'none named'}\n"
        f"frameworks: {', '.join(report.frameworks) or 'none named'}\n"
        f"build system: {report.build_system or 'none named'}\n"
        f"ci system: {report.ci_system or 'none named'}\n"
        "key components:\n"
        + "".join(f"- {a_component}\n" for a_component in report.key_components)
        + "\nWrite each piece of work as a request somebody could have typed: a title and a "
        "body that says what is wrong and why it matters. A request whose body says nothing "
        "is a title in a tracker, and nobody can work from that." + correction
    )


def propose_the_work_this_repository_shows(
    report: DiscoveryReport,
    the_model: BaseChatModel,
) -> TheWorkARepositoryShows:
    """Ask the model what work this repository shows, and hand back what it wrote.

    **The refusals are the answer type's and not this function's**, because a request with
    nothing in it is worthless to whoever reads it next rather than merely wrong here: a
    product analyst is asked to plan from the body alone, and four empty lists were once
    passed for a plan and the implementer then read a plan naming nothing to do.

    **And it asks again, because this node was the only one that did not.** Every other
    reasoning node in this package loops on `may_this_run_keep_asking` and hands the model what
    was wrong. This one invoked once, and a real run answered `None` — a shape this deployment's
    model produces routinely, and its own `.env` says so — which ended the stage with a
    `ValidationError` rather than a repair. A run that stops because a model returned nothing is
    a run stopped by the shape of an answer rather than by anything anybody decided.
    """
    asking = ask_a_model_for(the_model, TheWorkARepositoryShowsAnswer)
    what_was_wrong: str | None = None
    began_at = time.monotonic()
    asked_so_far = 0
    last: ValidationError | None = None

    while may_this_run_keep_asking(asked_so_far, began_at):
        asked_so_far += 1
        try:
            the_answer = TheWorkARepositoryShowsAnswer.model_validate(
                asking.invoke(
                    the_prompt_to_propose_the_work_this_repository_shows(report, what_was_wrong)
                )
            )
            break
        except ValidationError as refused:
            what_was_wrong = how_a_model_is_told_what_was_wrong(refused)
            last = refused
    else:
        raise last  # type: ignore[misc]

    the_requests = [
        CommissionedRequest(title=a_request.title, body=a_request.body)
        for a_request in the_answer.requests
    ]

    return TheWorkARepositoryShows(requests=the_requests, judged=the_answer.judged)
