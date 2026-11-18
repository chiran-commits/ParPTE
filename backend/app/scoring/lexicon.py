"""Spelling, vocabulary sophistication, cohesion markers and grammar checks."""
from __future__ import annotations

import logging
import os
import re
from functools import lru_cache

from .text import tokens

log = logging.getLogger(__name__)

CONNECTIVES = {
    "addition": ["furthermore", "moreover", "in addition", "additionally", "besides", "also", "what is more"],
    "contrast": ["however", "nevertheless", "nonetheless", "on the other hand", "in contrast", "whereas", "although",
                 "even though", "despite", "while", "conversely", "yet"],
    "cause": ["because", "since", "due to", "owing to", "as a result", "consequently", "therefore", "thus", "hence",
              "accordingly", "leads to", "result in"],
    "example": ["for example", "for instance", "such as", "to illustrate", "namely", "in particular"],
    "sequence": ["firstly", "first", "secondly", "second", "finally", "lastly", "subsequently", "then", "next"],
    "conclusion": ["in conclusion", "to conclude", "to sum up", "overall", "in summary", "all in all", "ultimately"],
    "opinion": ["in my opinion", "i believe", "i would argue", "from my perspective", "it is my view", "i strongly"],
}

SUBORDINATORS = {"although", "because", "since", "unless", "whereas", "while", "if", "when", "which", "who", "whom",
                 "whose", "that", "whether", "though", "until", "once", "provided"}

# Coxhead Academic Word List — a representative subset (headwords) used as a sophistication signal.
ACADEMIC = set(
    """analyse analyze approach area assess assume authority available benefit concept consist constitute context
    contract create data define derive distribute economy environment establish estimate evident export factor
    finance formula function identify income indicate individual interpret involve issue labour labor legal
    legislate major method occur percent period policy principle proceed process require research respond role
    section sector significant similar source specific structure theory vary achieve acquire administrate affect
    appropriate aspect assist category chapter commission community complex compute conclude conduct consequent
    construct consume credit culture design distinct element equate evaluate feature final focus impact injure
    institute invest item journal maintain normal obtain participate perceive positive potential previous primary
    purchase range region regulate relevant reside resource restrict secure seek select site strategy survey text
    tradition transfer alternative circumstance comment compensate component consent considerable constant
    constrain contribute convene coordinate core corporate correspond criteria deduce demonstrate document dominate
    emphasis ensure exclude framework fund illustrate immigrate imply initial instance interact justify layer link
    locate maximise maximize minor negate outcome partner philosophy physical proportion publish react register
    rely remove scheme sequence sex shift specify sufficient task technical technique technology valid volume
    access adequate annual apparent approximate attitude attribute civil code commit communicate concentrate
    confer contrast cycle debate despite dimension domestic emerge error ethnic goal grant hence hypothesis
    implement implicate impose integrate internal investigate job label mechanism obvious occupy option output
    overall parallel parameter phase predict principal prior professional project promote regime resolve retain
    series statistic status stress subsequent sum summary undertake sustainable sustain innovation infrastructure
    phenomenon substantial comprehensive fundamental inevitable crucial essential detrimental beneficial
    unprecedented prevalent diverse facilitate enhance mitigate exacerbate foster incentive""".split()
)


@lru_cache(maxsize=1)
def _spell():
    try:
        from spellchecker import SpellChecker

        return SpellChecker(language="en", distance=2)
    except Exception as e:  # pragma: no cover
        log.warning("pyspellchecker unavailable: %s", e)
        return None


_UK_US = [(r"is(e|ed|es|ing|ation|ations)$", r"iz\1"), (r"our", "or"), (r"yse(d|s)?$", r"yze\1"), (r"tre(s)?$", r"ter\1"),
          (r"ogue(s)?$", r"og\1"), (r"ence$", "ense"), (r"ll(ed|ing|er|ers)$", r"l\1"), (r"ae", "e"), (r"oe", "e")]


def _known(word: str) -> bool:
    sp = _spell()
    if sp is None or word in sp:
        return True
    for uk, us in _UK_US:  # accept both British and American spellings
        cand = re.sub(uk, us, word)
        if cand != word and cand in sp:
            return True
    # American → British direction
    for us, uk in ((r"iz(e|ed|es|ing|ation)$", r"is\1"), (r"or$", "our"), (r"er$", "re"), (r"l(ed|ing)$", r"ll\1")):
        cand = re.sub(us, uk, word)
        if cand != word and cand in sp:
            return True
    return False


