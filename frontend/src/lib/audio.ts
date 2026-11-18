/* Browser audio: exam beep, text-to-speech prompts, recording with PTE-style silence cut-off,
   and live speech recognition (used as the transcript when the server has no Whisper model). */

let ctx: AudioContext | null = null;
const ac = () => (ctx ??= new (window.AudioContext || (window as any).webkitAudioContext)());

export function beep(ms = 350, freq = 880): Promise<void> {
  return new Promise((resolve) => {
    try {
      const a = ac();
      const o = a.createOscillator();
      const g = a.createGain();
      o.frequency.value = freq;
      g.gain.setValueAtTime(0.0001, a.currentTime);
      g.gain.exponentialRampToValueAtTime(0.25, a.currentTime + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + ms / 1000);
      o.connect(g).connect(a.destination);
      o.start();
      o.stop(a.currentTime + ms / 1000 + 0.02);
      setTimeout(resolve, ms + 30);
    } catch {
      resolve();
    }
  });
}

// ------------------------------------------------------------------ text-to-speech
function voices(): SpeechSynthesisVoice[] {
  return typeof speechSynthesis === "undefined" ? [] : speechSynthesis.getVoices().filter((v) => v.lang.startsWith("en"));
}

export function voicesReady(): Promise<void> {
  if (typeof speechSynthesis === "undefined" || voices().length) return Promise.resolve();
  return new Promise((r) => {
    const done = () => r();
    speechSynthesis.addEventListener("voiceschanged", done, { once: true });
    setTimeout(done, 1200);
  });
}

function pickVoice(accent: string, n = 0): SpeechSynthesisVoice | undefined {
  const all = voices();
  const match = all.filter((v) => v.lang.replace("_", "-") === accent);
  const pool = match.length ? [...match, ...all.filter((v) => !match.includes(v))] : all;
  const natural = pool.filter((v) => /natural|google|neural|premium|enhanced/i.test(v.name));
  const ordered = [...natural, ...pool.filter((v) => !natural.includes(v))];
  return ordered[n % Math.max(1, ordered.length)];
}

let cancelled = false;

export function stopSpeech() {
  cancelled = true;
  if (typeof speechSynthesis !== "undefined") speechSynthesis.cancel();
  currentAudio?.pause();
}

let currentAudio: HTMLAudioElement | null = null;

export interface SpeakOpts {
  accent?: string;
  voiceIndex?: number;
  rate?: number;
  pitch?: number;
  onProgress?: (fraction: number) => void;
}

/** Speak text sentence by sentence (avoids Chrome's ~15 s utterance cut-off) and report progress. */
export async function speak(text: string, o: SpeakOpts = {}): Promise<void> {
  cancelled = false;
  await voicesReady();
  if (typeof speechSynthesis === "undefined") return;
  const chunks = text.match(/[^.!?]+[.!?]*\s*/g) ?? [text];
  const total = text.length || 1;
  let done = 0;
  for (const chunk of chunks) {
    if (cancelled) return;
    await new Promise<void>((resolve) => {
      const u = new SpeechSynthesisUtterance(chunk.trim());
      const v = pickVoice(o.accent ?? "en-GB", o.voiceIndex ?? 0);
      if (v) u.voice = v;
      u.lang = v?.lang ?? o.accent ?? "en-GB";
      u.rate = o.rate ?? 0.98;
      u.pitch = o.pitch ?? 1;
      u.onboundary = (e) => o.onProgress?.((done + e.charIndex) / total);
      u.onend = u.onerror = () => resolve();
      speechSynthesis.speak(u);
    });
    done += chunk.length;
    o.onProgress?.(done / total);
  }
}

/** Multi-speaker audio for Summarize Group Discussion: a different voice and pitch per speaker. */
export async function speakTurns(turns: { speaker: string; text: string }[], o: SpeakOpts = {}) {
  cancelled = false;
  const speakers = [...new Set(turns.map((t) => t.speaker))];
  const total = turns.reduce((s, t) => s + t.text.length, 0) || 1;
  let done = 0;
  for (const t of turns) {
    if (cancelled) return;
    const i = speakers.indexOf(t.speaker);
    await speak(t.text, {
      ...o,
      voiceIndex: i,
      pitch: [1, 0.82, 1.18][i % 3],
      onProgress: (f) => o.onProgress?.((done + f * t.text.length) / total),
    });
    done += t.text.length;
    await new Promise((r) => setTimeout(r, 350));
  }
}

export function playUrl(url: string, onProgress?: (f: number) => void): Promise<void> {
  return new Promise((resolve) => {
    const a = new Audio(url);
    currentAudio = a;
    a.ontimeupdate = () => a.duration && onProgress?.(a.currentTime / a.duration);
    a.onended = a.onerror = () => resolve();
    a.play().catch(() => resolve());
  });
}

