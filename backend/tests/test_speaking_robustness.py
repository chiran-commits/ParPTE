"""Adversarial speaking tests: deliberately bad answers must never get top marks.

Audio is synthesised with espeak-ng. Where a browser recogniser would "tidy up" speech, the transcript we
pass is the clean reference text — the scorer must still catch the problem from the audio itself.
"""
import os
import random
import shutil
import subprocess
import tempfile

import pytest

os.environ.setdefault("PARPTE_DISABLE_ML", "1")  # heavy optional models off; acoustic engine + trained regressor on

from app import bank  # noqa: E402
from app.scoring import score_item, sphinx  # noqa: E402

pytestmark = pytest.mark.skipif(not shutil.which("espeak-ng") or not sphinx.available(), reason="needs espeak-ng and pocketsphinx")

RA = bank.get("ra-004")["text"]  # coral reefs
RS = bank.get("rs-002")["text"]


def tts(text: str, wpm: int = 165, ssml: bool = False, voice: str = "en-us+f3") -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        cmd = ["espeak-ng", "-v", voice, "-s", str(wpm), "-w", f.name]
        if ssml:
            cmd.append("-m")
        subprocess.run(cmd + [text], check=True)
        return open(f.name, "rb").read()


def traits(r):
    return {t["name"]: t["raw"] for t in r["traits"]}


@pytest.fixture(scope="module")
def good_ra():
    return traits(score_item("read_aloud", bank.get("ra-004"), {"transcript": RA}, tts(RA), with_coach=False))


def test_good_reading_scores_well(good_ra):
    # espeak is a robotic formant synthesiser, so its pronunciation sits well below a real fluent speaker's
    # (word GOP ≈ −2.7 vs −1.7). We only require it to be clearly fluent and not penalised to the floor.
    assert good_ra["Content"] >= 4.8
    assert good_ra["Oral Fluency"] >= 3.0, good_ra
    assert good_ra["Pronunciation"] >= 1.5, good_ra


def test_long_pauses_cap_fluency(good_ra):
    words = RA.split()
    paused = " ".join(words[:8]) + ' <break time="1600ms"/> ' + " ".join(words[8:20]) + ' <break time="1600ms"/> ' + " ".join(words[20:])
    r = traits(score_item("read_aloud", bank.get("ra-004"), {"transcript": RA}, tts(f"<speak>{paused}</speak>", ssml=True), with_coach=False))
    assert r["Oral Fluency"] <= 2.0, r  # two long pauses ⇒ Limited at best
    assert r["Oral Fluency"] < good_ra["Oral Fluency"] - 1


def test_fillers_hidden_from_transcript_still_hurt(good_ra):
    words = RA.split()
    um = " ".join(w + (" um," if i in (3, 9, 15, 22, 30) else "") for i, w in enumerate(words))
    r = traits(score_item("read_aloud", bank.get("ra-004"), {"transcript": RA}, tts(um), with_coach=False))
    assert r["Oral Fluency"] < good_ra["Oral Fluency"], r
    assert r["Oral Fluency"] <= 3.5, r


def test_slow_word_by_word_reading():
    words = RA.split()
    choppy = "<speak>" + ' <break time="700ms"/> '.join(words) + "</speak>"
    r = traits(score_item("read_aloud", bank.get("ra-004"), {"transcript": RA}, tts(choppy, wpm=110, ssml=True), with_coach=False))
    assert r["Oral Fluency"] <= 2.0, r


def test_mispronounced_but_transcript_autocorrected(good_ra):
    # What was said is badly mispronounced; the browser transcript (autocorrected) shows the right words.
    bad = ("Korral reefus kova lesu dan wan persento of za oshan flora, yet zey suppot about a kwota of oll marin spishis. "
           "Zese fragail ekosistems ar tretend by raising si temperachurs, polushon and ovafishing, and sientists warn zat meni "
           "reefs kud disapia wizin a fyu dekeds.")
    r = traits(score_item("read_aloud", bank.get("ra-004"), {"transcript": RA}, tts(bad), with_coach=False))
    assert r["Pronunciation"] < good_ra["Pronunciation"] - 0.6, (r, good_ra)
    assert r["Pronunciation"] <= 2.0, r


