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

Everything below runs on a small CPU server with no model downloads. PocketSphinx and Silero ship inside the install.

1. **Decode** any browser recording to 16 kHz mono (ffmpeg).
2. **Voice activity (Silero VAD, neural):** exact speech/silence boundaries, even with background noise. This gives pauses, long pauses (≥1 s), initial delay and speaking time.
3. **Syllable nuclei** (de Jong & Wempe method): syllables counted from intensity peaks in the signal itself, which gives speech rate, articulation rate and mean length of run. This is measured from the audio, so a browser recogniser that tidies up your speech can't inflate it.
4. **Forced alignment (PocketSphinx):** the audio is aligned to the words you were meant to say. For Read Aloud and Repeat Sentence that's the reference text, in the order you actually said it; for open tasks it's the transcript. The aligner tries a grammar with optional fillers between words, falls back to wider beams for long passages, then to aligning long recordings piece by piece at their pauses. British-style non-rhotic pronunciations are added as alternatives, and words missing from the dictionary get pronunciations from UK/US spelling variants, compound splitting or letter-to-sound rules.
5. **Goodness of Pronunciation (GOP):** each word's acoustic score, normalised per frame against the best-matching sound model, shows how far the sounds you produced were from the expected ones. The phone-level pass names the sound that went wrong ("the 'th' in think").
6. **Trained model:** gradient-boosted regressors map 29 acoustic features to expert pronunciation-accuracy, fluency and prosody ratings. They were trained on **speechocean762** (5,000 utterances, five expert raters each) with `training/train_speaking.py`.
7. **Rubric layer:** the PTE oral-fluency bands are applied as hard caps on top of the model. One long pause caps fluency at 2.5, two or more at 1.5, three or more hesitations at 3, and unnaturally fast speech (over 6.5 syllables/s) at 3. For Read Aloud and Repeat Sentence, fluency and pronunciation are also capped by how much of the text you said correctly, so reading half the passage or reading it out of order can't earn top marks for how it sounded.
8. **Optional extras:** Whisper (server transcription that keeps fillers and repetitions), a wav2vec2 phoneme recogniser, and the fine-tuned wav2vec2 model from the Kaggle notebook are blended in when installed.

### Accuracy on unseen speech

| Trait | ParPTE (held-out speechocean762 test split) | GOPT, published research model (2022) |
|---|---|---|
| Pronunciation accuracy | PCC 0.67 | 0.71 |
| Fluency | PCC 0.75 | 0.75 |
| Prosody | PCC 0.74 | 0.76 |

PCC is the Pearson correlation with the average of five expert raters; 1.0 would be perfect agreement. Human raters don't agree with each other perfectly either, so no automatic system gets close to 1.0.

### Adversarial tests

`tests/test_speaking_robustness.py` synthesises deliberately bad answers and checks they can't score well. For several of them the transcript passed in is the clean reference text, simulating a browser that autocorrected the speech:

* long pauses mid-sentence → fluency ≤ 2
* "um" fillers the transcript hides → fluency drops and is capped at 3.5
* word-by-word, slow reading → fluency ≤ 2
* badly mispronounced audio with a perfect transcript → pronunciation ≤ 2 and well below the clean reading
* words read out of order → content ≤ 2.5, fluency and pronunciation ≤ 3
* only half the passage read → every trait ≤ 3
* repetitions and restarts → fluency ≤ 4
* rushed speech (≈420 wpm) → fluency ≤ 3.5
* a keyword list instead of sentences (Describe Image) → content ≤ 2.5
* silence → 0

## Writing pipeline

Rules handle form, spelling (UK and US accepted), 20+ grammar patterns, cohesion markers, paragraphing, sentence variety, lexical diversity and academic vocabulary. They also penalise memorised template phrases (Pearson has lowered scores for memorised content since 2025), summaries copied word for word from the passage, and paragraphs that drift off topic. Set `LANGUAGETOOL_URL` to a LanguageTool server for much stronger grammar checking. With the ELLIPSE model installed, cohesion, syntax, vocabulary, phraseology, grammar and conventions predictions are blended into DSC, GLR, vocabulary and grammar.

## From items to the 10–90 scale

Every task contributes to one or more skills with a weight (`app/tasks.py`). For example, Repeat Sentence feeds Speaking with all traits and Listening through Content only. Following the 2025 format, Read Aloud now counts for Speaking only. Each skill's weighted proportion of points is mapped to 10–90 by the piecewise curve `CURVE` in `app/scoring/overall.py`. Overall is the mean of the skills.

### Calibrating against real results

Once users share official PTE score reports, fit `CURVE` so predictions match them:

1. Export each user's predicted skill proportions (from `/api/progress`) taken within two weeks of their exam.
2. Pair them with the official skill scores.
3. Fit a monotonic mapping (isotonic regression works well) and replace the `CURVE` anchor points.
