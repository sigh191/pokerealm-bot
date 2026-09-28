"""
Diagnostic version - run this INSTEAD of the previous test_audio.py.

Same idea (classify a few Pokemon cries, no Discord needed), but this
one prints two extra things to help track down why every Pokemon was
getting the exact same label ("aggressive and sharp") last time:

1. Basic stats about the DOWNLOADED WAVEFORM ITSELF (length, duration,
   max volume) for each Pokemon - if these numbers are identical (or
   the max volume is ~0.0) across every Pokemon, the bug is in
   downloading/decoding the audio, before the model even sees it.

2. The FULL ranked list of scores for every label, not just the
   winner - if the scores are all clearly different per Pokemon, but
   "aggressive and sharp" just happens to always end up on top, that's
   a different kind of problem (the model/labels aren't a good fit for
   this data), not a code bug.

Run with: python test_audio.py
(from your project's root folder)
"""

from io import BytesIO

import librosa
import requests

from ai.audio_classifier import (
    CRY_URL_TEMPLATE,
    CLAP_SAMPLE_RATE,
    SOUND_LABELS,
    HYPOTHESIS_TEMPLATE,
    _get_audio_classifier,
)

TEST_POKEMON = {
    25: "Pikachu",
    6: "Charizard",
    94: "Gengar",
    143: "Snorlax",
}

print("Loading CLAP model (fast if you already ran this before - it's cached)...\n")
classifier = _get_audio_classifier()

for dex_number, name in TEST_POKEMON.items():
    url = CRY_URL_TEMPLATE.format(dex_number=dex_number)
    response = requests.get(url, timeout=15)
    response.raise_for_status()

    waveform, _ = librosa.load(BytesIO(response.content), sr=CLAP_SAMPLE_RATE)

    print(f"=== {name} (#{dex_number}) ===")
    print(f"  waveform: {len(waveform)} samples, {len(waveform) / CLAP_SAMPLE_RATE:.2f}s, "
          f"max amplitude={waveform.max():.4f}, mean abs={abs(waveform).mean():.4f}")

    results = classifier(
        waveform,
        candidate_labels=SOUND_LABELS,
        hypothesis_template=HYPOTHESIS_TEMPLATE,
    )
    print("  scores (highest first):")
    for r in results:
        print(f"    {r['score']:.4f}  {r['label']}")
    print()
