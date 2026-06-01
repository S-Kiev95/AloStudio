"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useChangePassword } from "@/lib/api/profile";

export function SecurityView() {
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
      return setError("Completá los tres campos.");
    }
    if (next.length < 8) {
      return setError("La contraseña nueva tiene que tener al menos 8 caracteres.");
    }
    if (next !== confirm) {
      return setError("La confirmación no coincide con la contraseña nueva.");
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
        (e as { message?: string })?.message ?? "No se pudo cambiar la contraseña.",
      );
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-4 md:p-6">
      <h2 className="text-xl font-semibold text-fg">Seguridad</h2>

      <Card>
        <CardHeader>
          <CardTitle>Cambiar contraseña</CardTitle>
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
                Tu contraseña fue actualizada.
              </p>
            ) : null}

            <div className="space-y-1.5">
              <Label htmlFor="s-current" required>
                Contraseña actual
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
                Contraseña nueva
              </Label>
              <Input
                id="s-next"
                type="password"
                autoComplete="new-password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
              />
              <p className="text-xs text-fg-muted">
                Mínimo 8 caracteres.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="s-confirm" required>
                Repetir contraseña nueva
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
                Actualizar contraseña
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
