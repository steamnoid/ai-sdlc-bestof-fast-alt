"""What the real tier is given, and where each of those things comes from.

**Nothing here is a default, and that is the whole file.** A repository named in this
file would be a repository this repository names, and a task written into it would be a
task about that repository — so `the_repository` and `the_task` are refused rather than
filled in. A tier that quietly analysed whatever was in a constant is a tier nobody can
point anywhere, and a run commissioned with a request nobody gave produces eight artifacts
about work nobody asked for, each one shaped exactly like a record of work that was.

**`load_dotenv` in a fixture here, and neither in `src/` nor at the top of this file.**
`python-dotenv` is a dev dependency and nothing in the package imports it, because a library
that read a dotfile from its own directory would behave differently depending on where it was
imported from. A deployment has real environment variables; a developer has a `.env`. It is
not at the top of this file either, and that is the half worth reading: pytest imports a
conftest in order to read the markers of the tests it is about to deselect, so a dotfile
loaded at import time is loaded by every default run on this machine. See
`the_deployments_own_settings` for what that cost the first time.

**One clone per module, and the reason is the cost.** A clone is a network round trip over
a whole history, and a test asserting three contracts about *one* report is three claims
about one run rather than three claims about three runs. Asserting separately about
separate runs would only prove the model answers differently each time, which is true and
is not what any of this is for.

**The provider is a parameter the test drives, never one the environment names.** The
fixtures take `request.param` and every test is parametrised over it indirectly, so a
deployment configured for one provider *skips* the others with the reason printed. Reading
`LLM_PROVIDER` inside the fixture instead means every parametrised case runs against
whichever provider the shell happened to name, and a green tick beside a provider's name
then proves nothing about that provider — which is what happened in the engine this tier
was copied from, and is why the copy says so.

**Every fixture here is opt-in by living in this directory.** `addopts` in `pyproject.toml`
deselects `e2e`, so a deselected test's fixtures never run and the default suite needs no
credential, no network and no container. The watching switch is therefore set by a fixture
here rather than by a line at the top of this file: pytest imports a conftest to read the
markers of tests it is about to deselect, so a `setdefault` at import time would turn the
watching on for the whole default run and every test proving a milestone line exists would
fail on a terminal instead of on `capsys`.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from dotenv import load_dotenv

from aisdlc.domain.commissioned_request import a_request_about
from aisdlc.domain.repository import Repository
from aisdlc.llm.llm_configuration import a_configuration_from_the_environment
from aisdlc.llm.model_factory import a_model_for
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.observability.saying_what_a_run_is_doing import THE_SETTING_THAT_ASKS_TO_WATCH
from aisdlc.store.where_the_register_lives import the_register_lives_at
from aisdlc.tools.github_client import Addresses, the_clone_url_of
from aisdlc.tools.github_clone_repository import (
    ClonedRepository,
    a_repository_to_clone,
    clone_repository,
)
from aisdlc.tools.run_tests import SuiteOutcome, the_container_is_reachable
from aisdlc.verify_the_change import the_suite_in_a_container

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

PLACEHOLDERS = frozenset(
    {"", "todo", "tbd", "n/a", "none", "unknown", "...", "lorem ipsum", "placeholder"}
)
"""One list for the whole tier, because two copies would be two places to forget an entry."""


@pytest.fixture(scope="session", autouse=True)
def the_deployments_own_settings() -> Iterator[None]:
    """Read the deployment's `.env`, for this tier and only while this tier runs.

    **Inside a fixture and not at the top of this file, and the reason is a whole run bought
    by accident.** Pytest imports a conftest in order to read the markers of the tests it is
    about to deselect, so a `load_dotenv` written here runs on every `uv run pytest -q` on this
    machine — and the two default-suite tests guarded by `skipif` on `LLM_PROVIDER` stopped
    skipping. The first default run after that file landed cloned a public repository and asked
    a paid model, and the only visible sign was a suite that took 64 seconds instead of 5.

    `gate.yml` says in a comment that the default suite is free of every real dependency, and
    this fixture is what makes that true rather than true on the machine it was written on.
    A deselected test's fixtures never run, so the loading happens only when a test in this
    directory actually asks for something.

    `load_dotenv` does not override a variable that is already set, which is the second half
    of the honesty: a credential passed in the shell wins over the one in the file, and a
    credential deliberately set to an empty string stays empty instead of being refilled and
    turned into a paid call.
    """
    # **Every variable it loaded is put back, and the shape beside it is why.** A session fixture
    # that takes and does not return leaves every one of these in the process for every file that
    # follows, which is how a file passes alone and fails in a suite — and a person who has seen
    # that twice re-runs the tier until it is green. `the_real_tier_is_being_watching` below saves
    # one variable and puts it back; this one loads an arbitrary number of them and has to do the
    # same for each. **A fixture that yields without doing anything afterwards has still taken and
    # not returned.**
    what_was_already_set = dict(os.environ)
    load_dotenv(REPOSITORY_ROOT / ".env")
    yield

    for a_name, a_value in what_was_already_set.items():
        os.environ[a_name] = a_value
    for a_name in [a_name for a_name in os.environ if a_name not in what_was_already_set]:
        os.environ.pop(a_name, None)


@pytest.fixture(autouse=True)
def the_register_this_test_works_in(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Open the register at this test's own directory, for every test, and nobody else opens it.

    **The connection is process-wide, so the only shapes available are per tier and per test —
    and *each file opens its own* is not one of them**, because a second call closes the first.
    Twelve of the fourteen files in this tier depended on whichever of the other two ran first, and
    inherited a path under a temporary directory that belonged to a module which had since ended.
    **That is how a file passes alone and fails in a suite.**

    **Per test rather than per tier**, because a register shared by the whole tier means a work item
    one file commissioned is visible to every file after it, and a test counting what a register
    holds would be counting another file's. Opening one is a `sqlite3.connect` and the previous
    connection closes by this one, so **the isolation is free and the sharing would be a choice.**

    **Autouse, because the whole point is that no file has to remember.** A helper twelve files
    import is twelve places to forget, and the twelfth is found by a file that fails only when it
    runs after one of the other eleven.
    """
    the_register_lives_at(tmp_path_factory.mktemp("register") / "aisdlc.sqlite3")
    yield


