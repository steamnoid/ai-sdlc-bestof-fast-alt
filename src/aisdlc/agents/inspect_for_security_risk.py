"""The security analyst as a node: ask the model about the repository, then build the artifact.

§10 gives this agent `inspect repository for obvious security risks`, `identify
authentication/authorization concerns`, `inspect dependency/security configuration`, `identify
secrets handling issues` and `provide recommendations` — every one of them a question about
code, so like discovery, the product analyst and the architecture analyst it reads the clone.

**The node is called `inspect_for_security_risk` and the tool that renders the repository is
called `an_inspection_of`**, and the two are different things: one is a model's conclusion and
the other is a truncation of files. The glossary's own verb for this agent is "Inspect for
security risk", so that is the name.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from aisdlc.agents.a_value_that_says_something import a_value_that_says_something
from aisdlc.agents.how_to_name_a_file import the_rule_about_naming_a_file
from aisdlc.agents.security_finding import THE_FIELDS_A_FINDING_MAY_NAME
from aisdlc.agents.security_report import (
    EmptySecurityReportError,
    SecurityReport,
)
from aisdlc.agents.security_report_answer import SecurityReportAnswer
from aisdlc.domain.repository import Repository
from aisdlc.llm.asking_a_model_for import ask_a_model_for
from aisdlc.llm.correction_budget import (
    how_a_model_is_told_what_was_wrong,
    may_this_run_keep_asking,
)
from aisdlc.llm.llm_configuration import a_configuration_from_the_environment
from aisdlc.llm.model_factory import a_model_for
from aisdlc.tools.github_clone_repository import ClonedRepository
from aisdlc.tools.inspect_the_repository import an_inspection_of_the_code


def the_prompt_to_inspect_for_security_risk(
    inspection: str,
    repository: Repository,
    what_was_wrong_about_the_last_answer: str | None = None,
) -> str:
    """The question put to the model about one inspected repository.

    §10 calls this analysis advisory and not a replacement for a scanner, and the sentence is
    in the prompt because it is a claim about what the artifact *is*. Nothing depends on the
    model agreeing with it, and nothing would: the field asking for a signal is what makes an
    unsupported opinion refusable, and that is a shape rather than a sentence.
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
        f"You are inspecting {repository.owner}/{repository.name} for security risk.\n"
        "Answer from the inspection below and from nothing else.\n"
        "\n"
        "This is advisory analysis, not a replacement for a security scanner, and a finding\n"
        "is worth more for saying what a reader should doubt about itself.\n"
        "\n"
        "The inspection ends with a section naming the files you were NOT shown. A finding\n"
        "about one of those is a finding about a file you have not read, and it has to say\n"
        "that rather than reason from the name — a filename is not evidence of what is in\n"
        "it. A real run's gate refused a whole report for doing otherwise.\n"
        "\n"
        f"Each finding names these: {', '.join(THE_FIELDS_A_FINDING_MAY_NAME)}.\n"
        f"{correction}"
        "\n"
        "Your answer is one object with one field, and the field is called `findings`. Its\n"
        "value is the array: `[`, then each finding, then `]`.\n"
        "\n"
        "You cannot send a bare array, so do not try and do not invent another wrapper. A\n"
        "repository with nothing to report sends `{\"findings\": []}` — the field present and\n"
        "its value empty. Send `null` and there is no array to read, and a run that cannot\n"
        "read it asks you again rather than believing you."
        "\n"
        "A signal is what in this repository made you suspect it, quoted or named — a\n"
        "finding with no signal is an opinion. False-positive notes say why this might be\n"
        "fine, and an empty list of findings is an answer: a repository with no visible\n"
        "risk should say so rather than invent one.\n"
        "\n"
        "Name no field beyond these. An answer carrying anything else is refused rather than\n"
        "trimmed, because a conclusion this system did not ask for is one no human was ever\n"
        "shown.\n"
        "\n"
        f"Inspection of {repository.owner}/{repository.name}:\n"
        f"{inspection}"
    )



