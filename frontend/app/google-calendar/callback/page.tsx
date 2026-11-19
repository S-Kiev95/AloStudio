"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import {
  RETURN_KEY,
  googleCalendarProblemKey,
  useConnectGoogleCalendar,
} from "@/lib/api/google-calendar";
import { useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";

/** Google sends the browser back here after the consent screen (F17). The
 *  code goes to the backend, then the user returns to where they started. */
function Exchange() {
  const t = useT();
  const router = useRouter();
  const params = useSearchParams();
  const connect = useConnectGoogleCalendar();
  const [problem, setProblem] = useState<string | null>(null);
  // The code works once: never post it twice (React may run effects twice).
  const sent = useRef(false);

  useEffect(() => {
    if (sent.current) return;
    sent.current = true;
    const code = params.get("code");
    const state = params.get("state");
    if (params.get("error") || !code || !state) {
      setProblem("googleCalendar.problems.cancelled");
      return;
    }
    connect.mutate(
      { code, state },
      {
        onSuccess: () => {
          let back = "/accounts";
          try {
            back = window.sessionStorage.getItem(RETURN_KEY) || back;
            window.sessionStorage.removeItem(RETURN_KEY);
          } catch {
            // No storage: the accounts page.
          }
          router.replace(back);
        },
        onError: (err) => setProblem(googleCalendarProblemKey(err)),
      },
    );
  }, [params, router, connect]);

  return (
    <div className="mx-auto max-w-md space-y-4 p-8">
      <h1 className="text-xl font-medium text-fg">{t("googleCalendar.title")}</h1>
      {problem ? (
        <>
          <p role="alert" className="text-sm text-danger">
            {translateOr(t, problem, t("googleCalendar.problems.failed"))}
          </p>
          <Link href="/accounts" className="text-sm text-info hover:underline">
            {t("googleCalendar.back")}
          </Link>
        </>
      ) : (
        <p className="text-sm text-fg-muted">{t("googleCalendar.connecting")}</p>
      )}
    </div>
  );
}

export default function GoogleCalendarCallbackPage() {
  return (
    <Suspense>
      <Exchange />
    </Suspense>
  );
}
