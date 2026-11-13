"use client";

import { Compass } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import type { Contact } from "@/lib/api/contacts";
import {
  type ContactOrigin,
  ORIGIN_CHANNELS,
  ORIGIN_SOURCES,
  type OriginChannel,
  type OriginSource,
  useSetContactOrigin,
} from "@/lib/api/crm";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

export const sourceLabelKey = (s: OriginSource) => `origin.sources.${s}` as MessageKey;
export const channelLabelKey = (c: OriginChannel) => `origin.channels.${c}` as MessageKey;

/** One line that says how someone came: "Anuncio · WhatsApp", or just
 *  "WhatsApp" when they simply wrote on that channel. */
export function useOriginSummary() {
  const t = useT();
  return (origin: ContactOrigin) =>
    origin.source === "channel" && origin.channel
      ? t(channelLabelKey(origin.channel))
      : [t(sourceLabelKey(origin.source)), origin.channel ? t(channelLabelKey(origin.channel)) : null]
      .filter(Boolean)
      .join(" · ");
}

/** How a contact first reached the business, on their page: filled by their
 *  first conversation, or set by hand. */
export function ContactOriginCard({ accountId, contact }: { accountId: string; contact: Contact }) {
  const t = useT();
  const intlTag = useIntlTag();
  const summary = useOriginSummary();
  const origin = contact.origin ?? null;
  const save = useSetContactOrigin(accountId, contact.id);
  const [editing, setEditing] = useState(false);
  const [source, setSource] = useState<OriginSource | "">("");
  const [channel, setChannel] = useState<OriginChannel | "">("");
  const [detail, setDetail] = useState("");
  const [error, setError] = useState<string | null>(null);

  function startEditing() {
    setSource(origin?.source ?? "");
    setChannel(origin?.channel ?? "");
    setDetail(origin?.detail ?? "");
    setError(null);
    setEditing(true);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await save.mutateAsync({
        source: source || null,
        channel: channel || null,
        detail: detail.trim() || null,
      });
      setEditing(false);
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("origin.saveFailed"));
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Compass className="h-4 w-4 text-fg-muted" aria-hidden />
          {t("origin.title")}
        </CardTitle>
        {!editing ? (
          <Button size="sm" variant="ghost" onClick={startEditing}>
            {origin ? t("agenda.dialog.change") : t("origin.set")}
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-2">
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}
        {editing ? (
          <form onSubmit={submit} className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor="origin-source">{t("origin.source")}</Label>
                <select
                  id="origin-source"
                  value={source}
                  onChange={(e) => setSource(e.target.value as OriginSource | "")}
                  className={selectClassName("sm")}
                >
                  <option value="">{t("origin.unknown")}</option>
                  {ORIGIN_SOURCES.map((s) => (
                    <option key={s} value={s}>
                      {t(sourceLabelKey(s))}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="origin-channel">{t("origin.channel")}</Label>
                <select
                  id="origin-channel"
                  value={channel}
                  onChange={(e) => setChannel(e.target.value as OriginChannel | "")}
                  disabled={!source}
                  className={selectClassName("sm")}
                >
                  <option value="">{t("origin.noChannel")}</option>
                  {ORIGIN_CHANNELS.map((c) => (
                    <option key={c} value={c}>
                      {t(channelLabelKey(c))}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="space-y-1">
              <Label htmlFor="origin-detail">{t("origin.detail")}</Label>
              <Input
                id="origin-detail"
                value={detail}
                maxLength={255}
                disabled={!source}
                placeholder={t("origin.detailPlaceholder")}
                onChange={(e) => setDetail(e.target.value)}
              />
            </div>
            <div className="flex gap-2">
              <Button type="submit" size="sm" disabled={save.isPending}>
                {t("actions.save")}
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)}>
                {t("actions.cancel")}
              </Button>
            </div>
          </form>
        ) : origin ? (
          <div className="space-y-0.5">
            <p className="text-sm font-medium text-fg">{summary(origin)}</p>
            {origin.detail ? <p className="text-sm text-fg-muted">{origin.detail}</p> : null}
            {origin.at ? (
              <p className="text-xs text-fg-muted">
                {t("origin.since", {
                  date: new Date(origin.at * 1000).toLocaleDateString(intlTag, { dateStyle: "medium" }),
                })}
              </p>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-fg-muted">{t("origin.none")}</p>
        )}
      </CardContent>
    </Card>
  );
}
