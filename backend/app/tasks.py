"""Registry of all PTE Academic task types: timings, module, and how each contributes to the four skills.

Contribution weights approximate Pearson's integrated scoring (2025 format, where Read Aloud counts for
Speaking only and Listening Fill in the Blanks no longer feeds Writing). `trait` limits a contribution to
one trait — e.g. Repeat Sentence feeds Listening through Content only.
"""
from __future__ import annotations

TASKS: dict[str, dict] = {
    # ------------------------------------------------------------ Speaking
    "personal_introduction": dict(name="Personal Introduction", abbr="PI", module="speaking", prep=25, record=30, scored=False,
                                  skills=[]),
    "read_aloud": dict(name="Read Aloud", abbr="RA", module="speaking", prep=35, record=40,
                       skills=[("speaking", None, 1.0)]),
    "repeat_sentence": dict(name="Repeat Sentence", abbr="RS", module="speaking", prep=0, record=15, audio=True,
                            skills=[("speaking", None, 1.0), ("listening", "Content", 0.9)]),
    "describe_image": dict(name="Describe Image", abbr="DI", module="speaking", prep=25, record=40,
                           skills=[("speaking", None, 1.2)]),
    "retell_lecture": dict(name="Re-tell Lecture", abbr="RL", module="speaking", prep=10, record=40, audio=True,
                           skills=[("speaking", None, 1.2), ("listening", "Content", 0.8)]),
    "answer_short_question": dict(name="Answer Short Question", abbr="ASQ", module="speaking", prep=0, record=10, audio=True,
                                  skills=[("speaking", None, 0.3), ("listening", None, 0.3)]),
    "summarize_group_discussion": dict(name="Summarize Group Discussion", abbr="SGD", module="speaking", prep=10, record=120,
                                       audio=True, new=True,
                                       skills=[("speaking", None, 1.4), ("listening", "Content", 1.0)]),
    "respond_to_situation": dict(name="Respond to a Situation", abbr="RTS", module="speaking", prep=20, record=40,
                                 audio=True, new=True, skills=[("speaking", None, 1.2)]),
    # ------------------------------------------------------------ Writing
    "summarize_written_text": dict(name="Summarize Written Text", abbr="SWT", module="writing", time=600,
                                   skills=[("writing", None, 1.2), ("reading", "Content", 0.6)]),
    "write_essay": dict(name="Write Essay", abbr="WE", module="writing", time=1200, skills=[("writing", None, 2.0)]),
    # ------------------------------------------------------------ Reading
    "rw_fill_blanks": dict(name="Reading & Writing: Fill in the Blanks", abbr="RWFIB", module="reading", suggested=120,
                           skills=[("reading", None, 1.0), ("writing", None, 0.8)]),
    "mcq_multiple_reading": dict(name="Multiple Choice, Multiple Answers", abbr="MCMA", module="reading", suggested=120,
                                 skills=[("reading", None, 0.6)]),
    "reorder_paragraphs": dict(name="Re-order Paragraphs", abbr="RO", module="reading", suggested=150,
                               skills=[("reading", None, 0.8)]),
    "reading_fill_blanks": dict(name="Reading: Fill in the Blanks", abbr="RFIB", module="reading", suggested=90,
                                skills=[("reading", None, 1.0)]),
    "mcq_single_reading": dict(name="Multiple Choice, Single Answer", abbr="MCSA", module="reading", suggested=90,
                               skills=[("reading", None, 0.4)]),
    # ------------------------------------------------------------ Listening
    "summarize_spoken_text": dict(name="Summarize Spoken Text", abbr="SST", module="listening", time=600, audio=True,
                                  skills=[("listening", "Content", 1.0), ("writing", None, 1.0)]),
    "mcq_multiple_listening": dict(name="Multiple Choice, Multiple Answers", abbr="LMCMA", module="listening", audio=True,
                                   skills=[("listening", None, 0.5)]),
    "listening_fill_blanks": dict(name="Fill in the Blanks", abbr="LFIB", module="listening", audio=True,
                                  skills=[("listening", None, 0.9)]),
    "highlight_correct_summary": dict(name="Highlight Correct Summary", abbr="HCS", module="listening", audio=True,
                                      skills=[("listening", None, 0.5), ("reading", None, 0.3)]),
    "mcq_single_listening": dict(name="Multiple Choice, Single Answer", abbr="LMCSA", module="listening", audio=True,
                                 skills=[("listening", None, 0.4)]),
    "select_missing_word": dict(name="Select Missing Word", abbr="SMW", module="listening", audio=True,
                                skills=[("listening", None, 0.4)]),
    "highlight_incorrect_words": dict(name="Highlight Incorrect Words", abbr="HIW", module="listening", audio=True,
                                      skills=[("listening", None, 0.7), ("reading", None, 0.7)]),
    "write_from_dictation": dict(name="Write from Dictation", abbr="WFD", module="listening", audio=True,
                                 skills=[("listening", None, 1.3), ("writing", None, 1.2)]),
}

MODULES = ["speaking", "writing", "reading", "listening"]

# Full mock test blueprint (counts per task, within Pearson's published ranges)
MOCK_BLUEPRINT = {
    "full": {
        "read_aloud": 6, "repeat_sentence": 10, "describe_image": 5, "retell_lecture": 2, "answer_short_question": 5,
        "summarize_group_discussion": 2, "respond_to_situation": 2, "summarize_written_text": 2, "write_essay": 1,
        "rw_fill_blanks": 5, "mcq_multiple_reading": 2, "reorder_paragraphs": 2, "reading_fill_blanks": 4,
        "mcq_single_reading": 2, "summarize_spoken_text": 2, "mcq_multiple_listening": 2, "listening_fill_blanks": 2,
        "highlight_correct_summary": 2, "mcq_single_listening": 2, "select_missing_word": 2,
        "highlight_incorrect_words": 2, "write_from_dictation": 3,
    },
    "mini": {
        "read_aloud": 2, "repeat_sentence": 3, "describe_image": 1, "retell_lecture": 1, "answer_short_question": 2,
        "summarize_group_discussion": 1, "respond_to_situation": 1, "summarize_written_text": 1, "write_essay": 1,
        "rw_fill_blanks": 2, "mcq_multiple_reading": 1, "reorder_paragraphs": 1, "reading_fill_blanks": 2,
        "mcq_single_reading": 1, "summarize_spoken_text": 1, "mcq_multiple_listening": 1, "listening_fill_blanks": 1,
        "highlight_correct_summary": 1, "mcq_single_listening": 1, "select_missing_word": 1,
        "highlight_incorrect_words": 1, "write_from_dictation": 2,
    },
}

for _k, _v in TASKS.items():
    _v["id"] = _k
    _v.setdefault("scored", True)
    _v.setdefault("audio", False)
    _v.setdefault("new", False)
