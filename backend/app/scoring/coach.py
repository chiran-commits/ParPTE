"""AI coach: turns the scoring evidence into a short, prioritised improvement summary.

* Always available: a rule-based coach that ranks the biggest point losses and attaches a concrete drill.
* Optional: set ANTHROPIC_API_KEY (and optionally COACH_MODEL) and Claude writes the summary from the same
  evidence. The rule-based version is used whenever the API is unavailable, slow or returns bad JSON.
"""
from __future__ import annotations

import json
import logging
import os

log = logging.getLogger(__name__)

DRILLS = {
    "Content": "Before speaking or writing, note the 3–4 key ideas, then make sure every one appears in your answer.",
    "Oral Fluency": "Shadowing: play a 30-second clip, then speak along with it 3 times, matching its rhythm. Record yourself and listen for pauses.",
    "Pronunciation": "Record the flagged words slowly, compare them with a dictionary's audio, then say each one in a short sentence 5 times.",
    "Form": "Check the word count and sentence count before submitting. This trait is all-or-nothing.",
    "Grammar": "Re-read each sentence once for subject–verb agreement, articles (a/an/the) and verb tense.",
    "Vocabulary": "Swap 2–3 everyday words for precise academic ones (e.g. 'big' → 'substantial', 'show' → 'demonstrate').",
    "Vocabulary Range": "Use topic-specific vocabulary and avoid repeating the same noun; use synonyms or pronouns.",
    "Spelling": "Keep a list of words you misspell and type each one correctly 5 times. Spell-check is off in the real test.",
    "Development, Structure & Coherence": "Use a 4-paragraph plan: introduction with your position, two body paragraphs (claim + example), conclusion.",
    "General Linguistic Range": "Mix sentence types: one complex sentence with 'although' or 'which', one with a passive, one short sentence for emphasis.",
    "Correctness": "Review why the correct option is right, and find the exact words in the text that prove it.",
    "Words": "Practise 5 dictation sentences a day; write while listening, then fix spelling and plurals.",
}

TASK_STRATEGY = {
    "read_aloud": "Use the preparation time to mark pauses at commas and full stops, and say the hardest words silently.",
    "repeat_sentence": "Repeat immediately, keeping the sentence's rhythm. A fluent partial answer scores better than a hesitant full one.",
    "describe_image": "Structure it: topic → 2–3 key data points with numbers → a trend or comparison → conclusion.",
    "retell_lecture": "Note keywords as you listen, then retell: topic → main points → conclusion, without stopping.",
    "summarize_group_discussion": "Write one line per speaker as you listen, then report each speaker's view and the outcome.",
    "respond_to_situation": "Identify who you're talking to and what you must achieve, then respond politely in the first person.",
    "summarize_written_text": "Find the topic sentence and 2–3 supporting points; join them into one sentence with 'and', 'while' or 'which'.",
    "write_essay": "Spend 3 minutes planning; leave 2 minutes to proofread spelling and grammar.",
    "summarize_spoken_text": "Aim for 50–70 words: topic, two key points, conclusion. Proofread spelling.",
    "write_from_dictation": "Write keywords while listening, then rebuild the sentence. Check plurals and articles.",
}


TASK_DRILLS = {
    ("read_aloud", "Content"): "Read the passage aloud slowly once, then at normal speed, touching each word as you say it. Don't skip, add or change words.",
    ("repeat_sentence", "Content"): "Listen for meaning chunks (subject, verb, object) rather than single words, and repeat chunk by chunk in your head.",
    ("write_from_dictation", "Words"): "Write keywords while listening, then rebuild the sentence. Check plurals, articles and spelling.",
}


