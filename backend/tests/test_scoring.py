import os
import shutil
import subprocess
import tempfile

import numpy as np
import pytest

os.environ.setdefault("PARPTE_DISABLE_ML", "1")

from app import bank  # noqa: E402
from app.scoring import objective, score_item, writing  # noqa: E402
from app.scoring.audio import SR, acoustic_features  # noqa: E402
from app.scoring.overall import aggregate, to_pte  # noqa: E402
from app.scoring.text import align, keypoint_hits, lcs_len, tokens  # noqa: E402
from app.tasks import TASKS  # noqa: E402


# ---------------------------------------------------------------- bank
def test_every_task_has_questions_and_public_view_hides_answers():
    counts = bank.counts()
    for task in TASKS:
        assert counts[task] >= 1, task
    for q in bank.all_questions():
        pub = bank.public(q)
        for secret in ("answer", "answers", "key_points", "substitutions", "functions"):
            assert secret not in pub, (q["id"], secret)


def test_hiw_indices():
    q = bank.get("hiw-001")
    assert [s["shown"] for s in q["substitutions"]] == ["millions", "useful", "expose", "height"]
    assert q["shown_words"][q["substitutions"][0]["index"]] == "millions"


# ---------------------------------------------------------------- objective (Pearson rules)
def test_mcq_multiple_negative_marking():
    assert objective.mcq_multiple(["A", "C"], ["A", "C", "E"])["score"] == 2
    assert objective.mcq_multiple(["A", "B"], ["A", "C", "E"])["score"] == 0
    assert objective.mcq_multiple(["B", "D"], ["A", "C", "E"])["score"] == 0  # floor at 0


def test_reorder_adjacent_pairs():
    assert objective.reorder(["A", "B", "C", "D"], ["A", "B", "C", "D"])["score"] == 3
    assert objective.reorder(["B", "C", "A", "D"], ["A", "B", "C", "D"])["score"] == 1


def test_hiw_and_wfd():
    assert objective.highlight_incorrect([1, 2, 9], [1, 2, 5])["score"] == 1
    r = objective.write_from_dictation("the seminar has moved to main lecture theater", "The seminar has been moved to the main lecture theatre.")
    assert r["score"] == 7 and r["max"] == 10


def test_fill_blanks():
    q = bank.get("rwfib-003")
    r = score_item("rw_fill_blanks", q, {"blanks": {"0": "popular", "1": "socialise", "2": "showed", "3": "than"}})
    assert r["score"] == 3 and r["max"] == 4


# ---------------------------------------------------------------- text
def test_alignment_and_lcs():
    al = align(tokens("the cat sat on the mat"), tokens("the cat sit on mat"))
    ops = [a.op for a in al]
    assert ops.count("sub") == 1 and ops.count("del") == 1
    assert lcs_len(tokens("a b c d"), tokens("a c d b")) == 3


def test_keypoints():
    hits = keypoint_hits("Coal fell from 45 to 20 percent", [{"label": "coal", "keywords": ["coal", ["fell", "drop"], ["45", "20"]]}])
    assert hits[0]["covered"]


# ---------------------------------------------------------------- writing
GOOD_SWT = ("Trials of a four-day working week show that productivity stayed stable while employees reported lower stress, "
            "although the model does not suit sectors such as hospitals because of higher staffing costs, so it should be adapted to each organisation.")


def test_swt_good_and_form_gate():
    q = bank.get("swt-001")
    r = writing.summarize_written_text(GOOD_SWT, q)
    assert r["traits"][1]["score"] == 1  # form
    assert r["traits"][0]["score"] >= 3  # content
    assert r["score"] >= 7
    bad = writing.summarize_written_text("Four day weeks are good. Productivity is stable.", q)
    assert bad["score"] == 0  # two sentences ⇒ form 0 ⇒ total 0


ESSAY = """Technology now plays a central role in modern classrooms. While some people argue that digital devices make learning easier and more effective, others believe that they distract students and lower the quality of education. In my opinion, technology is beneficial when it is used purposefully.

On the one hand, technology gives learners access to an enormous range of resources. For example, students can watch lectures from leading universities, use interactive simulations in science, and receive instant feedback from online quizzes. Consequently, learning can become more personalised and engaging than traditional textbook study.

On the other hand, it is undeniable that devices can be a source of distraction. Social media notifications and games compete for students' attention, which may reduce concentration and lead to superficial learning. Furthermore, excessive screen time has been linked to poorer sleep, which in turn affects academic performance.

In conclusion, although technology can distract students, I believe that its advantages outweigh its drawbacks provided that teachers set clear rules and integrate digital tools into well-designed lessons. Ultimately, the quality of education depends less on the tools themselves than on how wisely they are used, and this responsibility lies with schools, teachers, parents and the learners themselves alike."""


def test_essay_scores_high_for_good_essay():
    q = bank.get("we-001")
    r = writing.write_essay(ESSAY, q)
    t = {x["name"]: x["score"] for x in r["traits"]}
    assert t["Form"] == 2 and t["Content"] >= 4 and t["Development, Structure & Coherence"] >= 4
    assert r["score"] >= 18, r


def test_essay_off_topic_is_zero():
    q = bank.get("we-001")
    off = " ".join(["My favourite food is pizza with cheese and tomatoes."] * 25)
    assert writing.write_essay(off, q)["score"] == 0