@pytest.fixture(scope="session", autouse=True)
def the_real_tier_is_being_watched() -> Iterator[None]:
    """Turn the watching on for this tier and only this tier, and never over a deployment's word.

    A real run here is a real model, a real clone, a real container and tens of minutes, and
    the thing that makes it supervisable is a person seeing which call is running right now.
    The default suite stays silent, and silence is what makes it assertable at all.

    `setdefault` rather than an assignment, so a deployment that deliberately turned the
    watching off has said so and this tier does not overrule it.
    """
    what_it_was = os.environ.get(THE_SETTING_THAT_ASKS_TO_WATCH)
    os.environ.setdefault(THE_SETTING_THAT_ASKS_TO_WATCH, "1")
    yield
    if what_it_was is None:
        os.environ.pop(THE_SETTING_THAT_ASKS_TO_WATCH, None)
    else:
        os.environ[THE_SETTING_THAT_ASKS_TO_WATCH] = what_it_was


@pytest.fixture(scope="module")
def the_placeholders() -> frozenset[str]:
    """The words that are a shape rather than a finding, handed over rather than imported.

    A fixture rather than a module constant so a test says what it is checking against and
    a reader does not have to know that two `conftest`s in one repository share a name.
    """
    return PLACEHOLDERS


@pytest.fixture(scope="module")
def the_repository() -> Repository:
    """The repository this deployment points the real tier at, or a loud reason there is none.

    `E2E_REPOSITORY` with no default, and `pytest.skip` rather than an exception: a tier that
    cannot say what it was asked to work on says so and stops, and it says which setting
    would have given it one. The address is `owner/name` and anything else is refused here
    rather than failing later inside GitHub with a message about a repository.
    """
    named = os.environ.get("E2E_REPOSITORY", "").strip()
    if not named or "/" not in named:
        pytest.skip(
            "E2E_REPOSITORY is not set to owner/name, so there is no repository to work on. "
            "Set it and run again — this tier will not name a repository of its own."
        )

    owner, _, name = named.partition("/")
    return Repository(owner=owner, name=name)


@pytest.fixture(scope="module")
def the_cloned_repository(
    the_repository: Repository, tmp_path_factory: pytest.TempPathFactory
) -> ClonedRepository:
    """A real clone of that repository, made once for the module and read by everybody in it.

    Read-only, and that is why it needs no credential: this system promises to onboard an
    arbitrary *public* repository, and asking for a token to read one would break that
    promise for no reason. A stage that writes asks for `a_clone_this_run_may_write_to`,
    which is a different request and a different fixture.
    """
    project = tmp_path_factory.mktemp("the-repository-this-run-read")
    return clone_repository(
        a_repository_to_clone(
            repository=the_repository,
            addresses=Addresses(
                fetch_from=the_clone_url_of(the_repository),
                origin_of_the_code=the_clone_url_of(the_repository),
            ),
            into=project / "repository",
        )
    )


