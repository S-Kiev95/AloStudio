"use client";

import { Check, Minus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/errors";
import {
  type InstallationConfig,
  groupConfigs,
  useClearInstallationConfig,
  useInstallationConfigs,
  useSetInstallationConfig,
} from "@/lib/api/installation";

export function InstallationView() {
  const configs = useInstallationConfigs();

  if (configs.isLoading) {
    return <p className="text-sm text-fg-muted">Cargando…</p>;
  }
  if (configs.isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        {configs.error instanceof ApiError && configs.error.status === 401
          ? "Sólo el operador de la instalación puede ver esta pantalla. Pedile acceso a quien la desplegó."
          : "No se pudo cargar la configuración."}
      </p>
    );
  }

  const groups = groupConfigs(configs.data ?? []);

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold">Configuración de la instalación</h1>
        <p className="text-sm text-fg-muted">
          Ajustes que valen para todo AloStudio, no para una cuenta. Podés
          dejarlos vacíos y completarlos cuando tengas las credenciales — la
          app funciona sin ellos, y cada función te avisa qué le falta.
        </p>
      </div>

      {groups.map((group) => (
        <Card key={group.group}>
          <CardHeader>
            <CardTitle>{group.group}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {group.items.map((config) => (
              <ConfigRow key={config.name} config={config} />
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ConfigRow({ config }: { config: InstallationConfig }) {
  const set = useSetInstallationConfig();
  const clear = useClearInstallationConfig();
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const inputId = `config-${config.name}`;

  async function save(value: string | boolean) {
    setError(null);
    try {
      await set.mutateAsync({ name: config.name, value });
      setDraft("");
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo guardar.");
    }
  }

  async function reset() {
    setError(null);
    try {
      await clear.mutateAsync(config.name);
      setDraft("");
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo borrar.");
    }
  }

  if (config.kind === "boolean") {
    const on = config.value === true;
    return (
      <div className="space-y-1">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <Label htmlFor={inputId}>{config.title}</Label>
            <p className="text-xs text-fg-muted">{config.description}</p>
          </div>
          <input
            id={inputId}
            type="checkbox"
            checked={on}
            disabled={!config.editable || set.isPending}
            onChange={(e) => save(e.target.checked)}
            className="mt-1 h-4 w-4 shrink-0"
          />
        </div>
        <SourceNote config={config} onReset={reset} pending={clear.isPending} />
        <RowError error={error} />
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <Label htmlFor={inputId}>{config.title}</Label>
      <p className="text-xs text-fg-muted">{config.description}</p>
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <Input
          id={inputId}
          type={config.secret ? "password" : "text"}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          // A secret is only ever shown masked, so the box starts empty and
          // the current state lives in the placeholder.
          placeholder={
            config.configured
              ? String(config.value)
              : "Sin configurar"
          }
          className="min-w-0 flex-1"
          autoComplete="off"
        />
        <Button
          size="sm"
          onClick={() => save(draft)}
          disabled={!config.editable || draft.trim() === ""}
          loading={set.isPending}
        >
          Guardar
        </Button>
      </div>
      <SourceNote config={config} onReset={reset} pending={clear.isPending} />
      <RowError error={error} />
    </div>
  );
}

function SourceNote({
  config,
  onReset,
  pending,
}: {
  config: InstallationConfig;
  onReset: () => void;
  pending: boolean;
}) {
  return (
    <p className="flex flex-wrap items-center gap-2 pt-1 text-xs text-fg-muted">
      {config.configured ? (
        <span className="inline-flex items-center gap-1 text-success">
          <Check className="h-3 w-3" aria-hidden />
          Configurado
        </span>
      ) : (
        <span className="inline-flex items-center gap-1">
          <Minus className="h-3 w-3" aria-hidden />
          Sin configurar
        </span>
      )}
      <span aria-hidden>·</span>
      {config.source === "database" ? (
        <>
          <span>guardado desde acá</span>
          <button
            type="button"
            onClick={onReset}
            disabled={pending}
            className="text-info hover:underline disabled:opacity-50"
          >
            volver al valor del servidor
          </button>
        </>
      ) : (
        <span>viene del archivo del servidor (.env)</span>
      )}
    </p>
  );
}

function RowError({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <p role="alert" className="text-xs text-danger">
      {error}
    </p>
  );
}