def test_out_of_order_reading_is_not_top_band():
    words = RA.replace(",", "").replace(".", "").split()
    random.Random(3).shuffle(words)
    shuffled = " ".join(words)
    r = traits(score_item("read_aloud", bank.get("ra-004"), {"transcript": shuffled}, tts(shuffled), with_coach=False))
    assert r["Content"] <= 2.5, r
    assert r["Oral Fluency"] <= 3.0 and r["Pronunciation"] <= 3.0, r


def test_reading_half_the_text_caps_everything():
    half = " ".join(RA.split()[:20])
    r = traits(score_item("read_aloud", bank.get("ra-004"), {"transcript": half}, tts(half), with_coach=False))
    assert r["Content"] <= 3.0 and r["Oral Fluency"] <= 3.0 and r["Pronunciation"] <= 3.0, r


def test_repetitions_and_restarts():
    q = bank.get("rs-002")
    said = "Students must sub- submit their their assignments through the online the online portal before midnight"
    r = traits(score_item("repeat_sentence", q, {"transcript": said}, tts(said), with_coach=False))
    assert r["Oral Fluency"] <= 4.0, r


def test_rushed_speech():
    r = traits(score_item("read_aloud", bank.get("ra-004"), {"transcript": RA}, tts(RA, wpm=420), with_coach=False))
    assert r["Oral Fluency"] <= 3.5, r


def test_keyword_salad_in_describe_image():
    q = bank.get("di-001")
    salad = "coal solar wind gas hydro two thousand twenty percent forty five eighteen fifteen renewable fossil shift increase decrease"
    r = traits(score_item("describe_image", q, {"transcript": salad}, tts(salad), with_coach=False))
    assert r["Content"] <= 2.5, r


def test_silence_scores_zero():
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000), w.writeframes(b"\x00\x00" * 16000 * 3)
    r = score_item("read_aloud", bank.get("ra-004"), {"transcript": ""}, buf.getvalue(), with_coach=False)
    assert r["score"] == 0


def test_coach_summary_present():
    r = score_item("read_aloud", bank.get("ra-004"), {"transcript": RA}, tts(RA, wpm=90))
    assert r["coach"]["headline"] and r["coach"]["priorities"]


# ---- browser-recognition errors must not count against a correct reading (user report, Nov 2026)
CHROME_ERRORS = ("it is a often several decrease warmer than the rounding counter side a phenomenon known as the urban heat island "
                 "effect concrete and asfalt absorb sunlight during the day and release it slowly at night were the lack of vegetation "
                 "reduces natural cooling planting trees and installing reflective routes are two practical ways to reduce the effect")


def test_correct_reading_survives_browser_misrecognition():
    q = bank.get("ra-001")
    r = score_item("read_aloud", q, {"transcript": CHROME_ERRORS}, tts(q["text"]), with_coach=False)
    assert r["detail"]["content_engine"] == "acoustic"
    assert traits(r)["Content"] >= 4.8, [a for a in r["detail"]["alignment"] if a["op"] != "ok"]


def test_real_misreading_still_caught():
    q = bank.get("ra-001")
    said = q["text"].replace("while", "were")
    r = score_item("read_aloud", q, {"transcript": CHROME_ERRORS}, tts(said), with_coach=False)
    subs = [(a["ref"], a["hyp"]) for a in r["detail"]["alignment"] if a["op"] == "sub"]
    assert ("while", "were") in subs, subs


def test_no_transcript_uses_audio_only():
    q = bank.get("ra-001")
    full = traits(score_item("read_aloud", q, {"transcript": ""}, tts(q["text"]), with_coach=False))
    half = traits(score_item("read_aloud", q, {"transcript": ""}, tts(" ".join(q["text"].split()[:25])), with_coach=False))
    assert full["Content"] >= 4.5 and half["Content"] <= 3.0, (full, half)
