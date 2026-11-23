"use client";

import { ArrowRight, CircleHelp, Image as ImageIcon, ImagePlus, Loader2, Mic, Square, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  helpProblemKey,
  type HelpAnswer,
  type HelpMode,
  useAllowFastHelp,
  useAskHelp,
  useHelpAssistant,
} from "@/lib/api/help-assistant";
import { useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";
import { cn } from "@/lib/utils";

type Turn = { question: string; imageLabel?: string; answer: HelpAnswer };
type Attached = { dataUrl: string; label: string };

const MODE_KEY = "alostudio:help-mode";
const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];
const IMAGE_MAX_BYTES = 5 * 1024 * 1024;
// A voice question, not a voice note: a minute is plenty.
const RECORD_MAX_SECONDS = 60;

function readMode(): HelpMode | null {
  try {
    const value = window.localStorage.getItem(MODE_KEY);
    return value === "free" || value === "fast" ? value : null;
  } catch {
    return null;
  }
}

function asDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/** Topbar "?" button: ask how to do something in AloStudio, from AloStudio's
 *  own help, by writing, with a screenshot or by voice. Free uses the free
 *  model (no cost); Fast uses OpenAI when an administrator allowed it.
 *  Hidden while neither is set up, except for an administrator who can
 *  allow Fast. */
