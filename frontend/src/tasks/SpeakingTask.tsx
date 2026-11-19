import { useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";
import { AudioBox } from "../components/AudioBox";
import { Chart } from "../components/Chart";
import { Button, Notice, cx } from "../components/ui";
import { useApp } from "../lib/app";
import { beep, LiveTranscript, Recorder } from "../lib/audio";
import type { TaskProps } from "./types";

type Phase = "audio" | "prep" | "record" | "done";

export function SpeakingTask({ q, meta, onSubmit, accent, mode }: TaskProps) {
  const hasAudio = meta.audio;
  const prepSeconds = meta.prep ?? 0;
  const recordSeconds = meta.record ?? 40;
  const [phase, setPhase] = useState<Phase>(hasAudio ? "audio" : "prep");
  const [left, setLeft] = useState(prepSeconds);
  const [elapsed, setElapsed] = useState(0);
  const [level, setLevel] = useState(0);
  const [live, setLive] = useState("");
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<Recorder | null>(null);
  const tr = useRef<LiveTranscript | null>(null);
  const finishing = useRef(false);
  const { meta: appMeta } = useApp();
  const noAsr = appMeta?.engines.asr !== "whisper" && !LiveTranscript.supported();

  // reset when the question changes
  useEffect(() => {
    setPhase(hasAudio ? "audio" : "prep");
    setLeft(prepSeconds);
    setElapsed(0);
    setLive("");
    setError(null);
    finishing.current = false;
    return () => {
      rec.current?.abort();
      tr.current?.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.id]);

  // preparation countdown
  useEffect(() => {
    if (phase !== "prep") return;
    if (left <= 0) {
      startRecording();
      return;
    }
    const t = setTimeout(() => setLeft((l) => l - 1), 1000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, left]);

  // recording clock
  useEffect(() => {
    if (phase !== "record") return;
    const start = performance.now();
    const t = setInterval(() => setElapsed((performance.now() - start) / 1000), 200);
    return () => clearInterval(t);
  }, [phase]);

  async function startRecording() {
    if (!Recorder.supported()) {
      setError("This browser can't record audio. Use the latest Chrome or Edge.");
      return;
    }
    await beep();
    try {
      const r = new Recorder();
      await r.start({ maxSeconds: recordSeconds, silenceStop: 3, onLevel: setLevel, onAutoStop: () => finish() });
      rec.current = r;
      if (LiveTranscript.supported()) {
        const l = new LiveTranscript();
        l.onUpdate = setLive;
        l.start(accent === "en-IN" ? "en-IN" : accent);
        tr.current = l;
      }
      setPhase("record");
    } catch {
      setError("Microphone access was blocked. Allow the microphone in your browser's site settings, then try again.");
    }
  }

  async function finish() {
    if (finishing.current) return;
    finishing.current = true;
    const audio = (await rec.current?.stop()) ?? null;
    const t = (await tr.current?.stop()) ?? { text: "", confidence: null };
    rec.current = null;
    tr.current = null;
    setPhase("done");
    onSubmit({ response: { transcript: t.text, confidence: t.confidence }, audio });
  }

  const statusText =
    phase === "audio" ? "Listen to the audio" : phase === "prep" ? (prepSeconds ? `Recording in ${left} s` : "Get ready") : phase === "record" ? "Recording" : "Completed";

  return (
    <div className="space-y-5">
      {q.task === "read_aloud" && <p className="rounded-panel border border-line bg-white p-5 text-[19px] leading-[1.75]">{q.text}</p>}
      {q.task === "personal_introduction" && <p className="text-[17px] leading-relaxed">{q.prompt}</p>}
      {q.task === "describe_image" && q.chart && <Chart chart={q.chart} />}
      {q.task === "respond_to_situation" && <p className="rounded-panel border border-line bg-white p-5 text-[17px] leading-relaxed">{q.situation}</p>}
      {hasAudio && <AudioBox q={q} accent={accent} delay={3} onEnded={() => setPhase("prep")} />}
      {q.task === "summarize_group_discussion" && phase === "audio" && (
        <p className="text-sm text-ink-mute">You'll hear {new Set(q.audio_turns?.map((t) => t.speaker)).size} speakers. Take notes on what each person says.</p>
      )}

      {noAsr && q.task !== "personal_introduction" && (
        <Notice tone="warn">This browser can't transcribe speech and the server's Whisper model isn't installed, so answers can't be scored. Use Chrome or Edge, or set up Whisper (see the README).</Notice>
      )}
      {appMeta && (appMeta.engines.decode !== "ok" || appMeta.engines.pronunciation === "proxy") && (
        <Notice tone="error">
          The server's speech engine isn't fully set up, so speaking scores won't be accurate.{" "}
          {appMeta.engines.decode !== "ok" ? `Audio decoding: ${String(appMeta.engines.decode)}` : "Install the backend requirements: pip install -r requirements.txt"}
        </Notice>
      )}
      {error && <Notice tone="error">{error}</Notice>}

      <div className="rounded-panel border border-line bg-paper-raised px-5 py-4">
        <div className="flex flex-wrap items-center gap-4">
          <Mic className={cx("h-6 w-6", phase === "record" ? "text-coral" : "text-ink-mute")} aria-hidden />
          <div className="min-w-[200px] flex-1">
            <p className="text-[15px]" aria-live="polite">
              <span className="text-ink-soft">Status: </span>
              {statusText}
            </p>
            <div className="mt-2 flex items-center gap-3">
              <div className="h-1.5 flex-1 rounded-full bg-paper-sunk">
                <div
                  className={cx("h-full rounded-full", phase === "record" ? "bg-coral" : "bg-pine")}
                  style={{
                    width: `${phase === "record" ? Math.min(100, (elapsed / recordSeconds) * 100) : phase === "prep" && prepSeconds ? ((prepSeconds - left) / prepSeconds) * 100 : phase === "done" ? 100 : 0}%`,
                  }}
                />
              </div>
              <span className="w-12 text-right text-sm tabular-nums text-ink-soft">
                {phase === "record" ? `${Math.floor(elapsed)}/${recordSeconds}` : ""}
              </span>
            </div>
          </div>
          {phase === "record" && (
            <div className="flex h-6 w-24 items-end gap-[3px]" aria-hidden>
              {Array.from({ length: 12 }).map((_, i) => (
                <span key={i} className="w-1.5 rounded-sm bg-coral/80" style={{ height: `${Math.max(12, Math.min(100, level * 100 * (0.6 + ((i * 7) % 5) / 6)))}%` }} />
              ))}
            </div>
          )}
          {phase === "prep" && (
            <Button variant="secondary" onClick={() => setLeft(0)}>
              Start recording now
            </Button>
          )}
          {phase === "record" && (
            <Button variant="danger" onClick={finish}>
              <Square className="h-4 w-4" /> Stop and score
            </Button>
          )}
        </div>
        {phase === "record" && mode === "practice" && live && <p className="mt-3 border-t border-line pt-3 text-[15px] italic text-ink-soft">“{live}”</p>}
      </div>
      {phase === "record" && <p className="text-sm text-ink-mute">The microphone closes automatically after 3 seconds of silence, just like the real test.</p>}
    </div>
  );
}
