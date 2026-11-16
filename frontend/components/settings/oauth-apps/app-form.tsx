"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Textarea } from "@/components/ui/textarea";
import type { OAuthApp, OAuthAppInput } from "@/lib/api/oauth";
import { useT } from "@/lib/i18n/provider";

const KIND_OPTIONS = [
  { value: "confidential", label: "settingsOauth.confidential" },
  { value: "public", label: "settingsOauth.public" },
] as const;

const KIND_HINT = {
  confidential:
    "settingsOauth.kindHint.confidential",
  public:
    "settingsOauth.kindHint.public",
} as const;

/** Create (with the confidential/public choice) or edit an app. */
export function AppForm({
  initial,
  submitting,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: OAuthApp;
  submitting: boolean;
  error: string | null;
  onSubmit: (input: OAuthAppInput) => void;
  onCancel: () => void;
}) {
  const t = useT();
  const [name, setName] = useState(initial?.name ?? "");
  const [uris, setUris] = useState((initial?.redirect_uris ?? []).join("\n"));
  const [kind, setKind] = useState<"confidential" | "public">(
    initial && !initial.confidential ? "public" : "confidential",
  );

  function submit(event: React.FormEvent) {
    event.preventDefault();
    onSubmit({
      name,
      redirect_uris: uris
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      confidential: kind === "confidential",
    });
  }

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <div className="space-y-1.5">
        <Label htmlFor="oauth-app-name" required>
          {t("profile.name")}
        </Label>
        <Input
          id="oauth-app-name"
          value={name}
          maxLength={80}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("settingsOauth.namePlaceholder")}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="oauth-app-uris" required>
          {t("settingsOauth.redirectUrl")}
        </Label>
        <Textarea
          id="oauth-app-uris"
          rows={3}
          value={uris}
          onChange={(e) => setUris(e.target.value)}
          placeholder="https://tu-app.com/oauth/callback"
        />
        <p className="text-xs text-fg-muted">
          {t("settingsOauth.redirectHint")}
        </p>
      </div>
      {initial ? null : (
        <div className="space-y-1.5">
          <p className="text-sm font-medium text-fg">{t("settingsOauth.kind")}</p>
          <SegmentedControl
            value={kind}
            onValueChange={setKind}
            options={KIND_OPTIONS.map((o) => ({ ...o, label: t(o.label) }))}
            ariaLabel={t("settingsOauth.appKind")}
          />
          <p className="text-xs text-fg-muted">{t(KIND_HINT[kind])}</p>
        </div>
      )}
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          {t("actions.cancel")}
        </Button>
        <Button type="submit" size="sm" loading={submitting}>
          {initial ? t("actions.save") : t("settingsOauth.create")}
        </Button>
      </div>
    </form>
  );
}
