import { useMutation, useQuery } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** AI help while writing (F17): the composer's AI button rewrites the draft
 *  or writes a note summarizing the conversation. */
export const REWRITE_ACTIONS = ["improve", "fix", "formal", "friendly", "shorter"] as const;
export type AssistAction = (typeof REWRITE_ACTIONS)[number] | "translate" | "summarize";

export type WritingAssistInfo = {
  /** The installation's operator turned it on and there is an OpenAI key. */
  enabled: boolean;
  actions: AssistAction[];
  /** What the draft can be translated into. */
  languages: string[];
  text_max: number;
};

export type AssistInput = {
  action: AssistAction;
  text?: string;
  /** Translate into it; for the summary, the language to write it in. */
  language?: string;
  /** The conversation's number, for the summary. */
  conversation_id?: number;
};

/** Each language in its own words, the way people look for theirs. */
export const LANGUAGE_NAMES: Record<string, string> = {
  es: "Español", // i18n-ignore
  en: "English",
  pt: "Português", // i18n-ignore
  fr: "Français", // i18n-ignore
  de: "Deutsch",
  it: "Italiano",
  ja: "日本語",
  ko: "한국어",
  zh: "中文",
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/writing_assist`;
}

export function useWritingAssist(accountId: string) {
  return useQuery({
    queryKey: ["writingAssist", accountId] as const,
    queryFn: () => apiFetch<WritingAssistInfo>(base(accountId)),
    staleTime: 5 * 60_000,
  });
}

export function useAssist(accountId: string) {
  return useMutation({
    mutationFn: (input: AssistInput) =>
      apiFetch<{ text: string }>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
  });
}

export function assistProblemKey(err: unknown): string {
  const code = (err as { body?: { code?: unknown } })?.body?.code;
  if (typeof code === "string" && code.startsWith("writing_assist.")) {
    return `writingAssist.problems.${code.slice(15)}`;
  }
  return "writingAssist.problems.failed";
}
