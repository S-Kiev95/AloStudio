"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { type InboxDetail, useUpdateInbox } from "@/lib/api/inboxes";
import { useT } from "@/lib/i18n/provider";

/** What every reply from this mailbox signs with.
 *
 *  Per mailbox rather than per account: the identity of an outgoing email
 *  already lives here — the address it comes from, the server it goes
 *  through — and support@ and sales@ commonly sign differently.
 *
 *  The preview is the point of the screen. A signature is written once and
 *  then goes out on every reply, so seeing it rendered before saving is
 *  what stops a broken logo or a stray line reaching customers. */
export function EmailBrandingPanel({
  accountId,
  inbox,
}: {
  accountId: string;
  inbox: InboxDetail;
}) {
  const t = useT();
  const update = useUpdateInbox(accountId);
  const [signature, setSignature] = useState(inbox.signature ?? "");
  const [logoUrl, setLogoUrl] = useState(inbox.logo_url ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const dirty =
    signature !== (inbox.signature ?? "") || logoUrl !== (inbox.logo_url ?? "");

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    try {
      await update.mutateAsync({
        id: inbox.id,
        patch: { channel: { signature, logo_url: logoUrl.trim() } },
      });
      setSaved(true);
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("settingsInboxes.saveFailed"));
    }
  }

  return (
    <form onSubmit={save} className="space-y-4">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="space-y-1.5">
        <Label htmlFor="signature">{t("settingsInboxes.signature")}</Label>
        <Textarea
          id="signature"
          rows={4}
          maxLength={2000}
          value={signature}
          onChange={(e) => {
            setSignature(e.target.value);
            setSaved(false);
          }}
          placeholder={[t("settingsInboxes.exampleOrg"), t("settingsInboxes.exampleHours"), "(598) 4732 0000"].join("\n")}
        />
        <p className="text-xs text-fg-muted">
          {t("settingsInboxes.signatureHint")}
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="logo">{t("settingsInboxes.logo")}</Label>
        <Input
          id="logo"
          type="url"
          value={logoUrl}
          onChange={(e) => {
            setLogoUrl(e.target.value);
            setSaved(false);
          }}
          placeholder="https://tusitio.com/logo.png"
        />
        <p className="text-xs text-fg-muted">
          {t("settingsInboxes.logoHint")}
        </p>
      </div>

      <SignaturePreview signature={signature} logoUrl={logoUrl} />

      <div className="flex items-center gap-3">
        <Button type="submit" size="sm" loading={update.isPending} disabled={!dirty}>
          {t("actions.save")}
        </Button>
        {saved && !dirty ? (
          <span role="status" className="text-sm text-success">
            {t("settingsInboxes.saved")}
          </span>
        ) : null}
      </div>
    </form>
  );
}

/** Rendered on the light background a mail client uses, not the app's dark
 *  one — otherwise a logo that vanishes on white looks fine here. */
function SignaturePreview({
  signature,
  logoUrl,
}: {
  signature: string;
  logoUrl: string;
}) {
  const t = useT();
  const has = signature.trim().length > 0 || logoUrl.trim().length > 0;
  return (
    <div className="space-y-1.5">
      <Label>{t("settingsInboxes.preview")}</Label>
      <div className="rounded-lg border border-border bg-[#f4f5f7] p-4">
        <div className="rounded-md bg-white p-4 text-[#1f2328]">
          <p className="text-sm">{t("settingsInboxes.previewBody")}</p>
          {has ? (
            <>
              <hr className="my-4 border-t border-[#e5e7eb]" />
              {logoUrl.trim() ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={logoUrl}
                  alt=""
                  className="mb-3 max-h-14 max-w-[160px] object-contain"
                />
              ) : null}
              {signature.trim() ? (
                <p className="whitespace-pre-wrap text-[13px] leading-snug text-[#5b6470]">
                  {signature}
                </p>
              ) : null}
            </>
          ) : (
            <p className="mt-4 text-xs text-[#8a919b]">
              {t("settingsInboxes.noSignatureNote")}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
