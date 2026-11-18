# How ParPTE scores

ParPTE follows the trait structure and point ranges Pearson publishes for PTE Academic (including the 7 August 2025 changes), and uses speech and language models to judge each trait. Pearson's own model and its raw-score-to-10–90 conversion are not public, so every number ParPTE gives is an **estimate**.

## Item scoring

| Task | Traits (max) | Rules implemented |
|---|---|---|
| Read Aloud | Content (/5, scaled from per-word errors) · Oral fluency /5 · Pronunciation /5 | Each omission, insertion or substitution is one error (word-level Levenshtein alignment) |
| Repeat Sentence | Content /3 · Fluency /5 · Pronunciation /5 | 3 = all words in sequence; 2 = ≥50 %; 1 = some; 0 = almost none (longest common subsequence) |
| Describe Image | Content /6 · Fluency /5 · Pronunciation /5 | Key elements of the image + trend, comparison, figures and conclusion |
| Re-tell Lecture | Content /6 · Fluency /5 · Pronunciation /5 | Key-point coverage + semantic similarity to the lecture |
| Summarize Group Discussion | Content /6 · Fluency /5 · Pronunciation /5 | Each speaker's view must be reported. Missing a speaker caps content |
| Respond to a Situation | Content /6 · Fluency /5 · Pronunciation /5 | Communicative functions (apologise, explain, request…), politeness, first person, relevance |
| Answer Short Question | Vocabulary /1 | Any accepted answer present |
| Summarize Written Text | Content /4 · Form /1 · Grammar /2 · Vocabulary /2 | Form: one sentence, 5–75 words |
| Write Essay | Content /6 · Form /2 · DSC /6 · Grammar /2 · GLR /6 · Vocabulary /2 · Spelling /2 | Form: 200–300 = 2, 120–199 or 301–380 = 1. All caps or bullet lists = 0 |
| Summarize Spoken Text | Content /4 · Form /2 · Grammar /2 · Vocabulary /2 · Spelling /2 | Form: 50–70 = 2, 40–49 or 71–100 = 1 |
| MCQ multiple, HIW | +1 per correct, −1 per incorrect, minimum 0 | |
| Re-order Paragraphs | 1 per correct adjacent pair | |
| Fill in the Blanks (all three) | 1 per correct blank | Listening FIB requires exact spelling |
| MCQ single, HCS, SMW | 1 / 0 | |
| Write from Dictation | 1 per correct word | Order-free, spelling must be exact |

**Zero rule:** if Content (open speaking tasks, writing) or Form (writing) scores 0, the whole response scores 0, as in the real test.

## Speaking pipeline

1. **Decode** any browser recording to 16 kHz mono (ffmpeg).
2. **Acoustics** (numpy): energy-based voice activity → speech segments, pauses, initial silence, and pitch variation (intonation).
3. **Speech recognition:** Whisper with word timestamps, prompted to keep fillers. Without Whisper, the browser's transcript is used and word timings are estimated from the detected speech segments.
4. **Oral fluency** maps the PTE rubric bands (native-like → disfluent) onto speech rate, hesitations (fillers + 0.5–1 s pauses), long pauses (≥1 s), repetitions and false starts, phrase length and intonation.
5. **Pronunciation:** with the phoneme model, the recognised phonemes are aligned to the expected phonemes (g2p) and phoneme accuracy gives the score, plus a per-word breakdown. Without it, the score is estimated from how intelligible the speech was to the recogniser.
6. **Learned models** (from Kaggle) are blended in when present: a feature regressor and/or a fine-tuned wav2vec2 model predict expert accuracy, fluency and prosody ratings.

## Writing pipeline

Rules handle form, spelling (UK and US accepted), grammar patterns, cohesion markers, paragraphing, sentence variety, lexical diversity and academic vocabulary. Set `LANGUAGETOOL_URL` to a LanguageTool server for much stronger grammar checking. With the ELLIPSE model installed, cohesion, syntax, vocabulary, phraseology, grammar and conventions predictions are blended into DSC, GLR, vocabulary and grammar.

## From items to the 10–90 scale

Every task contributes to one or more skills with a weight (`app/tasks.py`). For example, Repeat Sentence feeds Speaking with all traits and Listening through Content only. Following the 2025 format, Read Aloud now counts for Speaking only. Each skill's weighted proportion of points is mapped to 10–90 by the piecewise curve `CURVE` in `app/scoring/overall.py`. Overall is the mean of the skills.

### Calibrating against real results

Once users share official PTE score reports, fit `CURVE` so predictions match them:

1. Export each user's predicted skill proportions (from `/api/progress`) taken within two weeks of their exam.
2. Pair them with the official skill scores.
3. Fit a monotonic mapping (isotonic regression works well) and replace the `CURVE` anchor points.