def test_spelling_penalty():
    q = bank.get("we-001")
    r = writing.write_essay(ESSAY.replace("technology", "tecnology", 3).replace("students", "studants", 1), q)
    assert {x["name"]: x["score"] for x in r["traits"]}["Spelling"] == 0


# ---------------------------------------------------------------- speaking
def _tts(text: str, wpm: int = 160, gap_ms: int = 0) -> bytes:
    if not shutil.which("espeak-ng"):
        pytest.skip("espeak-ng not installed")
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        subprocess.run(["espeak-ng", "-s", str(wpm), "-g", str(gap_ms // 10), "-w", f.name, text], check=True)
        return open(f.name, "rb").read()


def test_acoustic_pauses_detected():
    sr = SR
    tone = lambda s: 0.3 * np.sin(2 * np.pi * 180 * np.arange(int(s * sr)) / sr) * (1 + 0.3 * np.sin(np.arange(int(s * sr)) / 400))
    sil = lambda s: np.zeros(int(s * sr))
    wave = np.concatenate([sil(0.8), tone(1.0), sil(1.5), tone(1.0), sil(0.6), tone(1.0)]).astype(np.float32)
    ac = acoustic_features(wave, neural=False)  # pure tones aren't speech to the neural VAD
    assert len(ac.segments) == 3
    assert ac.n_long_pauses == 1 and abs(ac.initial_silence - 0.8) < 0.1


def test_read_aloud_with_real_audio():
    q = bank.get("ra-004")
    audio = _tts(q["text"])
    good = score_item("read_aloud", q, {"transcript": q["text"]}, audio)
    t = {x["name"]: x["score"] for x in good["traits"]}
    assert t["Content"] == 5 and t["Oral Fluency"] >= 3, good
    sloppy = score_item("read_aloud", q, {"transcript": "Coral reefs cover less than one percent of the ocean, yet they support a quarter of marine species."}, audio)
    assert sloppy["traits"][0]["score"] < good["traits"][0]["score"]


def test_slow_choppy_speech_scores_lower_fluency():
    q = bank.get("rs-002")
    fluent = score_item("repeat_sentence", q, {"transcript": q["text"]}, _tts(q["text"], 165))
    choppy = score_item("repeat_sentence", q, {"transcript": "students um must submit their uh assignments through the online portal"},
                        _tts(q["text"], 80, gap_ms=900))
    assert fluent["traits"][1]["score"] > choppy["traits"][1]["score"], (fluent["traits"], choppy["traits"])


def test_open_task_irrelevant_content_zeroes_item():
    q = bank.get("rl-001")
    r = score_item("retell_lecture", q, {"transcript": "I like playing football with my friends on the weekend in the park."},
                   _tts("I like playing football with my friends on the weekend in the park."))
    assert r["score"] == 0


def test_sgd_requires_all_speakers():
    q = bank.get("sgd-001")
    only_maya = "Maya was worried because the group has not agreed on a research question and every meeting turns into a debate."
    r = score_item("summarize_group_discussion", q, {"transcript": only_maya}, _tts(only_maya))
    assert r["traits"][0]["score"] <= 3
    assert r["detail"]["speakers_covered"]["Maya"] and not r["detail"]["speakers_covered"]["Leo"]


def test_asq():
    q = bank.get("asq-003")
    assert score_item("answer_short_question", q, {"transcript": "the heart"}, _tts("the heart"))["score"] == 1
    assert score_item("answer_short_question", q, {"transcript": "lungs"}, _tts("lungs"))["score"] == 0


# ---------------------------------------------------------------- overall
def test_curve_and_aggregate():
    assert to_pte(0) == 10 and to_pte(1) == 90 and 74 <= to_pte(0.78) <= 78
    items = [{"task": "write_from_dictation", "score": 10, "max": 10, "traits": []},
             {"task": "read_aloud", "score": 15, "max": 15, "traits": []}]
    agg = aggregate(items)
    assert agg["skills"]["listening"] == 90 and agg["skills"]["speaking"] == 90 and agg["skills"]["reading"] is None


def test_template_essay_penalised():
    q = bank.get("we-001")
    tpl = ("In this day and age, it is an undeniable fact that technology plays a pivotal role in our lives. This essay will discuss "
           "the pros and cons of this hotly debated topic. ") + ESSAY + (" In a nutshell, every coin has two sides and technology "
           "is a double-edged sword. Last but not least, taking everything into consideration, it goes without saying that a plethora of "
           "factors matter.")
    t = {x["name"]: x["score"] for x in writing.write_essay(tpl, q)["traits"]}
    assert t["Content"] <= 5


def test_swt_copied_sentence_penalised():
    q = bank.get("swt-001")
    copied = ("Over the past decade, a growing number of companies have experimented with a four-day working week, in which "
              "employees work fewer hours for the same pay.")
    r = writing.summarize_written_text(copied, q)
    assert r["traits"][0]["score"] <= 1


def test_grammar_patterns():
    from app.scoring.lexicon import grammar_issues
    codes = {i["code"] for i in grammar_issues("There is many reasons. Its a problem that we discuss about. People could of known more then that.")}
    assert {"there-is-plural", "its-its", "discuss-about", "could-of", "than-then"} <= codes
