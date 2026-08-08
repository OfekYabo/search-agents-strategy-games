"""Renders the report from analysis.json. Computes nothing.

Two kinds of content live here and they are kept strictly apart:

  - Generated: every table and figure, derived from analysis.json. Same input,
    byte-identical output, so the report can be regenerated for any run.
  - Interpretive: hand-written prose in docs/report/commentary.md, merged in
    by section id.

The generated report is disposable and must never be hand-edited. Prose lives
in the sidecar precisely so that regenerating is unconditionally safe - if
prose lived in the generated file, regeneration would either destroy it or
need round-trip parsing of a file that is supposed to be write-only.
"""
import re
import sys

# Report order. Adding a section here without adding its rendering, or
# renaming one without updating commentary.md, is caught by
# validate_commentary rather than silently dropping prose.
SECTION_IDS = (
    "overview",
    "method",
    "results",
    "budget-response",
    "search-volume",
    "instrument-validation",
    "game-characteristics",
    "limitations",
)

_SECTION_RE = re.compile(r"^<!--\s*section:\s*([a-z0-9-]+)\s*-->\s*$",
                         re.MULTILINE)


def parse_commentary(text):
    # type: (str) -> dict
    """Split the sidecar into {section_id: body}. A body consisting only of
    a TODO marker is treated as empty, so a placeholder reads as a gap rather
    than as prose."""
    sections = {}
    parts = _SECTION_RE.split(text)
    # parts[0] is the preamble before any marker; then (id, body) pairs.
    for index in range(1, len(parts) - 1, 2):
        body = parts[index + 1].strip()
        if body == "<!-- TODO -->":
            body = ""
        sections[parts[index]] = body
    return sections


def validate_commentary(sections, known_ids):
    # type: (dict, tuple) -> None
    unknown = sorted(set(sections) - set(known_ids))
    if unknown:
        raise ValueError(
            "commentary.md has sections matching no report slot: %s. "
            "Rename them or remove them - a renamed report section must not "
            "silently orphan its prose." % ", ".join(unknown))


def commentary_for(sections, section_id):
    # type: (dict, str) -> str
    body = sections.get(section_id, "")
    if not body:
        return "> **[COMMENTARY NEEDED: %s]**" % section_id
    return body