def inspect_for_security_risk(
    clone: ClonedRepository, repository: Repository, model: BaseChatModel
) -> SecurityReport:
    """The security report for a repository this run cloned.

    Validated inside the correction loop rather than before it, for the reason the architecture
    analyst's real run established: a provider that answers in prose instead of JSON raises a
    pydantic error, and a node that lets that error escape dies on a stack trace rather than
    asking the model to try again. The validation lives here so that a wrong shape, a bad
    severity and an empty report are all three the same event to the loop — one correction,
    the reason shown, the budget bounds it.
    """
    inspection = an_inspection_of_the_code(clone)
    what_was_wrong: str | None = None

    began_at = time.monotonic()
    asked_so_far = 0
    while may_this_run_keep_asking(asked_so_far, began_at):
        asked_so_far += 1
        asking = ask_a_model_for(model, SecurityReportAnswer)
        try:
            answer = SecurityReportAnswer.model_validate(
                asking.invoke(
                    the_prompt_to_inspect_for_security_risk(
                        inspection, repository, what_was_wrong
                    )
                )
            )
            return SecurityReport(
                findings=answer.findings,
                # **The account is written here rather than asked of the model, and the reason
                # is two real runs old.** `SecurityReportAnswer` is a bare array because a
                # model asked to fill a one-field object sends the field's contents instead, so
                # there is nowhere for a model to put this. The node holds the fact anyway:
                # what the analyst examined is what the node showed it.
                #
                # **Only after a correction has been spent**, and that ordering is the whole of
                # it. Composing the account on the first empty answer would let a model that
                # simply did not look be recorded as one that looked and found nothing — the
                # account is composed by the node, so it would vouch for an inspection the
                # model may not have made. The model is asked once more, in the ordinary way
                # and on the ordinary budget, and only a second silence becomes an account.
                nothing_found_because=_what_was_examined(inspection)
                if not a_value_that_says_something(answer.findings)
                and what_was_wrong is not None
                else None,
            )
        except (EmptySecurityReportError, ValidationError) as refused:
            what_was_wrong = how_a_model_is_told_what_was_wrong(refused)
            last = refused

    raise last


def _what_was_examined(inspection: str) -> str:
    """The account, composed from what the analyst was shown, and true by construction.

    **Named rather than "nothing found", because a bare claim is the silence the rule was
    written about.** What a reader needs from a security report with no findings is not the
    verdict — it is the scope, so they can tell "I looked and found nothing" from "I looked at
    one manifest and said nothing about the routes".
    """
    return (
        "The analyst reported no findings after examining what this run showed it: the "
        "repository's manifests, its README, its CI configuration and its top-level listing. "
        "Nothing outside that inventory was read, and no risk outside it was assessed.\n\n"
        f"What it was shown:\n\n{inspection}"
        + the_rule_about_naming_a_file()
    )


def the_security_analyst_using_the_configured_model() -> Callable[
    [ClonedRepository, Repository], SecurityReport
]:
    """The real `aisdlc-sec-analyze`: the model the environment names, asked about a clone.

    A factory rather than a default argument on `the_lifecycle`, for discovery's reason: the
    graph should not know how a model is obtained — it is handed a function, and this is the
    one that asks the environment. A test hands it a different function and never reads a key.

    **The model is built inside the call rather than at import time**, so the environment is
    read when the node runs. A factory that read it at import would freeze one deployment's
    model name into a process, and a resumed run would keep answering with the model that was
    configured when it started rather than the one configured now.

    `aisdlc-sec-analyze` looks for risk, and this is the only place that decision
    becomes a model call.
    """

    def analysing(
        clone: ClonedRepository, repository: Repository,
    ) -> SecurityReport:
        return inspect_for_security_risk(
            clone, repository, a_model_for(a_configuration_from_the_environment())
        )

    return analysing