export function HelpButton({ accountId }: { accountId: string }) {
  const t = useT();
  const pathname = usePathname() ?? "";
  const info = useHelpAssistant(accountId);
  const ask = useAskHelp(accountId);
  const allowFast = useAllowFastHelp(accountId);
  const [picked, setPicked] = useState<HelpMode | null>(null);
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const [image, setImage] = useState<Attached | null>(null);
  const [audio, setAudio] = useState<Attached | null>(null);
  const [recordingFor, setRecordingFor] = useState<number | null>(null);
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const secondsRef = useRef(0);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    function onDocClick(e: MouseEvent) {
      if (detailsRef.current && !detailsRef.current.contains(e.target as Node)) {
        detailsRef.current.removeAttribute("open");
        setOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        detailsRef.current?.removeAttribute("open");
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  // Seconds counter while recording; it stops by itself at the limit.
  useEffect(() => {
    if (recordingFor === null) return;
    secondsRef.current = recordingFor;
    if (recordingFor >= RECORD_MAX_SECONDS) {
      recorderRef.current?.stop();
      return;
    }
    const id = window.setTimeout(
      () => setRecordingFor((s) => (s === null ? s : s + 1)),
      1000,
    );
    return () => window.clearTimeout(id);
  }, [recordingFor]);

  const data = info.data;
  if (!data || !(data.enabled || (data.can_manage && data.fast_possible))) return null;
  const max = data.question_max;
  const wanted = picked ?? (open ? readMode() : null);
  const mode: HelpMode | null =
    wanted && data.modes.includes(wanted) ? wanted : (data.modes[0] ?? null);
  const recording = recordingFor !== null;

  function pick(next: HelpMode) {
    setPicked(next);
    try {
      window.localStorage.setItem(MODE_KEY, next);
    } catch {
      // No storage: the choice lasts while the panel is open.
    }
  }

  async function takeImage(file: File | null | undefined) {
    if (!file) return;
    if (!IMAGE_TYPES.includes(file.type)) {
      setProblem("helpAssistant.problems.media_type");
      return;
    }
    if (file.size > IMAGE_MAX_BYTES) {
      setProblem("helpAssistant.problems.media_size");
      return;
    }
    setProblem(null);
    setImage({ dataUrl: await asDataUrl(file), label: file.name || t("helpAssistant.screenshot") });
  }

  async function startRecording() {
    setProblem(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setProblem("helpAssistant.problems.microphone");
      return;
    }
    const recorder = new MediaRecorder(stream);
    const chunks: Blob[] = [];
    recorder.ondataavailable = (e) => chunks.push(e.data);
    recorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      const seconds = Math.max(1, secondsRef.current);
      setRecordingFor(null);
      recorderRef.current = null;
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      setAudio({
        dataUrl: await asDataUrl(blob),
        label: t("helpAssistant.audioLabel", { seconds: String(seconds) }),
      });
    };
    recorderRef.current = recorder;
    recorder.start();
    setRecordingFor(0);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = question.trim();
    if ((!text && !image && !audio) || ask.isPending || !mode || recording) return;
    setProblem(null);
    const imageLabel = image?.label;
    ask.mutate(
      { question: text, page: pathname, mode, image: image?.dataUrl, audio: audio?.dataUrl },
      {
        onSuccess: (answer) => {
          const shown = [
            answer.heard ? `«${answer.heard}»` : "",
            text,
          ]
            .filter(Boolean)
            .join(" · ");
          setTurns((prev) => [...prev, { question: shown, imageLabel, answer }].slice(-5));
          setQuestion("");
          setImage(null);
          setAudio(null);
        },
        onError: (err) => setProblem(helpProblemKey(err)),
      },
    );
  }

  const attached: Array<[string, Attached, () => void]> = [];
  if (image) attached.push(["image", image, () => setImage(null)]);
  if (audio) attached.push(["audio", audio, () => setAudio(null)]);

  return (
    <details
      ref={detailsRef}
      className="group relative"
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary
        aria-label={t("helpAssistant.title")}
        title={t("helpAssistant.title")}
        className={cn(
          "relative flex h-10 w-10 cursor-pointer list-none items-center justify-center rounded-control text-fg-muted transition-colors",
          "hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
        )}
      >
        <CircleHelp className="h-5 w-5" aria-hidden />
      </summary>

      <div
        role="dialog"
        aria-label={t("helpAssistant.title")}
        className="z-30 flex flex-col overflow-hidden rounded-md border border-glass bg-surface-2 shadow-menu max-sm:fixed max-sm:inset-x-3 max-sm:top-[4.5rem] max-sm:max-h-[calc(100dvh-5.5rem)] max-sm:w-auto sm:absolute sm:right-0 sm:mt-1.5 sm:w-[24rem] sm:max-w-[calc(100vw-2rem)]"
      >
        <div className="border-b border-glass px-3 py-2.5">
          <h2 className="text-sm font-medium text-fg">{t("helpAssistant.title")}</h2>
          <p className="text-xs text-fg-muted">{t("helpAssistant.intro")}</p>
          {data.modes.length > 1 ? (
            <div role="radiogroup" aria-label={t("helpAssistant.modeLabel")} className="mt-2 flex gap-1.5">
              {data.modes.map((m) => (
                <button
                  key={m}
                  type="button"
                  role="radio"
                  aria-checked={mode === m}
                  onClick={() => pick(m)}
                  className={cn(
                    "flex-1 rounded-control border px-2 py-1 text-left text-xs transition-colors",
                    mode === m
                      ? "border-neon bg-focused text-lit"
                      : "border-glass bg-field text-fg-muted hover:bg-hover-glass",
                  )}
                >
                  <span className="block font-medium">
                    {m === "fast" ? t("helpAssistant.modeFast") : t("helpAssistant.modeFree")}
                  </span>
                  <span className="block text-[11px] opacity-80">
                    {m === "fast" ? t("helpAssistant.modeFastHint") : t("helpAssistant.modeFreeHint")}
                  </span>
                </button>
              ))}
            </div>
          ) : null}
        </div>

        <div className="max-h-[24rem] space-y-3 overflow-y-auto px-3 py-3 text-sm">
          {turns.length === 0 && !ask.isPending ? (
            <p className="text-xs text-fg-muted">{t("helpAssistant.examples")}</p>
          ) : null}
          {turns.map((turn, i) => (
            <div key={i} className="space-y-1.5">
              <p className="flex flex-wrap items-center gap-1.5 text-xs font-medium text-fg-muted">
                {turn.question ? <span>{turn.question}</span> : null}
                {turn.imageLabel ? (
                  <span className="inline-flex items-center gap-1">
                    <ImageIcon className="h-3 w-3 shrink-0" aria-hidden />
                    {turn.imageLabel}
                  </span>
                ) : null}
              </p>
              <p className={cn("text-fg", !turn.answer.known && "text-fg-muted")}>
                {turn.answer.answer}
              </p>
              {turn.answer.screen ? (
                <Link
                  href={
                    turn.answer.screen.path
                      ? `/accounts/${accountId}/${turn.answer.screen.path}`
                      : `/accounts/${accountId}`
                  }
                  onClick={() => {
                    detailsRef.current?.removeAttribute("open");
                    setOpen(false);
                  }}
                  className="inline-flex items-center gap-1 text-xs font-medium text-info hover:underline"
                >
                  {t("helpAssistant.goTo", { screen: turn.answer.screen.label })}
                  <ArrowRight className="h-3.5 w-3.5" aria-hidden />
                </Link>
              ) : null}
              {turn.answer.note ? (
                <p className="text-xs text-fg-muted">{turn.answer.note}</p>
              ) : null}
              {turn.answer.seen ? (
                <p className="text-[11px] text-fg-muted">
                  {t("helpAssistant.seen", { text: turn.answer.seen })}
                </p>
              ) : null}
            </div>
          ))}
          {ask.isPending ? (
            <p className="inline-flex items-center gap-2 text-xs text-fg-muted" role="status">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              {mode === "fast" ? t("helpAssistant.thinkingFast") : t("helpAssistant.thinking")}
            </p>
          ) : null}
          {problem ? (
            <p role="alert" className="text-xs text-danger">
              {translateOr(t, problem, t("helpAssistant.problems.failed"))}
            </p>
          ) : null}
        </div>

        {data.can_manage && data.fast_possible ? (
          <label className="flex items-center gap-2 border-t border-glass px-3 py-2 text-xs text-fg-muted">
            <input
              type="checkbox"
              checked={data.fast_allowed}
              disabled={allowFast.isPending}
              onChange={(e) => allowFast.mutate(e.target.checked)}
            />
            {t("helpAssistant.allowFast")}
          </label>
        ) : null}

        {attached.length || recording ? (
          <div className="flex flex-wrap gap-1.5 border-t border-glass px-2 pt-2 text-xs">
            {recording ? (
              <span className="inline-flex items-center gap-1 px-1 text-danger" role="status">
                <span className="h-2 w-2 animate-pulse rounded-full bg-danger-solid" aria-hidden />
                {t("helpAssistant.recording", { seconds: String(recordingFor) })}
              </span>
            ) : null}
            {attached.map(([kind, item, remove]) => (
              <span
                key={kind}
                className="inline-flex max-w-[14rem] items-center gap-1 rounded-pill border border-glass bg-field px-2 py-0.5"
              >
                <span className="truncate">{item.label}</span>
                <button
                  type="button"
                  onClick={remove}
                  aria-label={t("helpAssistant.remove", { item: item.label })}
                  className="text-fg-muted hover:text-fg"
                >
                  <X className="h-3 w-3" aria-hidden />
                </button>
              </span>
            ))}
          </div>
        ) : null}

        <form onSubmit={submit} className="flex gap-2 border-t border-glass p-2">
          {data.media ? (
            <>
              <input
                ref={fileRef}
                type="file"
                accept={IMAGE_TYPES.join(",")}
                className="hidden"
                tabIndex={-1}
                aria-label={t("helpAssistant.attachImage")}
                onChange={(e) => {
                  void takeImage(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                aria-label={t("helpAssistant.attachImage")}
                title={t("helpAssistant.attachImage")}
                className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-control text-fg-muted hover:bg-hover-glass hover:text-fg"
              >
                <ImagePlus className="h-4 w-4" aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => (recording ? recorderRef.current?.stop() : void startRecording())}
                aria-label={recording ? t("helpAssistant.stopRecording") : t("helpAssistant.record")}
                title={recording ? t("helpAssistant.stopRecording") : t("helpAssistant.record")}
                aria-pressed={recording}
                className={cn(
                  "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-control hover:bg-hover-glass",
                  recording ? "text-danger" : "text-fg-muted hover:text-fg",
                )}
              >
                {recording ? (
                  <Square className="h-4 w-4" aria-hidden />
                ) : (
                  <Mic className="h-4 w-4" aria-hidden />
                )}
              </button>
            </>
          ) : null}
          <input
            ref={inputRef}
            value={question}
            maxLength={max}
            onChange={(e) => setQuestion(e.target.value)}
            onPaste={(e) => {
              if (!data.media) return;
              const file = [...e.clipboardData.files].find((f) => f.type.startsWith("image/"));
              if (file) {
                e.preventDefault();
                void takeImage(file);
              }
            }}
            aria-label={t("helpAssistant.question")}
            placeholder={t("helpAssistant.placeholder")}
            className="glass-field h-9 min-w-0 flex-1 rounded-control border border-glass bg-field px-2.5 text-xs text-fg placeholder:text-fg-muted"
          />
          <Button
            type="submit"
            variant="ai"
            size="sm"
            disabled={(!question.trim() && !image && !audio) || ask.isPending || !mode || recording}
          >
            {t("helpAssistant.ask")}
          </Button>
        </form>
      </div>
    </details>
  );
}
