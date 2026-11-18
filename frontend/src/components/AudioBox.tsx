import { useEffect, useRef, useState } from "react";
import { Volume2 } from "lucide-react";
import { playUrl, speak, speakTurns, stopSpeech } from "../lib/audio";
import type { Question } from "../lib/types";
import { cx } from "./ui";

type Phase = "waiting" | "playing" | "done";

/** Exam-style audio box: counts down, plays the prompt once, reports when finished. */
export function AudioBox({
  q,
  delay = 3,
  accent = "en-GB",
  onEnded,
  allowReplay = false,
  cutAtEnd = false,
}: {
  q: Question;
  delay?: number;
  accent?: string;
  onEnded?: () => void;
  allowReplay?: boolean;
  cutAtEnd?: boolean; // Select Missing Word: a beep replaces the final word
}) {
  const [phase, setPhase] = useState<Phase>("waiting");
  const [left, setLeft] = useState(delay);
  const [progress, setProgress] = useState(0);
  const ended = useRef(onEnded);
  ended.current = onEnded;

  const play = async () => {
    setPhase("playing");
    setProgress(0);
    if (q.audio_url) await playUrl(q.audio_url, setProgress);
    else if (q.audio_turns) await speakTurns(q.audio_turns, { accent, onProgress: setProgress });
    else if (q.audio_text) await speak(q.audio_text, { accent, onProgress: setProgress });
    if (cutAtEnd) {
      const { beep } = await import("../lib/audio");
      await beep(500, 660);
    }
    setProgress(1);
    setPhase("done");
    ended.current?.();
  };

  useEffect(() => {
    setPhase("waiting");
    setLeft(delay);
    let n = delay;
    const t = window.setInterval(() => {
      n -= 1;
      setLeft(n);
      if (n <= 0) {
        clearInterval(t);
        play();
      }
    }, 1000);
    return () => {
      clearInterval(t);
      stopSpeech();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.id]);

  return (
    <div className="flex items-center gap-4 rounded-panel border border-line bg-paper-raised px-5 py-4" aria-live="polite">
      <Volume2 className={cx("h-6 w-6 shrink-0", phase === "playing" ? "text-pine" : "text-ink-mute")} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-[15px]">
          <span className="text-ink-soft">Status: </span>
          {phase === "waiting" && `Beginning in ${left} second${left === 1 ? "" : "s"}`}
          {phase === "playing" && "Playing"}
          {phase === "done" && "Completed"}
        </p>
        <div className="mt-2 h-1.5 rounded-full bg-paper-sunk">
          <div className="h-full rounded-full bg-pine transition-[width] duration-300" style={{ width: `${progress * 100}%` }} />
        </div>
      </div>
      {allowReplay && phase === "done" && (
        <button className="text-sm font-semibold text-pine hover:underline" onClick={play}>
          Play again
        </button>
      )}
    </div>
  );
}
