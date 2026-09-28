"""
Tests for ai/quest_generator.py - specifically the parts of it that
are ordinary deterministic Python, not the AI call itself.

This project's own workplan (see claude/rubric-gap-analysis.md and the
draft report's Table 6.1) explicitly calls out adding tests for this
module's "JSON parsing/fallback logic" - what happens when Llama
returns something that isn't valid JSON (which DOES happen sometimes
with real models, hence the fallback existing at all in
generate_quest() and continue_quest() in the first place).

What this file deliberately does NOT test: it never calls the real
ask_ollama() (which needs a real, running Ollama server) or the real
classify_sprite()/classify_cry() (which need real network access and
the CLIP/CLAP models downloaded) - those are mocked out with
monkeypatch so these tests run in under a second, anywhere, without
needing Ollama or the internet. ai/image_classifier.py and
ai/audio_classifier.py's OWN behaviour is exercised separately (see
this session's manual test_audio.py-style checks for the audio
classifier); this file is only about what quest_generator.py itself
does with whatever those pieces return.
"""

import json

import ai.quest_generator as quest_generator


def _stub_classifiers(monkeypatch, vibe="fiery", sound="deep and powerful"):
    """Replace the real image/audio classifiers with fixed, fast fake ones for one test."""
    monkeypatch.setattr(quest_generator, "_team_vibe", lambda team: vibe)
    monkeypatch.setattr(quest_generator, "_team_sound", lambda team: sound)


SAMPLE_TEAM = [{"name": "Charmander", "level": 5, "exp": 0, "friendship": 0}]


# --- _team_vibe() / _team_sound() fallbacks --------------------------------

def test_team_vibe_falls_back_to_default_when_team_is_empty():
    assert quest_generator._team_vibe([]) == quest_generator.DEFAULT_VIBE


def test_team_sound_falls_back_to_default_when_team_is_empty():
    assert quest_generator._team_sound([]) == quest_generator.DEFAULT_SOUND


def test_team_sound_falls_back_to_default_for_an_unrecognised_species():
    # DEX_NUMBER covers all 151 real species, so this shouldn't happen
    # in practice - but if it ever did (a typo in a species name
    # somewhere), this should degrade gracefully rather than crash.
    unknown_team = [{"name": "Not A Real Pokemon", "level": 1, "exp": 0, "friendship": 0}]
    assert quest_generator._team_sound(unknown_team) == quest_generator.DEFAULT_SOUND


# --- generate_quest() -------------------------------------------------------

def test_generate_quest_returns_the_models_json_when_it_is_valid(monkeypatch):
    _stub_classifiers(monkeypatch)
    valid_response = json.dumps({
        "title": "A Fiery Encounter",
        "scene": "Something happens.",
        "npc": "A trainer",
        "objective": "Do the thing",
        "choices": ["a", "b", "c"],
    })
    monkeypatch.setattr(quest_generator, "ask_ollama", lambda prompt: valid_response)

    quest, vibe, sound = quest_generator.generate_quest("Cinnabar Island", 5, SAMPLE_TEAM)

    assert quest["title"] == "A Fiery Encounter"
    assert quest["choices"] == ["a", "b", "c"]
    assert vibe == "fiery"
    assert sound == "deep and powerful"


def test_generate_quest_falls_back_to_a_default_quest_on_broken_json(monkeypatch):
    _stub_classifiers(monkeypatch)
    # Real models occasionally wrap their JSON in commentary or
    # markdown code fences despite being told not to - this simulates
    # that kind of unparseable response.
    monkeypatch.setattr(quest_generator, "ask_ollama", lambda prompt: "Sure! Here's your quest: ```not json```")

    quest, vibe, sound = quest_generator.generate_quest("Cinnabar Island", 5, SAMPLE_TEAM)

    assert quest["title"] == "Unknown Encounter"
    assert quest["choices"] == ["Look around", "Walk away", "Rest"]
    # The fallback should still carry the real classified vibe/sound -
    # a broken response from Llama shouldn't also break the parts of
    # generate_quest() that worked fine.
    assert vibe == "fiery"
    assert sound == "deep and powerful"


def test_generate_quest_prompt_includes_both_vibe_and_sound(monkeypatch):
    # A regression check for the three-model orchestration itself:
    # both the image classifier's vibe AND the audio classifier's
    # sound need to actually reach the prompt sent to Llama, not just
    # be computed and thrown away.
    _stub_classifiers(monkeypatch, vibe="spooky", sound="eerie and unsettling")
    captured = {}

    def fake_ask_ollama(prompt):
        captured["prompt"] = prompt
        return json.dumps({"title": "t", "scene": "s", "npc": "n", "objective": "o", "choices": []})

    monkeypatch.setattr(quest_generator, "ask_ollama", fake_ask_ollama)

    quest_generator.generate_quest("Lavender Town", 5, SAMPLE_TEAM)

    assert "spooky" in captured["prompt"]
    assert "eerie and unsettling" in captured["prompt"]


# --- continue_quest() -------------------------------------------------------

def test_continue_quest_returns_the_models_json_when_it_is_valid(monkeypatch):
    valid_response = json.dumps({
        "scene": "The story continues.",
        "npc": "Same trainer",
        "objective": "Finish the quest",
        "choices": [],
    })
    monkeypatch.setattr(quest_generator, "ask_ollama", lambda prompt: valid_response)

    result = quest_generator.continue_quest(
        location="Cinnabar Island",
        player_level=5,
        team=SAMPLE_TEAM,
        vibe="fiery",
        sound="deep and powerful",
        history=["An earlier scene."],
        choice_taken="Look around",
        is_final=True,
    )

    assert result["scene"] == "The story continues."


def test_continue_quest_falls_back_to_a_default_ending_on_broken_json(monkeypatch):
    monkeypatch.setattr(quest_generator, "ask_ollama", lambda prompt: "{not valid json")

    result = quest_generator.continue_quest(
        location="Cinnabar Island",
        player_level=5,
        team=SAMPLE_TEAM,
        vibe="fiery",
        sound="deep and powerful",
        history=["An earlier scene."],
        choice_taken="Look around",
        is_final=True,
    )

    # Exact match against continue_quest()'s own documented fallback -
    # if this fallback text is ever changed, this test is a deliberate
    # reminder to update it on purpose, not by accident.
    assert result == {
        "scene": "The moment passes, and the path ahead grows quiet.",
        "npc": "",
        "objective": "The quest ends here.",
        "choices": [],
    }