@pytest.fixture(scope="module")
def a_clone_this_run_may_write(
    the_cloned_repository: ClonedRepository, tmp_path_factory: pytest.TempPathFactory
) -> ClonedRepository:
    """A second copy of that clone, which a stage may write into and commit to.

    **A copy rather than the shared clone, and the reason is that the two kinds of stage are
    not the same claim.** Every other stage in this tier reads; the implementer writes and
    commits, and a commit left in the shared clone would be there for the next module to
    find. A test asserting a checkout is unchanged by a stage that changed nothing would then
    pass for the wrong reason, which is the same shape as a test that cannot fail.

    The copy is of a real clone, made with the file system rather than with `git`, because
    the history is what the delivery diffs against and a fresh `git clone` of a path would
    be a second network call to obtain a thing already on disk.
    """
    a_second_copy = tmp_path_factory.mktemp("the-repository-this-run-writes") / "repository"
    shutil.copytree(the_cloned_repository.path, a_second_copy)
    return ClonedRepository(
        path=a_second_copy,
        ref=the_cloned_repository.ref,
        commit=the_cloned_repository.commit,
    )


@pytest.fixture(scope="module")
def the_task() -> str:
    """The one sentence the stages that plan a change are asked to act on.

    `E2E_TASK` with no default, for the reason `E2E_REPOSITORY` has none. **Empty rather than
    skipping**, because a stage that plans needs one and a stage that analyses a repository
    does not — so a skip here would make every file in this tier unreachable for a
    deployment that has a repository and no task yet, which is a quiet way of never proving
    anything. The stages that need it refuse with a message naming the setting.
    """
    return os.environ.get("E2E_TASK", "").strip()


@pytest.fixture(scope="module")
def the_model_for() -> Callable[[LlmProvider], object]:
    """How to obtain a real model of a named provider, or a loud reason there is none.

    A fixture returning a function rather than a fixture returning a model, because the
    provider is the thing a run proves and a fixture cannot be given one.
    """

    def a_model_of(the_provider: LlmProvider) -> object:
        configured = os.environ.get("LLM_PROVIDER", "").strip()
        if configured != the_provider.value:
            pytest.skip(
                f"the deployment states LLM_PROVIDER={configured!r}, so this run can prove "
                f"{configured!r} and not {the_provider.value!r}. Point LLM_PROVIDER at "
                f"{the_provider.value!r} and run again."
            )
        return a_model_for(a_configuration_from_the_environment())

    return a_model_of


@pytest.fixture(scope="module")
def a_placeholder_check() -> Callable[[object, str], None]:
    """Refuse a value that is a shape rather than a finding, and say which field it was in.

    A fixture returning the check, so a test says `check(what, where)` rather than importing
    a helper out of a module whose name is shared with another `conftest`.
    """

    def checked(value: object, what_it_is: str) -> None:
        if value is None:
            # Absent is a value this system means and not one to judge. A repository with no
            # CI is ordinary, and `str(None)` is "none", which reads as a placeholder and is
            # not one.
            return
        text = str(value).strip()
        if text.lower() in PLACEHOLDERS:
            raise AssertionError(
                f"{text!r} is placeholder text in {what_it_is}, which means the model returned "
                "a shape rather than a finding"
            )

    return checked


@pytest.fixture(scope="module")
def a_container() -> Callable[[ClonedRepository, Repository], SuiteOutcome]:
    """The repository's own suite, run where §27 says it runs — or a loud reason there is none.

    Asked of Docker itself rather than of `Docker.is_available()`, because that reports what
    the client library found at import time and the failure this guards against is a daemon
    that is not *running* — which reads as available and answers nothing.
    """
    if not the_container_is_reachable():
        pytest.skip(
            "no container on this machine, and a repository's own suite may not be run on the "
            "host. Start Docker and run again — there is no cheaper way to make this pass and "
            "there must not be one."
        )
    return the_suite_in_a_container


@pytest.fixture(scope="module")
def a_request() -> object:
    """The request the analysts are handed, built from the deployment's sentence.

    A fixture rather than a module constant because the sentence is the deployment's, and a
    module in a test tier that is imported before `load_dotenv` has run would carry whatever
    the environment held at import time.
    """
    a_sentence = os.environ.get("E2E_TASK", "").strip()
    if not a_sentence:
        pytest.skip(
            "E2E_TASK is not set, so this run has no request to reason about. Set it to one "
            "sentence and run again."
        )
    return a_request_about(a_sentence)
