import { ChoiceTask } from "./ChoiceTask";
import { FibTask } from "./FibTask";
import { HighlightTask, ReorderTask } from "./OrderAndHighlight";
import { SpeakingTask } from "./SpeakingTask";
import type { TaskProps } from "./types";
import { WritingTask } from "./WritingTask";

export const INSTRUCTIONS: Record<string, string> = {
  personal_introduction: "Introduce yourself in up to 30 seconds. This isn't scored, but it is sent to the institutions you choose.",
  read_aloud: "Look at the text below. You have about 35 seconds to prepare, then read it aloud as naturally and clearly as possible.",
  repeat_sentence: "You will hear a sentence. Repeat it exactly as you heard it, straight after the tone.",
  describe_image: "Look at the image. In 25 seconds, prepare to describe it in detail, then speak for up to 40 seconds.",
  retell_lecture: "Listen to the lecture. After a short pause, retell it in your own words within 40 seconds.",
  answer_short_question: "You will hear a question. Answer with a single word or a few words.",
  summarize_group_discussion: "Listen to the discussion. Then summarize it in up to 2 minutes, covering every speaker's view and any conclusion.",
  respond_to_situation: "Read and listen to the situation. You have 20 seconds to prepare, then respond as if you were really there.",
  summarize_written_text: "Summarize the passage in ONE sentence of 5–75 words. You have 10 minutes.",
  write_essay: "Write a 200–300 word essay on the topic below. You have 20 minutes.",
  rw_fill_blanks: "Choose the best option for each gap.",
  mcq_multiple_reading: "Read the text and answer the question. More than one answer is correct.",
  reorder_paragraphs: "Put the paragraphs into the correct order.",
  reading_fill_blanks: "Drag words from the box into the gaps. There are more words than gaps.",
  mcq_single_reading: "Read the text and choose the single best answer.",
  summarize_spoken_text: "Listen, then summarize the recording in 50–70 words. You have 10 minutes.",
  mcq_multiple_listening: "Listen and answer the question. More than one answer is correct.",
  listening_fill_blanks: "Type the missing word in each gap as you listen.",
  highlight_correct_summary: "Listen, then choose the paragraph that best summarizes the recording.",
  mcq_single_listening: "Listen and choose the single best answer.",
  select_missing_word: "A beep replaces the last word or phrase of the recording. Choose what is missing.",
  highlight_incorrect_words: "Follow the transcript as you listen and click the words that differ from what you hear.",
  write_from_dictation: "Type the sentence exactly as you hear it. Spelling counts.",
};

const SPEAKING = new Set(["personal_introduction", "read_aloud", "repeat_sentence", "describe_image", "retell_lecture", "answer_short_question", "summarize_group_discussion", "respond_to_situation"]);
const WRITING = new Set(["summarize_written_text", "write_essay", "summarize_spoken_text", "write_from_dictation"]);
const CHOICE = new Set(["mcq_single_reading", "mcq_multiple_reading", "mcq_single_listening", "mcq_multiple_listening", "highlight_correct_summary", "select_missing_word"]);
const FIB = new Set(["rw_fill_blanks", "reading_fill_blanks", "listening_fill_blanks"]);

export function TaskRunner(p: TaskProps) {
  const t = p.q.task;
  if (SPEAKING.has(t)) return <SpeakingTask {...p} />;
  if (WRITING.has(t)) return <WritingTask {...p} />;
  if (CHOICE.has(t)) return <ChoiceTask {...p} />;
  if (FIB.has(t)) return <FibTask {...p} />;
  if (t === "reorder_paragraphs") return <ReorderTask {...p} />;
  if (t === "highlight_incorrect_words") return <HighlightTask {...p} />;
  return <p>Unsupported task: {t}</p>;
}