def rule_summary(result: dict) -> dict:
    traits = [t for t in result.get("traits", []) if t.get("max")]
    d = result.get("detail", {}) or {}
    task = result.get("task", "")
    if not traits:
        return {"headline": "Not scored", "priorities": [], "strengths": [], "source": "rules"}
    pct = result["score"] / result["max"] if result.get("max") else 0
    losses = sorted(traits, key=lambda t: (t["score"] / t["max"], -t["max"]))
    priorities = []
    for t in losses:
        lost = t["max"] - t["score"]
        if lost <= 0 or t["score"] / t["max"] >= 0.85:
            continue
        why = _why(t["name"], d, result)
        drill = TASK_DRILLS.get((task, t["name"]), DRILLS.get(t["name"], ""))
        priorities.append({"title": f"{t['name']}: {t['score']:g}/{t['max']}", "why": why, "drill": drill})
        if len(priorities) == 3:
            break
    strengths = [f"{t['name']} ({t['score']:g}/{t['max']})" for t in traits if t["score"] / t["max"] >= 0.85]
    if pct >= 0.9:
        headline = "Excellent. This answer is at or near the top band."
    elif pct >= 0.7:
        headline = "Good answer. A couple of fixes would push it into the top band."
    elif pct >= 0.45:
        headline = "Some solid parts, but clear points were lost. Focus on the first priority below."
    else:
        headline = "This answer lost most of its points. Work on the first priority before anything else."
    if task in TASK_STRATEGY and pct < 0.9:
        priorities.append({"title": "Strategy for this question type", "why": "", "drill": TASK_STRATEGY[task]})
    return {"headline": headline, "priorities": priorities, "strengths": strengths, "source": "rules"}


def _why(trait: str, d: dict, result: dict) -> str:
    fl = d.get("fluency") or {}
    pr = d.get("pronunciation") or {}
    capped = ""
    if trait in ("Oral Fluency", "Pronunciation") and d.get("total") and d.get("correct") is not None and d["correct"] / d["total"] < 0.8:
        capped = (f" Capped because only {d['correct']} of {d['total']} words matched the text. Fluency and pronunciation "
                  "are judged on the words you were asked to say.")
    if trait == "Oral Fluency" and fl:
        bits = []
        if fl.get("long_pauses"):
            bits.append(f"{fl['long_pauses']} long pause(s)")
        if fl.get("fillers"):
            bits.append(f"{fl['fillers']} filler(s)")
        if fl.get("mid_phrase_hesitations"):
            bits.append(f"{fl['mid_phrase_hesitations']} mid-phrase hesitation(s)")
        if fl.get("repetitions_restarts"):
            bits.append(f"{fl['repetitions_restarts']} repetition(s)")
        rate = fl.get("syllables_per_sec")
        if rate and rate < 2.4:
            bits.append(f"slow pace ({rate} syllables/s)")
        if fl.get("syllables_between_pauses") and fl["syllables_between_pauses"] < 4:
            bits.append("short, choppy phrases")
        return (("Detected: " + ", ".join(bits) + "." if bits else "" if capped else "Rhythm and phrasing were uneven.") + capped).strip()
    if trait == "Pronunciation" and pr:
        bad = [w["word"] for w in pr.get("words", []) if w.get("level") == "bad"][:6]
        sounds = pr.get("sounds_to_practise") or []
        out = []
        if bad:
            out.append("Unclear words: " + ", ".join(bad) + ".")
        if sounds:
            out.append("Sounds: " + "; ".join(sounds) + ".")
        return ((" ".join(out) or ("" if capped else "Several words were not clearly pronounced.")) + capped).strip()
    if trait == "Content":
        missed = [k["label"] for k in d.get("key_points", []) if not k.get("covered")][:3]
        if d.get("errors") is not None and d.get("total"):
            return f"{d['errors']} word error(s) out of {d['total']}."
        if missed:
            return "Missing: " + "; ".join(missed) + "."
        if d.get("coherence") is not None and d["coherence"] < 1:
            return "The answer wasn't in connected sentences."
    if trait in ("Grammar",) and d.get("grammar"):
        return "; ".join(sorted({g["message"] for g in d["grammar"]}))[:200] + "."
    if trait == "Spelling" and d.get("spelling"):
        return "Misspelled: " + ", ".join(s["word"] for s in d["spelling"][:6]) + "."
    if trait == "Form" and d.get("word_count") is not None:
        return f"{d['word_count']} words, outside the required range."
    return ""


