#!/usr/bin/env python3
"""Read-only validation for the two approved Faye Maxwell narrative briefs."""

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import wave


HERE = Path(__file__).resolve().parent
STEMS = ["brief-01-introduction", "brief-02-exit"]
SPEAKER = "Faye Maxwell, SOC supervisor for Operation Silent Ridge"
INTRO_AUDIO = HERE / "recordings" / "brief-01-introduction.wav"
INTRO_AUDIO_SHA256 = "6b5a471c510c29081cee1851546d513f88117bc93ba53b1f6121aea4c31eb92a"


def check(repo: Path) -> int:
    failures: list[str] = []

    def need(value: object, message: str) -> None:
        if not value:
            failures.append(message)

    def hits(text: str, term: str) -> bool:
        return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I) is not None

    data = json.loads((HERE / "briefs.json").read_text(encoding="utf-8"))
    audit = json.loads((HERE / "spoiler-audit.json").read_text(encoding="utf-8"))
    echoes = json.loads((HERE / "ANNOUNCE-TEXTS.json").read_text(encoding="utf-8"))
    provenance = json.loads((HERE / "SOURCE-PROVENANCE.json").read_text(encoding="utf-8"))

    need([brief["stem"] for brief in data] == STEMS, "exactly two ordered assets")
    need([brief["id"] for brief in data] == ["01", "02"], "ordered IDs")
    need(set(echoes) == set(STEMS), "exactly two announcement echoes")
    need({path.stem for path in (HERE / "spoken").glob("*.txt")} == set(STEMS), "exactly two canonical spoken files")
    need({path.stem for path in HERE.glob("brief-*.md")} == set(STEMS), "exactly two production sheets")

    media = [path for path in HERE.rglob("*") if path.suffix.casefold() in {".wav", ".mp3", ".ogg", ".m4a", ".flac"}]
    prohibited_renderers = [path for path in HERE.rglob("*.py") if path.name != "validate.py"]
    need(media == [INTRO_AUDIO], "only the unchanged introduction WAV is committed")
    need(hashlib.sha256(INTRO_AUDIO.read_bytes()).hexdigest() == INTRO_AUDIO_SHA256, "introduction audio hash")
    with wave.open(str(INTRO_AUDIO), "rb") as audio:
        need(audio.getnchannels() == 1, "introduction audio is mono")
        need(audio.getsampwidth() == 2, "introduction audio is PCM-16")
        need(audio.getframerate() == 48000, "introduction audio is 48 kHz")
        need(audio.getnframes() == 5464320, "introduction audio frame count")
    need(provenance["included_audio"]["sha256"] == INTRO_AUDIO_SHA256, "audio provenance hash")
    need(not prohibited_renderers, "no voice-rendering scripts are committed")
    need(not (HERE.parent / "audio-voice-current").exists(), "superseded voice-render directory is absent")
    need(not (HERE.parent / "soc-manager-three-briefs").exists(), "superseded three-brief directory is absent")

    answer_key = (repo / audit["answer_key_relative_path"]).read_text(encoding="utf-8")
    answers: list[str] = []
    for line in answer_key.splitlines():
        if re.match(r"\| T\d\d \| `", line):
            answers.extend(re.findall(r"`([^`]+)`", line.split("|")[2]))
    need(len(answers) == 80, "80 answer-key entries")

    for brief in data:
        stem = brief["stem"]
        text = brief["text"]
        label = stem + ": "
        spoken = (HERE / "spoken" / f"{stem}.txt").read_text(encoding="utf-8")
        sheet = (HERE / f"{stem}.md").read_text(encoding="utf-8")
        need(spoken == text, label + "canonical spoken parity")
        need(sheet.split("## Script\n\n", 1)[1].split("\n## Full written echo", 1)[0] == text, label + "production-sheet parity")
        need(echoes[stem] == " ".join(text.split()), label + "announcement echo parity")
        need(len(echoes[stem]) <= 8000, label + "announcement text limit")
        need(hashlib.sha256(text.encode()).hexdigest() == brief["text_sha256"], label + "source hash")
        need(provenance["narration_text_sha256"][stem] == brief["text_sha256"], label + "provenance hash")
        need(brief["speaker"] == SPEAKER, label + "speaker identity")
        words = len(re.findall(r"\b[\w]+(?:[-’'][\w]+)*\b", text))
        need(words == brief["words"], label + "word count")
        need(round(words / 140 * 60) == brief["estimated_seconds_at_140_wpm"], label + "duration estimate")
        need("[" not in text and "]" not in text, label + "no stage tags")
        for term in audit["prohibited_spoken_meta_terms"]:
            need(not hits(text, term), label + "unwanted spoken meta term " + term)

    intro, conclusion = data[0], data[1]
    intro_text, conclusion_text = intro["text"], conclusion["text"]
    allowed = set(audit["intro_allowed_answer_literals"])
    for term in set(answers) - allowed:
        need(not hits(intro_text, term), "introduction protected answer " + term)
    for term in audit["intro_forbidden_literals"]:
        need(term.casefold() not in intro_text.casefold(), "introduction forbidden literal " + term)
    for term in audit["conclusion_required_literals"]:
        need(term.casefold() in conclusion_text.casefold(), "conclusion required literal " + term)

    need(intro["trigger_kind"] == "agenda" and intro["ticket"] is None and not intro["requires"], "introduction is an independent opening cue")
    need(conclusion["trigger_kind"] == "completion" and conclusion["ticket"] == "T20", "conclusion is completion-gated at T20")
    need(conclusion["requires"] == ["20 of 20 ticket stages complete", "final assessment published"], "conclusion requires full completion and publication")
    need(intro_text.rstrip().endswith("patrol decisions stay with them."), "introduction matches the organizer-provided ending")
    need("I'm Faye Maxwell, SOC supervisor" in conclusion_text, "conclusion identifies Faye Maxwell")
    need("limited disclosure is confirmed" in conclusion_text.casefold(), "conclusion states the supported outcome")
    need("roster request was denied" in conclusion_text.casefold() and "zero bytes" in conclusion_text.casefold(), "conclusion preserves denied-roster limit")
    need("cannot establish who controlled" in conclusion_text.casefold(), "conclusion preserves controller uncertainty")
    need("WS-31 also remains unresolved" in conclusion_text, "conclusion preserves WS-31 uncertainty")
    need("rotate the CEDAR" in conclusion_text and "revoke session S-41" in conclusion_text, "conclusion states immediate containment")

    class Links(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.links: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            for key, value in attrs:
                if key == "href" and value:
                    self.links.append(value)

    player = (HERE / "player.html").read_text(encoding="utf-8")
    need(not re.search(r"\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(", player), "cue desk stays offline")
    links = Links()
    links.feed(player)
    for target in links.links:
        need(not target.startswith(("https:", "http:")), "cue-desk reference stays local")
        need((HERE / target.split("#")[0]).exists(), "cue-desk link exists: " + target)

    if failures:
        for failure in failures:
            print("FAIL:", failure)
        return 1

    print("PASS: exactly two approved Faye Maxwell scripts and one unchanged introduction WAV; no renderer or outro media is committed.")
    print("PASS: introduction is spoiler-safe; conclusion is completion-gated and matches the final assessment.")
    print("PASS: text, JSON, sheets, echoes, hashes, counts, provenance and cue-desk links agree.")
    print("Estimates: " + ", ".join(f"{brief['words']} words / {brief['estimated_seconds_at_140_wpm']} s" for brief in data) + ".")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=HERE.parents[2])
    raise SystemExit(check(parser.parse_args().repo.resolve()))
