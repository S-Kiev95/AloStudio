"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useChangePassword } from "@/lib/api/profile";
import { useT } from "@/lib/i18n/provider";

export function SecurityView() {
  const t = useT();
  const change = useChangePassword();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit() {
    setError(null);
    setDone(false);
    if (!current || !next || !confirm) {
      return setError(t("settingsSecurity.fillAll"));
    }
    if (next.length < 8) {
      return setError(t("settingsSecurity.min8"));
    }
    if (next !== confirm) {
      return setError(t("settingsSecurity.mismatch"));
    }
    try {
      await change.mutateAsync({
        current_password: current,
        password: next,
        password_confirmation: confirm,
      });
      setDone(true);
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? t("settingsSecurity.changeFailed"),
      );
    }
  }

  return (
    <div className="max-w-2xl space-y-4">
      <h2 className="text-xl font-medium text-fg">{t("settings.items.security")}</h2>

      <Card>
        <CardHeader>
          <CardTitle>{t("settingsSecurity.changePassword")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {error ? (
              <p role="alert" className="text-sm text-danger">
                {error}
              </p>
            ) : null}
            {done ? (
              <p className="text-sm text-success">
                {t("settingsSecurity.updated")}
              </p>
            ) : null}

            <div className="space-y-1.5">
              <Label htmlFor="s-current" required>
                {t("settingsSecurity.current")}
              </Label>
              <Input
                id="s-current"
                type="password"
                autoComplete="current-password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="s-next" required>
                {t("settingsSecurity.new")}
              </Label>
              <Input
                id="s-next"
                type="password"
                autoComplete="new-password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
              />
              <p className="text-xs text-fg-muted">
                {t("settingsSecurity.min8Short")}
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="s-confirm" required>
                {t("settingsSecurity.repeat")}
              </Label>
              <Input
                id="s-confirm"
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </div>

            <div>
              <Button onClick={submit} loading={change.isPending}>
                {t("settingsSecurity.update")}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