def llm_summary(result: dict, task_name: str) -> dict | None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import httpx

        d = result.get("detail", {}) or {}
        evidence = {
            "task": task_name, "score": result["score"], "max": result["max"],
            "traits": [{k: t[k] for k in ("name", "score", "max", "note") if k in t} for t in result["traits"]],
            "auto_feedback": result.get("feedback", [])[:10],
            "transcript_or_text": (d.get("transcript") or "")[:1500],
            "fluency_evidence": d.get("fluency"),
            "mispronounced_words": [w["word"] for w in (d.get("pronunciation") or {}).get("words", []) if w.get("level") == "bad"][:12],
            "sounds": (d.get("pronunciation") or {}).get("sounds_to_practise"),
            "missed_key_points": [k["label"] for k in d.get("key_points", []) if not k.get("covered")],
            "grammar": [g["message"] for g in d.get("grammar", [])][:8],
            "spelling": [s["word"] for s in d.get("spelling", [])][:8],
        }
        prompt = (
            "You are an expert PTE Academic coach. Using ONLY the scoring evidence below, write feedback for the student. "
            "Return strict JSON: {\"headline\": one sentence, \"priorities\": [up to 3 objects {\"title\", \"why\", \"drill\"}], "
            "\"strengths\": [short strings]}. Order priorities by how many points they cost. 'why' must cite the evidence "
            "(specific words, pauses, missing points). 'drill' must be a concrete exercise for the next practice session. "
            "Do not invent problems that aren't in the evidence. Plain, encouraging, direct English.\n\nEVIDENCE:\n"
            + json.dumps(evidence, ensure_ascii=False)
        )
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=15,
                       headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                       json={"model": os.getenv("COACH_MODEL", "claude-haiku-5-5"), "max_tokens": 700,
                             "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", []))
        data = json.loads(text[text.index("{") : text.rindex("}") + 1])
        if not isinstance(data.get("priorities"), list):
            return None
        data["source"] = "claude"
        return data
    except Exception as e:
        log.info("LLM coach unavailable: %s", e)
        return None


def summarize(result: dict, task_name: str = "") -> dict:
    if not result.get("max"):
        return {"headline": "", "priorities": [], "strengths": [], "source": "none"}
    return llm_summary(result, task_name) or rule_summary(result)


def mock_summary(agg: dict, items: list[dict], task_names: dict[str, str], target: int) -> dict:
    """Study plan after a mock test: weakest skills and question types, ranked by impact."""
    skills = {k: v for k, v in (agg.get("skills") or {}).items() if v is not None}
    weak_skills = sorted(skills.items(), key=lambda kv: kv[1])
    by_task: dict[str, list[float]] = {}
    for it in items:
        if it.get("max"):
            by_task.setdefault(it["task"], []).append(it["score"] / it["max"])
    weak_tasks = sorted(((t, sum(v) / len(v)) for t, v in by_task.items()), key=lambda kv: kv[1])[:4]
    prof = sorted((agg.get("profile") or {}).items(), key=lambda kv: kv[1])[:3]
    gap = [f"{k.title()} {v}" for k, v in weak_skills if v < target]
    headline = (f"You're at or above your target of {target} in every skill." if not gap
                else f"To reach {target}, focus on: " + ", ".join(gap) + ".")
    plan = [{"title": task_names.get(t, t), "why": f"Averaged {round(p * 100)}% in this mock.", "drill": TASK_STRATEGY.get(t, DRILLS.get("Content"))}
            for t, p in weak_tasks if p < 0.8]
    for name, v in prof:
        if v < 75 and name in DRILLS:
            plan.append({"title": f"Skill: {name}", "why": f"{v}% across the test.", "drill": DRILLS[name]})
    return {"headline": headline, "priorities": plan[:5], "strengths": [f"{k.title()} {v}" for k, v in weak_skills[::-1] if v >= target][:4],
            "source": "rules"}
