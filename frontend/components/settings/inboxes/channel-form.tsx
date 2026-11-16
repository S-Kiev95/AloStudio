"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, type ReactNode, useState } from "react";

import { Facebook, Instagram } from "@/components/ui/brand-icons";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { selectClassName } from "@/components/ui/select";
import { ApiError } from "@/lib/api/errors";
import { type ChannelPayload, useCreateInbox } from "@/lib/api/inboxes";
import { startOAuth } from "@/lib/api/instagram";
import { usePublicInstallation } from "@/lib/api/installation";
import { channelDef, type ChannelDef } from "@/lib/inboxes/channel-catalog";

import { FacebookPageConnect } from "./facebook-page-connect";
import { WhatsappEmbeddedSignup } from "./whatsapp-embedded-signup";
import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

const META_CHANNELS = new Set(["whatsapp", "facebook", "instagram"]);

export function ChannelForm({
  accountId,
  channel,
}: {
  accountId: string;
  channel: string;
}) {
  const t = useT();
  // Catalog texts are keys, or product names t() hands back unchanged.
  const tx = (text: string) => t(text as MessageKey);
  const def = channelDef(channel);
  const router = useRouter();
  const create = useCreateInbox(accountId);
  const installation = usePublicInstallation();
  const multitenant = Boolean(installation.data?.multitenant);
  const [name, setName] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const inboxesHref = `/accounts/${accountId}/settings/inboxes`;

  if (!def) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-danger">{t("settingsInboxes.unknownChannel")} {channel}</p>
        <Link href={`${inboxesHref}/new`} className={buttonVariants({ size: "sm" })}>
          {t("settingsInboxes.pickChannel")}
        </Link>
      </div>
    );
  }

  function setField(n: string, v: string) {
    setValues((prev) => ({ ...prev, [n]: v }));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError(t("settingsInboxes.nameRequired"));
      return;
    }
    for (const f of def!.fields) {
      if (f.required && !values[f.name]?.trim()) {
        setError(t("settingsInboxes.fieldMissing", { field: tx(f.label) }));
        return;
      }
    }
    try {
      const created = await create.mutateAsync({
        name: name.trim(),
        channel: buildChannel(def!, values),
      });
      // Land on the detail page so the webhook URL + verify token (what the
      // user pastes into the provider) are immediately visible.
      router.push(`${inboxesHref}/${created.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("settingsInboxes.createFailed"),
      );
    }
  }

  return (
    <div className="max-w-lg space-y-4">
      <div>
        <Link
          href={`${inboxesHref}/new`}
          className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          {t("settingsInboxes.changeChannel")}
        </Link>
        <h2 className="mt-2 text-xl font-medium text-fg">{tx(def.label)}</h2>
        <p className="text-sm text-fg-muted">{def.blurb}</p>
      </div>

      {channel === "whatsapp" ? (
        <WhatsappEmbeddedSignup
          accountId={accountId}
          onlyWhenReady={!multitenant}
          showManualHint={!multitenant}
        />
      ) : null}

      {channel === "facebook" ? (
        <FacebookPageConnect
          accountId={accountId}
          showManualHint={!multitenant}
        />
      ) : null}

      {channel === "instagram" ? (
        <InstagramOAuthConnect
          accountId={accountId}
          showManualHint={!multitenant}
        />
      ) : null}

      {/* A multitenant install connects Meta channels only through Meta's
          own flows: no tokens pasted by hand. */}
      {!multitenant || !META_CHANNELS.has(channel) ? (
      <form
        onSubmit={submit}
        className="space-y-4 rounded-md border border-glass bg-surface p-5"
      >
        <Field label={t("settingsInboxes.inboxName")} required>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("settingsInboxes.inboxNamePlaceholder")}
          />
        </Field>

        {def.fields.map((f) => (
          <Field
            key={f.name}
            label={tx(f.label)}
            required={f.required}
            help={f.help ? tx(f.help) : undefined}
          >
            {f.type === "checkbox" ? (
              <label className="flex items-center gap-2 text-sm text-fg">
                <input
                  type="checkbox"
                  checked={(values[f.name] ?? (f.default ? "true" : "")) === "true"}
                  onChange={(e) =>
                    setField(f.name, e.target.checked ? "true" : "")
                  }
                  className="h-4 w-4 rounded border-glass accent-neon"
                />
                {t("settingsNotif.enable")}
              </label>
            ) : f.type === "select" ? (
              <select
                value={values[f.name] ?? f.options?.[0]?.value ?? ""}
                onChange={(e) => setField(f.name, e.target.value)}
                className={selectClassName()}
              >
                {f.options?.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            ) : (
              <Input
                type={f.type === "password" ? "password" : "text"}
                value={values[f.name] ?? ""}
                onChange={(e) => setField(f.name, e.target.value)}
                placeholder={f.placeholder ? tx(f.placeholder) : undefined}
                // Chrome filled the saved AloStudio login into "Usuario
                // IMAP" and the password to match, which reached the
                // server as a mailbox that could not authenticate.
                autoComplete={f.type === "password" ? "new-password" : "off"}
              />
            )}
          </Field>
        ))}

        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}

        <div className="flex justify-end gap-2">
          <Link
            href={inboxesHref}
            className={buttonVariants({ variant: "secondary", size: "sm" })}
          >
            {t("actions.cancel")}
          </Link>
          <Button type="submit" size="sm" loading={create.isPending}>
            {t("settingsInboxes.createChannel")}
          </Button>
        </div>
      </form>
      ) : null}
    </div>
  );
}

function InstagramOAuthConnect({
  accountId,
  showManualHint,
}: {
  accountId: string;
  showManualHint: boolean;
}) {
  const t = useT();
  const [starting, setStarting] = useState<"facebook" | "instagram" | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  async function connect(flow: "facebook" | "instagram") {
    setError(null);
    setStarting(flow);
    try {
      await startOAuth(accountId, flow);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : t("settingsInboxes.igConnectFailed"),
      );
      setStarting(null);
    }
  }

  return (
    <div className="space-y-3 rounded-md border border-glass bg-surface p-5">
      {error ? (
        <p
          role="alert"
          className="rounded-control border border-danger bg-surface-2 px-3 py-2 text-sm text-danger"
        >
          {error}
        </p>
      ) : null}
      <div className="space-y-2">
        <p className="text-sm text-fg-muted">
          {t("settingsInboxes.igConnectBlurb")}
        </p>
        <div className="flex flex-wrap gap-3">
          <Button
            type="button"
            loading={starting === "facebook"}
            disabled={starting !== null}
            onClick={() => void connect("facebook")}
          >
            <Facebook mono className="h-4 w-4" aria-hidden />
            Facebook Login
          </Button>
          <Button
            type="button"
            variant="ghost"
            className="btn-instagram-brand text-white hover:bg-transparent hover:text-white"
            loading={starting === "instagram"}
            disabled={starting !== null}
            onClick={() => void connect("instagram")}
          >
            <Instagram mono className="h-4 w-4" aria-hidden />
            Instagram Login
          </Button>
        </div>
      </div>
      {showManualHint ? (
        <p className="border-t border-glass pt-3 text-xs text-fg-muted">
          {t("settingsInboxes.fbManual")}
        </p>
      ) : null}
    </div>
  );
}

function Field({
  label,
  required,
  help,
  children,
}: {
  label: string;
  required?: boolean;
  help?: string;
  children: ReactNode;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-fg">
        {label}
        {required ? <span className="text-danger"> *</span> : null}
      </span>
      {children}
      {help ? <span className="block text-xs text-fg-muted">{help}</span> : null}
    </label>
  );
}

/** Assemble the `channel` sub-hash from flat field values, nesting dotted
 *  paths (`provider_config.api_key`) and injecting the channel's `fixed`
 *  constants. */
function buildChannel(
  def: ChannelDef,
  values: Record<string, string>,
): ChannelPayload {
  const channel: Record<string, unknown> = {
    type: def.type,
    ...(def.fixed ?? {}),
  };
  for (const f of def.fields) {
    let val: string | undefined = values[f.name];
    if (val === undefined && f.type === "checkbox" && f.default) {
      val = "true";
    }
    if ((val === undefined || val === "") && f.type === "select") {
      val = f.options?.[0]?.value;
    }
    if (val === undefined || val === "") continue;
    // A checkbox has to arrive as a real boolean. Sent as a string, every
    // non-empty value is truthy on the server — so "false" would switch
    // the side on, which is the opposite of what the box says.
    const value: string | boolean = f.type === "checkbox" ? val === "true" : val;
    const parts = f.name.split(".");
    let cur = channel;
    for (let i = 0; i < parts.length - 1; i++) {
      const key = parts[i];
      if (typeof cur[key] !== "object" || cur[key] === null) cur[key] = {};
      cur = cur[key] as Record<string, unknown>;
    }
    cur[parts[parts.length - 1]] = value;
  }
  return channel as ChannelPayload;
}