def spelling_errors(text: str, extra_vocab: set[str] | None = None) -> list[dict]:
    """Return misspelled words with a suggestion. Capitalised words mid-sentence (proper nouns) are skipped."""
    sp = _spell()
    if sp is None:
        return []
    raw = tokens(text, lower=False)
    out, seen = [], set()
    extra = {w.lower() for w in (extra_vocab or set())}
    for i, w in enumerate(raw):
        lw = w.lower()
        if lw in seen or lw in extra or w.isdigit() or any(c.isdigit() for c in w) or len(lw) <= 1:
            continue
        if i > 0 and w[0].isupper() and not w.isupper():
            continue  # proper noun
        if "'" in lw:
            base = lw.split("'")[0]
            if _known(base):
                continue
        if not _known(lw):
            seen.add(lw)
            out.append({"word": w, "suggestion": sp.correction(lw)})
    return out


@lru_cache(maxsize=50000)
def zipf(word: str) -> float:
    """Approximate Zipf frequency (1–7) from pyspellchecker's frequency list. Rare ⇒ low."""
    import math

    sp = _spell()
    if sp is None:
        return 5.0
    freq = sp.word_frequency.dictionary.get(word.lower(), 0)
    total = sp.word_frequency.total_words or 1
    if not freq:
        return 1.5
    return max(1.0, min(7.0, math.log10(freq / total * 1e9)))


def sophistication(toks: list[str]) -> dict:
    content = [t for t in toks if len(t) > 3 and t.isalpha()]
    if not content:
        return {"rare_ratio": 0.0, "academic_ratio": 0.0, "avg_word_len": 0.0}
    rare = sum(1 for t in content if zipf(t) < 4.0)
    acad = sum(1 for t in content if t in ACADEMIC or t.rstrip("s") in ACADEMIC)
    return {
        "rare_ratio": rare / len(content),
        "academic_ratio": acad / len(content),
        "avg_word_len": sum(map(len, content)) / len(content),
    }


def connective_profile(text: str) -> dict:
    low = " " + re.sub(r"\s+", " ", text.lower()) + " "
    found = {}
    for cat, items in CONNECTIVES.items():
        hits = [c for c in items if re.search(r"(?<![a-z])" + re.escape(c) + r"(?![a-z])", low)]
        if hits:
            found[cat] = hits
    return found


# ---------------------------------------------------------------- grammar
_VOWEL_SOUND_EXCEPTIONS_AN = {"hour", "honest", "honour", "honor", "heir", "hourly"}
_CONSONANT_SOUND_U = ("uni", "use", "usu", "uti", "eur", "one", "once", "ubi")

GRAMMAR_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("double-word", re.compile(r"\b(\w+)\s+\1\b", re.I), "Repeated word"),
    ("lower-i", re.compile(r"(?<![\w'])i(?![\w'])"), "'I' should be capitalised"),
    ("space-before-punct", re.compile(r"\s+[,.;:!?]"), "Space before punctuation"),
    ("no-space-after-punct", re.compile(r"[,;:](?=[A-Za-z])"), "Missing space after punctuation"),
    ("sv-agreement", re.compile(r"\b(he|she|it|this|that|everyone|nobody|somebody)\s+(have|do|are|were|go|make|take|seem|need)\b", re.I),
     "Subject–verb agreement"),
    ("sv-agreement-pl", re.compile(r"\b(they|we|you|people|students|children)\s+(has|does|is|was|goes|makes|takes|seems|needs)\b", re.I),
     "Subject–verb agreement"),
    ("modal-verb", re.compile(r"\b(can|could|will|would|should|must|might|may)\s+(to\s+\w+|\w+s|\w+ed)\b(?<!\bneeds)", re.I),
     "Modal verbs take the bare infinitive"),
    ("more-er", re.compile(r"\bmore\s+(\w+er)\b", re.I), "Double comparative"),
    ("much-countable", re.compile(r"\bmuch\s+(people|students|cars|countries|things|problems|benefits)\b", re.I),
     "Use 'many' with countable nouns"),
    ("less-countable", re.compile(r"\bless\s+(people|students|cars|countries|problems)\b", re.I), "Use 'fewer' with countable nouns"),
    ("informal", re.compile(r"\b(gonna|wanna|gotta|kinda|ain't|u|ur|lol|etc\.\.\.)\b", re.I), "Informal language"),
    ("there-is-plural", re.compile(r"\bthere (is|was) (many|several|two|three|few|a lot of|lots of|numerous|various)\b", re.I),
     "Use 'there are/were' with plural nouns"),
    ("its-its", re.compile(r"\bits (a|an|the|very|not|important|clear|true|essential)\b|\bit's (own|role|impact|effect)\b", re.I),
     "Confused 'its' (possessive) and 'it's' (it is)"),
    ("could-of", re.compile(r"\b(could|should|would|must) of\b", re.I), "Use 'could have', not 'could of'"),
    ("than-then", re.compile(r"\b(more|less|better|worse|rather|other|greater|higher|lower) then\b", re.I), "Use 'than' in comparisons"),
    ("double-negative", re.compile(r"\b(don't|doesn't|didn't|can't|won't|isn't|aren't) (no|nothing|nobody|never)\b", re.I), "Double negative"),
    ("people-has", re.compile(r"\b(many|most|some|these|those|several) (\w+s) (has|is|was|does)\b", re.I), "Plural subject needs a plural verb"),
    ("despite-of", re.compile(r"\bdespite of\b", re.I), "Use 'despite' or 'in spite of'"),
    ("discuss-about", re.compile(r"\b(discuss|discussed|discussing) about\b", re.I), "'Discuss' takes no 'about'"),
    ("informations", re.compile(r"\b(informations|advices|knowledges|researches|equipments|furnitures|evidences)\b", re.I),
     "This noun is uncountable — no plural -s"),
]


