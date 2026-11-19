import { useMutation, useQuery } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** AloStudio's help assistant: a small local model that answers "how do
 *  I…?" from AloStudio's own help and points to the screen. */
export type HelpAnswer = {
  /** False: the help does not cover it (``answer`` says so). */
  known: boolean;
  answer: string;
  /** Where to go; ``path`` is under ``/accounts/{id}/``. */
  screen: { key: string; label: string; path: string } | null;
  /** E.g. "only an administrator uses that screen". */
  note: string | null;
  seconds: number;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/help_assistant`;
}

export function useHelpAssistant(accountId: string) {
  return useQuery({
    queryKey: ["helpAssistant", accountId] as const,
    queryFn: () =>
      apiFetch<{ enabled: boolean; question_max: number }>(base(accountId)),
    staleTime: 5 * 60_000,
  });
}

export function useAskHelp(accountId: string) {
  return useMutation({
    mutationFn: (input: { question: string; page?: string }) =>
      apiFetch<HelpAnswer>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
  });
}

export function helpProblemKey(err: unknown): string {
  const code = (err as { body?: { code?: unknown } })?.body?.code;
  if (typeof code === "string" && code.startsWith("help_assistant.")) {
    return `helpAssistant.problems.${code.slice(15)}`;
  }
  return "helpAssistant.problems.failed";
}
