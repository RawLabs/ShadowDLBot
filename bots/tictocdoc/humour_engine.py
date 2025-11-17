"""Absurd but deterministic diagnosis generator for TicTocDoc."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Mapping, Sequence


SYMPTOMS: Sequence[str] = (
    "dopamine overclock",
    "chronically elevated cringe markers",
    "mild existential static",
    "spontaneous meme echo",
    "post-irony vertigo",
    "attention span vapor lock",
    "rhythmic eyebrow fatigue",
    "parasitic dance memory",
)

TREATMENTS: Sequence[str] = (
    "twelve minute meme fast",
    "controlled dopamine detox",
    "ocular debugging session",
    "guided cringe breathing",
    "emergency vibe recalibration",
    "micro-dose of analog silence",
    "retro internet inoculation",
)

SIDE_EFFECTS: Sequence[str] = (
    "temporary clarity",
    "uncontrollable sighing",
    "mild nostalgia discharge",
    "questioning all life choices",
    "sudden urge to touch grass",
    "migratory eyebrow twitch",
)

DOCTOR_ACTIONS: Sequence[str] = (
    "triaged",
    "sanitized",
    "quarantined",
    "diagnosed",
    "stabilized",
    "contained",
)

CLINICAL_NOTES: Sequence[str] = (
    "prognosis remains whimsically guarded",
    "patient refuses to stop vibing",
    "further observation recommended under dim lighting",
    "subject may spontaneously narrate own life",
    "keep sharp objects away from the comment section",
)

TEMPLATES: Sequence[str] = (
    (
        "TicTocDoc Diagnosis\n"
        "Specimen: {video_id} ({action})\n"
        "\n"
        "Findings:\n"
        " • {symptom_1}\n"
        " • {symptom_2}\n"
        " • {symptom_3}\n"
        "Treatment: {treatment}\n"
        "Side effects: {side_effect}"
    ),
    (
        "Patient File {video_id}\n"
        "Status: {symptom_1}\n"
        "Complication: {symptom_2}\n"
        "Protocol: {treatment}\n"
        "Note: {note}"
    ),
    (
        "Clinical Memo\n"
        "Feed tagged: {video_id}\n"
        "Primary activity: {symptom_1}\n"
        "Secondary drift: {symptom_2}\n"
        "Countermeasure: {treatment}\n"
        "Aftermath: {side_effect}"
    ),
    (
        "Neural Scan Report\n"
        "{action} sequence {video_id}\n"
        "Alerts:\n"
        " - {symptom_1}\n"
        " - {symptom_2}\n"
        " - {symptom_3}\n"
        "Prescription: {treatment}\n"
        "Warning: {side_effect}"
    ),
    (
        "Clinic Brief\n"
        "TikTok flagged for {symptom_1}\n"
        "Risk driver: {symptom_2}\n"
        "Immediate care: {treatment}\n"
        "Projected fallout: {side_effect}"
    ),
)


@dataclass(frozen=True)
class TikTokContext:
    """Subset of TikTok info passed into the humour engine."""

    video_id: str = "unknown"
    title: str | None = None
    uploader: str | None = None


def _choose(seq: Sequence[str]) -> str:
    return random.choice(tuple(seq))


def generate_diagnosis(context: Mapping[str, str | None] | TikTokContext | None = None) -> str:
    """Return a formatted diagnosis string."""

    ctx = TikTokContext(
        video_id=_value_or(context, "video_id", "unknown"),
        title=_value_or(context, "title"),
        uploader=_value_or(context, "uploader"),
    )

    template = _choose(TEMPLATES)
    replacements = {
        "action": _choose(DOCTOR_ACTIONS),
        "symptom_1": _choose(SYMPTOMS),
        "symptom_2": _choose(SYMPTOMS),
        "symptom_3": _choose(SYMPTOMS),
        "treatment": _choose(TREATMENTS),
        "side_effect": _choose(SIDE_EFFECTS),
        "note": _choose(CLINICAL_NOTES),
        "video_id": ctx.video_id or "unknown",
    }

    if ctx.title:
        replacements["note"] = f"{ctx.title!r} still echoing in triage"

    return template.format(**replacements)


def _value_or(source: Mapping[str, str | None] | TikTokContext | None, key: str, default: str | None = None) -> str | None:
    if source is None:
        return default
    if isinstance(source, TikTokContext):
        return getattr(source, key)
    return source.get(key, default)