// ------------------------------------------------------------------ recording
export interface RecorderOpts {
  maxSeconds: number;
  /** PTE closes the mic after 3 s of silence (before or after speaking). */
  silenceStop?: number;
  onLevel?: (level: number) => void;
  onAutoStop?: (reason: "silence" | "time") => void;
}

export class Recorder {
  private rec?: MediaRecorder;
  private stream?: MediaStream;
  private chunks: Blob[] = [];
  private raf = 0;
  private timer = 0;
  private stopped?: Promise<Blob>;
  startedAt = 0;

  static supported() {
    return typeof window !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";
  }

  async start(o: RecorderOpts) {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"].find((m) => MediaRecorder.isTypeSupported(m));
    this.rec = new MediaRecorder(this.stream, mime ? { mimeType: mime } : undefined);
    this.chunks = [];
    this.rec.ondataavailable = (e) => e.data.size && this.chunks.push(e.data);
    this.stopped = new Promise((res) => {
      this.rec!.onstop = () => res(new Blob(this.chunks, { type: this.rec?.mimeType || "audio/webm" }));
    });
    this.rec.start(250);
    this.startedAt = performance.now();

    const a = ac();
    if (a.state === "suspended") await a.resume();
    const src = a.createMediaStreamSource(this.stream);
    const an = a.createAnalyser();
    an.fftSize = 1024;
    src.connect(an);
    const buf = new Float32Array(an.fftSize);
    let lastVoice = performance.now();
    let spoke = false;
    let noise = 0.005;
    const silence = (o.silenceStop ?? 3) * 1000;
    const tick = () => {
      an.getFloatTimeDomainData(buf);
      let sum = 0;
      for (const x of buf) sum += x * x;
      const rms = Math.sqrt(sum / buf.length);
      if (!spoke) noise = Math.min(noise * 0.95 + rms * 0.05, 0.02);
      const voiced = rms > Math.max(0.012, noise * 3);
      o.onLevel?.(Math.min(1, rms * 12));
      const t = performance.now();
      if (voiced) {
        lastVoice = t;
        spoke = true;
      }
      if (o.silenceStop !== 0 && t - lastVoice > silence) {
        o.onAutoStop?.("silence");
        return;
      }
      this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
    this.timer = window.setTimeout(() => o.onAutoStop?.("time"), o.maxSeconds * 1000);
  }

  async stop(): Promise<Blob | null> {
    cancelAnimationFrame(this.raf);
    clearTimeout(this.timer);
    if (!this.rec || this.rec.state === "inactive") return null;
    this.rec.stop();
    const blob = await this.stopped!;
    this.stream?.getTracks().forEach((t) => t.stop());
    return blob;
  }

  abort() {
    cancelAnimationFrame(this.raf);
    clearTimeout(this.timer);
    try {
      this.rec?.stop();
    } catch {
      /* already stopped */
    }
    this.stream?.getTracks().forEach((t) => t.stop());
  }
}

// ------------------------------------------------------------------ speech recognition (Chrome / Edge)
export class LiveTranscript {
  private r: any;
  text = "";
  confidence: number[] = [];
  interim = "";
  onUpdate?: (text: string) => void;

  static supported() {
    return typeof window !== "undefined" && !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
  }

  start(lang = "en-US") {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    this.r = new SR();
    this.r.lang = lang;
    this.r.continuous = true;
    this.r.interimResults = true;
    this.r.maxAlternatives = 1;
    this.r.onresult = (e: any) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) {
          this.text += (this.text ? " " : "") + res[0].transcript.trim();
          if (res[0].confidence) this.confidence.push(res[0].confidence);
        } else interim += res[0].transcript;
      }
      this.interim = interim;
      this.onUpdate?.((this.text + " " + interim).trim());
    };
    this.r.onend = () => {
      if (this.r) {
        try {
          this.r.start(); // Chrome ends continuous sessions on its own; keep listening until stop()
        } catch {
          /* ignore */
        }
      }
    };
    try {
      this.r.start();
    } catch {
      /* ignore */
    }
  }

  async stop(): Promise<{ text: string; confidence: number | null }> {
    const r = this.r;
    this.r = null;
    if (r) {
      await new Promise<void>((res) => {
        r.onend = () => res();
        try {
          r.stop();
        } catch {
          res();
        }
        setTimeout(res, 1200);
      });
    }
    const text = (this.text + " " + this.interim).trim();
    const c = this.confidence.length ? this.confidence.reduce((a, b) => a + b, 0) / this.confidence.length : null;
    return { text, confidence: c };
  }
}
