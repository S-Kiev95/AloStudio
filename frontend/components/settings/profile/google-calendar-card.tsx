"use client";

import { CalendarDays } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  RETURN_KEY,
  googleCalendarAuthorizeUrl,
  googleCalendarProblemKey,
  useDisconnectGoogleCalendar,
  useGoogleCalendar,
} from "@/lib/api/google-calendar";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";

/** Connect the user's Google Calendar (F17). Hidden while the installation
 *  has no Google credentials. */
export function GoogleCalendarCard() {
  const t = useT();
  const tag = useIntlTag();
  const status = useGoogleCalendar();
  const disconnect = useDisconnectGoogleCalendar();
  const [problem, setProblem] = useState<string | null>(null);
  const [going, setGoing] = useState(false);

  if (!status.data?.available) return null;
  const data = status.data;

  async function connect() {
    setProblem(null);
    setGoing(true);
    try {
      try {
        window.sessionStorage.setItem(RETURN_KEY, window.location.pathname);
      } catch {
        // No storage: the callback falls back to the accounts page.
      }
      window.location.assign(await googleCalendarAuthorizeUrl());
    } catch (err) {
      setGoing(false);
      setProblem(googleCalendarProblemKey(err));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarDays className="h-4 w-4" aria-hidden />
          {t("googleCalendar.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-fg-muted">{t("googleCalendar.intro")}</p>
        {data.connected ? (
          <>
            <p>
              {t("googleCalendar.connectedAs", { email: data.email ?? "Google" })}
              {data.last_synced_at
                ? ` · ${t("googleCalendar.lastSync", {
                    when: new Date(data.last_synced_at).toLocaleString(tag),
                  })}`
                : ` · ${t("googleCalendar.waiting")}`}
            </p>
            {data.problem ? (
              <p role="alert" className="text-danger">
                {data.problem === "revoked"
                  ? t("googleCalendar.revoked")
                  : t("googleCalendar.syncFailed", { detail: data.problem })}
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {data.problem === "revoked" ? (
                <Button type="button" size="sm" onClick={connect} loading={going}>
                  {t("googleCalendar.reconnect")}
                </Button>
              ) : null}
              <Button
                type="button"
                size="sm"
                variant="secondary"
                loading={disconnect.isPending}
                onClick={() =>
                  disconnect.mutate(undefined, {
                    onError: (err) => setProblem(googleCalendarProblemKey(err)),
                  })
                }
              >
                {t("googleCalendar.disconnect")}
              </Button>
            </div>
          </>
        ) : (
          <Button type="button" size="sm" onClick={connect} loading={going}>
            {t("googleCalendar.connect")}
          </Button>
        )}
        {problem ? (
          <p role="alert" className="text-danger">
            {translateOr(t, problem, t("googleCalendar.problems.failed"))}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
