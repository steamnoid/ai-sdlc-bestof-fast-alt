"""How to name a file, said once, because six prompts need saying it.

**Every artifact this pipeline produces writes file paths, and until now no prompt said where a
path starts.** So a model reads an inspection showing `src/aisdlc/graph/router.py` and writes
`graph/router.py` — because that is the import path, and the import path is what a person thinks
in when they are talking about a module.

**This is a convention rather than a slip, and this repository has produced it twice.** The
implementer asked for `.gitignore` was answered `gitignore`. The discovery agent naming
components produced `aisdlc/agents/what_an_agent_judged.py` for a file that really exists at
`src/aisdlc/agents/what_an_agent_judged.py`. Every one is a real file of this repository, named
from the inside out. **Loosening a path matcher would have stopped the tier noticing**, which is
the opposite of fixing it — so the sentence is here rather than the matcher.

**And the second half is the half that actually works.** "Write it from the root" asks a model to
reconstruct a path it was shown; "copy it out of the inspection" asks it to copy one. The
inspection is the one place in this system where a path is guaranteed to be exactly right,
because it was produced by walking the clone rather than by reading a name.

**So the sentence lives here and the prompts build it from here.** Six prompts each carrying
their own wording would drift, and then two of the six would be the ones that are wrong — and
nothing would say which two.
"""

from __future__ import annotations


def the_rule_about_naming_a_file() -> str:
    """The one paragraph every prompt whose answer carries a path puts into itself.

    **Two instructions and not one, because the second is the one that works.** Asking a model to
    write a path from the root asks it to reconstruct something it was handed; asking it to copy
    asks it to transcribe. The first is a rule to follow and the second is a thing to do, and a
    model given both does the second.

    **And it says not to invent a file**, which is a separate failure with the same shape: a
    path the inspection does not show is a link to nothing, and `PlannedFileNotFoundError` catches
    it after the fact rather than the model noticing it while it still has the inspection in
    front of it.
    """
    return (
        "\nWrite every file path from the root of the repository, with every directory on the\n"
        "way, and copy it out of the inspection above rather than writing it out again. A path\n"
        "like graph/router.py is a module's import name rather than a path a reader can open;\n"
        "what a reader opens is src/aisdlc/graph/router.py. Do not shorten a path to its last\n"
        "few directories, and do not invent a file the inspection does not show you.\n"
    )
