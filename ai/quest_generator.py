import json

from ai.ollama_client import ask_ollama
from ai.image_classifier import classify_sprite, DEFAULT_VIBE
from ai.audio_classifier import classify_cry, DEFAULT_SOUND
from pokemon.data import sprite_url, DEX_NUMBER


def _team_names(team: list[dict]) -> list[str]:
    """
    Team members are stored as {"name", "level", "exp", "friendship"}
    dicts (see database/player.py), but quest prompts only ever need
    the species names - this pulls just those out, in order.
    """
    return [pokemon["name"] for pokemon in team]


def _team_vibe(team: list[dict]) -> str:
    """
    Classify the "vibe" of the player's first team member's sprite
    (see ai/image_classifier.py), so quest prompts can be flavoured by
    how the team's lead Pokémon actually looks, not just their name.

    Returns DEFAULT_VIBE if the team is empty or classification fails
    for any reason - this is a flavour add-on, never something quest
    generation depends on to function.
    """
    if not team:
        return DEFAULT_VIBE

    url = sprite_url({"name": team[0]["name"]})
    return classify_sprite(url)


def _team_sound(team: list[dict]) -> str:
    """
    Classify the "sound" of the player's first team member's cry (see
    ai/audio_classifier.py) - the project's third orchestrated model,
    operating on AUDIO rather than the text (Llama) and image (CLIP)
    domains already used above.

    Returns DEFAULT_SOUND if the team is empty, the species has no
    known Pokédex number (shouldn't normally happen - DEX_NUMBER covers
    all 151 species), or classification fails for any reason - the
    same "flavour add-on, never load-bearing" approach as
    _team_vibe() above.
    """
    if not team:
        return DEFAULT_SOUND

    dex_number = DEX_NUMBER.get(team[0]["name"])
    if dex_number is None:
        return DEFAULT_SOUND

    return classify_cry(dex_number)


def generate_quest(location: str, player_level: int, team: list[dict]):
    """
    Generate the FIRST step of a quest.

    Returns a (quest, vibe, sound) tuple. The caller
    (commands/explore.py) hangs onto `vibe` and `sound` and reuses them
    for every later step in the same quest chain via continue_quest(),
    rather than re-classifying the team's sprite/cry on every single
    button press - both describe the player's lead Pokémon, which
    doesn't change mid-quest, so there's no reason to redo that work.
    """
    vibe = _team_vibe(team)
    sound = _team_sound(team)
    lead = team[0]["name"] if team else "the player's Pokémon"

    # TEMPORARY: prints the classified vibe/sound to the bot's own
    # console so you can confirm, while testing, that both classifiers
    # are actually running inside the live bot (not just a standalone
    # test script). Safe to delete once you've confirmed it works.
    print(f"[image_classifier/audio_classifier] lead={lead!r} team={_team_names(team)} -> vibe='{vibe}', sound='{sound}'")

    prompt = f"""
You are creating a Pokémon-inspired RPG quest.

This quest is about {lead}, the player's LEAD Pokémon accompanying
them on this trip - it is the only Pokémon that should appear in the
story. Do not invent or mention any other Pokémon by name.

Player:
- Level: {player_level}
- Location: {location}
- Lead Pokémon: {lead}
- {lead}'s sprite gives off a "{vibe}" vibe (from an image classifier).
- {lead}'s cry sounds "{sound}" (from an audio classifier).

Return ONLY valid JSON.

Example JSON format only, do not copy the content:

{{
    "title": "A Location-Specific Quest Title",
    "scene": "A short scene based on the chosen location.",
    "npc": "A suitable character for the area.",
    "objective": "A clear objective related to the scene.",
    "choices": [
        "First possible action",
        "Second possible action",
        "Third possible action"
    ]
}}

Rules:
- Under 100 words.
- Exactly 3 choices.
- No markdown.
- No explanations.
- No code blocks.
- Make the quest theme match the location.
- Let {lead}'s vibe and cry sound together subtly influence the tone of the scene and NPC.
- {lead} is the only Pokémon in this story - do not name any other Pokémon.
- Vary the NPC, objective, and problem each time.
"""

    response = ask_ollama(prompt)

    try:
        quest = json.loads(response)
    except Exception:
        quest = {
            "title": "Unknown Encounter",
            "scene": "Something unexpected happened.",
            "npc": "Nobody is nearby.",
            "objective": "Continue exploring.",
            "choices": [
                "Look around",
                "Walk away",
                "Rest"
            ]
        }

    return quest, vibe, sound


def continue_quest(
    location: str,
    player_level: int,
    team: list[dict],
    vibe: str,
    sound: str,
    history: list[str],
    choice_taken: str,
    is_final: bool,
):
    """
    Generate the NEXT step of an already-started quest, after the
    player picks one of the previous step's choices.

    `history` is the list of scene texts generated so far in this
    specific quest chain, so the model has continuity instead of
    inventing an unrelated scene each time - it's given the whole
    story so far and asked to continue it, not start over.

    Whether this is the LAST step is decided by the caller
    (commands/explore.py picks a fixed chain length of 2-3 steps when
    the quest starts), not by the model - the same principle used
    throughout this project: the AI generates content, deterministic
    code controls structure. When `is_final` is True, the model is
    told to resolve the story and return no further choices.
    """
    lead = team[0]["name"] if team else "the player's Pokémon"
    history_text = "\n".join(f"- {s}" for s in history) if history else "(nothing yet)"

    if is_final:
        choice_instruction = (
            "This is the FINAL step of the quest. Resolve the story "
            'based on the choice below. Return an empty "choices" list '
            "([]) - the quest ends after this."
        )
    else:
        choice_instruction = (
            'This is NOT the final step. Return exactly 3 new entries '
            'in "choices" for what the player can do next.'
        )

    prompt = f"""
You are continuing a Pokémon-inspired RPG quest that is already in progress.

This quest is about {lead}, the player's LEAD Pokémon - it is the only
Pokémon in the story. Do not introduce any other Pokémon by name.

Player:
- Level: {player_level}
- Location: {location}
- Lead Pokémon: {lead}
- {lead}'s vibe: "{vibe}"
- {lead}'s cry sounds: "{sound}"

Story so far:
{history_text}

The player just chose: "{choice_taken}"

{choice_instruction}

Return ONLY valid JSON in this shape:

{{
    "scene": "What happens next, following directly from the player's choice.",
    "npc": "Who (if anyone) is involved now - can be an earlier NPC or a new one.",
    "objective": "The player's current objective, or how the quest concluded if this is final.",
    "choices": ["...", "...", "..."]
}}

Rules:
- Under 80 words.
- No markdown, no explanations, no code blocks.
- Stay consistent with the story so far - do not contradict earlier events.
- {lead} is the only Pokémon in this story - do not name any other Pokémon.
"""

    response = ask_ollama(prompt)

    try:
        return json.loads(response)
    except Exception:
        return {
            "scene": "The moment passes, and the path ahead grows quiet.",
            "npc": "",
            "objective": "The quest ends here.",
            "choices": [],
        }