def grammar_issues(text: str) -> list[dict]:
    issues: list[dict] = []
    for code, pat, msg in GRAMMAR_PATTERNS:
        for m in pat.finditer(text):
            if code == "modal-verb":
                nxt = m.group(2).lower()
                if nxt.startswith("to ") or nxt in {"this", "has", "was", "is", "thus", "process", "access", "focus", "address",
                                                    "discuss", "pass", "express", "cross", "dress", "unless", "always", "perhaps",
                                                    "seriously", "less", "succeed", "need", "exceed", "proceed", "feed", "bleed"}:
                    if not nxt.startswith("to "):
                        continue
                if nxt.endswith("ss") or nxt.endswith("us") or nxt.endswith("is") or nxt.endswith("eed"):
                    continue
            if code == "double-word" and m.group(1).lower() in {"that", "had"}:
                continue
            issues.append({"code": code, "message": msg, "text": m.group(0), "offset": m.start()})
    # articles
    for m in re.finditer(r"\b(a|an)\s+([A-Za-z]+)", text):
        art, w = m.group(1).lower(), m.group(2).lower()
        vowel = w[0] in "aeiou"
        if w.startswith(_CONSONANT_SOUND_U):
            vowel = False
        if w in _VOWEL_SOUND_EXCEPTIONS_AN or w.startswith("hour") or w.startswith("hono"):
            vowel = True
        if art == "a" and vowel:
            issues.append({"code": "article", "message": f"Use 'an' before '{w}'", "text": m.group(0), "offset": m.start()})
        elif art == "an" and not vowel:
            issues.append({"code": "article", "message": f"Use 'a' before '{w}'", "text": m.group(0), "offset": m.start()})
    # sentence capitalisation
    for m in re.finditer(r"(?:^|[.!?]\s+)([a-z])", text):
        issues.append({"code": "capital", "message": "Sentence should start with a capital letter", "text": m.group(0).strip(),
                       "offset": m.start(1)})
    # run-on sentences
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if len(sent.split()) > 55 and sent.count(",") < 2:
            issues.append({"code": "run-on", "message": "Very long sentence with little punctuation — split it", "text": sent[:40] + "…",
                           "offset": text.find(sent)})
    issues.extend(_languagetool(text))
    # de-duplicate by offset
    seen, uniq = set(), []
    for i in sorted(issues, key=lambda x: x["offset"]):
        key = (i["offset"], i["code"][:5])
        if key not in seen:
            seen.add(key)
            uniq.append(i)
    return uniq


def _languagetool(text: str) -> list[dict]:
    """Optional: set LANGUAGETOOL_URL (e.g. a self-hosted LanguageTool server) for much better grammar checking."""
    url = os.getenv("LANGUAGETOOL_URL")
    if not url or not text.strip():
        return []
    try:
        import httpx

        r = httpx.post(url.rstrip("/") + "/v2/check", data={"text": text, "language": "en-US"}, timeout=8)
        r.raise_for_status()
        out = []
        for m in r.json().get("matches", []):
            cat = (m.get("rule", {}).get("category", {}) or {}).get("id", "")
            if cat in {"TYPOS", "CASING"}:  # spelling handled separately
                continue
            out.append({"code": "lt:" + m.get("rule", {}).get("id", ""), "message": m.get("message", ""),
                        "text": text[m["offset"]: m["offset"] + m["length"]], "offset": m["offset"]})
        return out
    except Exception as e:  # pragma: no cover
        log.info("LanguageTool unavailable: %s", e)
        return []
