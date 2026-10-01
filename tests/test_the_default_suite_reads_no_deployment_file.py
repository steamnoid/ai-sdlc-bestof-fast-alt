"""The default suite must not read a deployment's `.env`, and this is the check that says so.

**A real run of the default suite asked a paid model a question, and nothing about the
output said why.** This repository's `gate.yml` makes a claim in a comment rather than in an
assertion:

    # The default suite is free of every real dependency, so CI needs no secrets and the
    # e2e tier is deliberately absent rather than skipped.

Both halves were true until this repository grew `tests/e2e/conftest.py`, which loads the
deployment's `.env` so the real tier can find its model. **Pytest imports a conftest in order
to read the markers of the tests it is about to deselect**, so that file was imported by
every default run whether or not one of its tests was ever selected — and the two tests
guarded by `skipif` on `LLM_PROVIDER` stopped skipping. One of them is a whole run: a clone,
a graph walk, and a model call, paid for by a command whose contract is that it costs
nothing.

**So the claim is checked by asking a fresh interpreter rather than by reading the source.**
A test that parsed `conftest.py` and looked for a `load_dotenv` at module level would be a
guard that can be satisfied by moving the call one line down, which is the third guard of
that shape this family of repositories has now had. Importing the module in a subprocess
whose environment has the setting removed, and asking what the interpreter then sees, is the
question itself — and it fails for a `load_dotenv` wherever it is, at import time or three
lines below one.

**The setting removed from the subprocess environment, and named.** Inheriting the parent's
environment would make this test pass on a machine that had exported `LLM_MODEL` and fail on
one that had not, which is a guard that measures the developer's shell. The list is the
settings a `.env` is read for, and `python-dotenv` refusing to override an already-set
variable is exactly what makes removing them the honest way to ask.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

THE_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
THE_REAL_TIERS_CONFTEST = THE_REPOSITORY_ROOT / "tests" / "e2e" / "conftest.py"

THE_SETTINGS_A_DOTFILE_IS_READ_FOR = (
    "LLM_PROVIDER",
    "LLM_ENDPOINT",
    "LLM_MODEL",
    "LLM_THREAD_ID",
    "OPENAI_API_KEY",
    "AISDLC_PROJECT_NAME",
    "AISDLC_FORK_OWNER",
    "AISDLC_CORRECTION_BUDGET",
    "AISDLC_CORRECTION_MINUTES",
)


def _what_a_fresh_interpreter_sees_after_importing(the_conftest: Path) -> str:
    """What a new interpreter knows about a deployment's settings, having imported that file.

    **A subprocess and not an import in this process.** Two reasons, and the first is the
    whole test: this process has already imported that conftest, so importing it again is a
    no-op and the answer would be whatever this process did at collection time — which is the
    very thing in question. The second is that a failing import would otherwise take the
    default suite down with it, and a suite that cannot run to tell you a conftest is broken
    cannot report the break.
    """
    an_environment_without_a_deployment = {
        a_setting: ""
        for a_setting in os.environ
        if a_setting not in THE_SETTINGS_A_DOTFILE_IS_READ_FOR
    }

    a_question = (
        "import importlib.util, sys;"
        f"spec = importlib.util.spec_from_file_location('the_real_tier', r'{the_conftest}');"
        "module = importlib.util.module_from_spec(spec);"
        "sys.modules['the_real_tier'] = module;"
        "spec.loader.exec_module(module);"
        "import os;"
        f"print([a_setting for a_setting in {THE_SETTINGS_A_DOTFILE_IS_READ_FOR!r}"
        " if os.environ.get(a_setting)])"
    )

    answered = subprocess.run(
        [sys.executable, "-c", a_question],
        capture_output=True,
        text=True,
        cwd=THE_REPOSITORY_ROOT,
        env=an_environment_without_a_deployment,
        check=False,
    )

    assert answered.returncode == 0, (
        f"importing {the_conftest.name} raised, so the question could not be asked: "
        f"{answered.stderr.strip()}"
    )
    return answered.stdout.strip()


def test_importing_the_real_tier_does_not_load_a_deployment_dotfile() -> None:
    assert THE_REAL_TIERS_CONFTEST.is_file(), (
        f"{THE_REAL_TIERS_CONFTEST} is not there, so this is checking that a file which is not "
        "imported is not read at import time — a green tick about nothing"
    )

    what_it_came_to_know = _what_a_fresh_interpreter_sees_after_importing(THE_REAL_TIERS_CONFTEST)

    assert what_it_came_to_know == "[]", (
        f"importing the real tier's conftest put {what_it_came_to_know} into the environment. "
        "Pytest imports a conftest in order to read the markers of the tests it is about to "
        "deselect, so a dotfile loaded there is loaded by every default run on this machine — "
        "and a default run whose tests are guarded by `skipif` on those settings stops "
        "skipping. That is how a suite documented as needing no credential and no network came "
        "to clone a repository and pay a model. The loading belongs inside a fixture, which a "
        "deselected test never asks for."
    )
