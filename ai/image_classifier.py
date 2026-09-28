"""
Image-based "vibe" classifier for Pokémon sprites.

This is the project's second orchestrated AI model (see the CM3020
template discussion in the report). It operates on IMAGE data, not
text, which is what makes it a genuinely different model from the
Llama 3.2 text-generation model in ai/ollama_client.py - the template
asks for pre-trained models operating on different domains/data
spaces, and text-in/text-out twice over would not satisfy that.

It uses CLIP (openai/clip-vit-base-patch32) through Hugging Face's
"zero-shot-image-classification" pipeline. "Zero-shot" means CLIP was
never specifically trained to recognise "spooky" or "cute" Pokémon -
it was trained to match images against arbitrary text descriptions in
general, so it can score a sprite against any list of labels we give
it at call time, with no extra training needed on our side.

Nothing in this file touches the game engine or player data - like
ai/ollama_client.py, it only ever returns a plain string, which the
caller (ai/quest_generator.py) decides what to do with. That keeps the
same hybrid separation the rest of the project uses: AI components
produce flavour/content, nothing here can affect game state directly.
"""

from functools import lru_cache
from io import BytesIO

import requests
from PIL import Image

# The set of "vibe" labels a sprite can be matched against. CLIP just
# scores the image against whichever labels are passed in, so this
# list can be tuned freely without retraining anything.
VIBE_LABELS = [
    "spooky",
    "cute",
    "fierce",
    "fiery",
    "aquatic",
    "electric",
    "ancient and mysterious",
    "gentle and forest-dwelling",
]

# Used whenever classification fails or hasn't been attempted, so the
# rest of the code never has to special-case "no vibe available".
DEFAULT_VIBE = "mysterious"


@lru_cache(maxsize=1)
def _get_classifier():
    """
    Load (once) and cache the CLIP zero-shot image classification
    pipeline.

    This import is deliberately kept inside the function rather than
    at the top of the file: transformers/torch are fairly large
    dependencies, and importing them only when a classification is
    actually requested keeps bot startup fast if this feature is ever
    disabled or not yet installed.

    lru_cache(maxsize=1) means the (slow, ~600MB) model is only loaded
    into memory the first time this is called - every later call
    during the bot's lifetime reuses the same loaded model instead of
    reloading it from disk.
    """
    from transformers import pipeline

    return pipeline(
        "zero-shot-image-classification",
        model="openai/clip-vit-base-patch32",
    )


def classify_sprite(sprite_url: str, labels: list[str] = VIBE_LABELS) -> str:
    """
    Download the sprite image at `sprite_url` and return whichever
    label in `labels` CLIP scores highest against it.

    Returns DEFAULT_VIBE if anything goes wrong - a network error, a
    corrupt image, or the model failing to load - so a classifier
    problem can never crash quest generation. This mirrors the
    try/except fallback already used around the Ollama call in
    generate_quest().
    """
    try:
        response = requests.get(sprite_url, timeout=15)
        response.raise_for_status()

        image = Image.open(BytesIO(response.content)).convert("RGB")

        classifier = _get_classifier()
        results = classifier(image, candidate_labels=labels)

        # results is a list of {"label": ..., "score": ...} dicts,
        # sorted highest score first.
        return results[0]["label"]

    except Exception:
        return DEFAULT_VIBE
