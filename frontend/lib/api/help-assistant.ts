import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** AloStudio's help assistant: answers "how do I…?" from AloStudio's own
 *  help and points to the screen. Free uses the server's local model (no
 *  cost, slower); Fast uses OpenAI (faster, spends) when an administrator
 *  allowed it. */
export type HelpMode = "free" | "fast";

export type HelpInfo = {
  enabled: boolean;
  /** What this account can use, Free first. */
  modes: HelpMode[];
  /** The installation has an OpenAI key. */
  fast_possible: boolean;
  /** An administrator allowed Fast in this account. */
  fast_allowed: boolean;
  /** The user is an administrator (can allow or stop Fast). */
  can_manage: boolean;
  question_max: number;
  /** Screenshots and voice questions can be read (NVIDIA or Groq keys). */
  media: boolean;
};

export type HelpAnswer = {
  /** False: the help does not cover it (``answer`` says so). */
  known: boolean;
  answer: string;
  /** Where to go; ``path`` is under ``/accounts/{id}/``. */
  screen: { key: string; label: string; path: string } | null;
  /** E.g. "only an administrator uses that screen". */
  note: string | null;
  seconds: number;
  mode: HelpMode;
  /** What the voice question said, when there was one. */
  heard: string | null;
  /** What the screenshot shows, when there was one. */
  seen: string | null;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/help_assistant`;
}

function infoKey(accountId: string) {
  return ["helpAssistant", accountId] as const;
}

export function useHelpAssistant(accountId: string) {
  return useQuery({
    queryKey: infoKey(accountId),
    queryFn: () => apiFetch<HelpInfo>(base(accountId)),
    staleTime: 5 * 60_000,
  });
}

export function useAskHelp(accountId: string) {
  return useMutation({
    mutationFn: (input: {
      question: string;
      page?: string;
      mode?: HelpMode;
      /** ``data:image/…;base64,…`` */
      image?: string;
      /** ``data:audio/…;base64,…`` */
      audio?: string;
    }) =>
      apiFetch<HelpAnswer>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
  });
}

/** An administrator allows (or stops) Fast for the whole account. */
export function useAllowFastHelp(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fast: boolean) =>
      apiFetch<HelpInfo>(`${base(accountId)}/settings`, {
        method: "PUT",
        body: JSON.stringify({ fast }),
      }),
    onSuccess: (info) => qc.setQueryData(infoKey(accountId), info),
  });
}

export function helpProblemKey(err: unknown): string {
  const code = (err as { body?: { code?: unknown } })?.body?.code;
  if (typeof code === "string" && code.startsWith("help_assistant.")) {
    return `helpAssistant.problems.${code.slice(15)}`;
  }
  return "helpAssistant.problems.failed";
}
