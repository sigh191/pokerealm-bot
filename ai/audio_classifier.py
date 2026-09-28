"""
Audio-based "cry" classifier for Pokémon cries.

This is the project's THIRD orchestrated AI model. The CM3020 template
this project is built on ("Orchestrating AI models to achieve a goal")
requires at least three pre-trained models, each operating on a
different domain/data space - its own example being "text, image and
audio". Llama 3.2 (ai/ollama_client.py) already covers TEXT, and CLIP
(ai/image_classifier.py) already covers IMAGE - this file adds the
third and final domain, AUDIO, by classifying each Pokémon's short
"cry" sound clip. With all three in place, the project meets that
requirement rather than only two of the three domains.

It uses CLAP (laion/clap-htsat-unfused) through Hugging Face's
"zero-shot-audio-classification" pipeline - the audio equivalent of
the "zero-shot-image-classification" pipeline ai/image_classifier.py
already uses for CLIP. Exactly like CLIP, CLAP was never specifically
trained to recognise "aggressive" or "playful" sounds - it was trained
to match audio clips against arbitrary text descriptions in general,
so it can score a cry clip against any list of labels we give it at
call time, with no extra training needed on our side. This keeps the
same "zero-shot classification with our own vocabulary" technique used
for both AI components that only read data (as opposed to Llama, which
generates it).

Cry audio files come from the PokeAPI community "cries" project on
GitHub (https://github.com/PokeAPI/cries), a public, free-to-use
collection of one short .ogg cry per Pokémon species, named by
National Pokédex number. pokemon/data.py's DEX_NUMBER dict (added
earlier for /box's dex-order sorting) already maps every species name
to that same number, so no new ID mapping is needed here.

Nothing in this file touches the game engine or player data - like
ai/image_classifier.py, it only ever returns a plain string, which the
caller (ai/quest_generator.py) decides what to do with. That keeps the
same hybrid separation used everywhere in the project: AI components
produce flavour/content, nothing here can affect game state directly.
"""

from functools import lru_cache
from io import BytesIO

import librosa
import requests

# Where PokeAPI's community cries project hosts one .ogg file per
# National Pokédex number, e.g. .../25.ogg for Pikachu's cry.
CRY_URL_TEMPLATE = "https://raw.githubusercontent.com/PokeAPI/cries/main/cries/pokemon/latest/{dex_number}.ogg"

# CLAP (like most audio models) expects audio sampled at one specific
# rate - 48,000 samples per second is what this model was trained on -
# so the downloaded clip is resampled to match regardless of whatever
# rate the source .ogg file happens to be encoded at.
CLAP_SAMPLE_RATE = 48_000

# The set of "sound" labels a cry can be matched against - a separate
# vocabulary from ai/image_classifier.py's VIBE_LABELS (sight), since a
# Pokémon's cry can give a different impression than its sprite (e.g.
# Cubone's sprite reads as "cute", but its cry could read as
# "mournful"). CLAP just scores the clip against whichever labels are
# passed in, so this list can be tuned freely without retraining
# anything.
SOUND_LABELS = [
    "aggressive and sharp",
    "calm and gentle",
    "high-pitched and playful",
    "deep and powerful",
    "eerie and unsettling",
    "energetic and excitable",
]

# Used whenever classification fails or hasn't been attempted, so the
# rest of the code never has to special-case "no sound available".
DEFAULT_SOUND = "unusual"

# The zero-shot-audio-classification pipeline doesn't score a label on
# its own - it builds a full sentence by dropping each label into this
# template (replacing "{}"), then compares THAT sentence's meaning
# against the audio. The pipeline's own default template is "This is a
# sound of {}." - dropping our labels above into that produces
# ungrammatical, meaningless sentences like "This is a sound of
# aggressive and sharp." (missing a noun), which the model can't
# reliably match against real audio. This template is written to fit
# how SOUND_LABELS above are actually phrased (adjective descriptions,
# not nouns), so it always produces a real sentence, e.g. "This cry
# sounds aggressive and sharp."
HYPOTHESIS_TEMPLATE = "This cry sounds {}."


@lru_cache(maxsize=1)
def _get_audio_classifier():
    """
    Load (once) and cache the CLAP zero-shot audio classification
    pipeline.

    Just like _get_classifier() in ai/image_classifier.py, this import
    is deliberately kept inside the function rather than at the top of
    the file - transformers/torch are fairly large dependencies, and
    importing them only when a classification is actually requested
    keeps bot startup fast if this feature is ever disabled or not yet
    installed.

    lru_cache(maxsize=1) means the model is only loaded into memory the
    first time this is called - every later call during the bot's
    lifetime reuses the same loaded model instead of reloading it from
    disk.
    """
    from transformers import pipeline

    return pipeline(
        "zero-shot-audio-classification",
        model="laion/clap-htsat-unfused",
    )


def classify_cry(dex_number: int, labels: list[str] = SOUND_LABELS) -> str:
    """
    Download the cry clip for the species at `dex_number` and return
    whichever label in `labels` CLAP scores highest against it.

    Returns DEFAULT_SOUND if anything goes wrong - a network error, a
    corrupt/undecodable file, an unknown dex number, or the model
    failing to load - so an audio classifier problem can never crash
    quest generation. This mirrors classify_sprite()'s fallback in
    ai/image_classifier.py exactly.
    """
    try:
        url = CRY_URL_TEMPLATE.format(dex_number=dex_number)
        response = requests.get(url, timeout=15)
        response.raise_for_status()

        # librosa.load decodes the compressed .ogg bytes into a plain
        # waveform (a NumPy array of samples) and resamples it to
        # CLAP_SAMPLE_RATE in the same step - the pipeline below
        # expects a raw waveform at that rate, not a compressed audio
        # file.
        waveform, _ = librosa.load(BytesIO(response.content), sr=CLAP_SAMPLE_RATE)

        classifier = _get_audio_classifier()
        results = classifier(
            waveform,
            candidate_labels=labels,
            hypothesis_template=HYPOTHESIS_TEMPLATE,
        )

        # results is a list of {"label": ..., "score": ...} dicts,
        # sorted highest score first - the same shape
        # ai/image_classifier.py already relies on for CLIP.
        return results[0]["label"]

    except Exception:
        return DEFAULT_SOUND
