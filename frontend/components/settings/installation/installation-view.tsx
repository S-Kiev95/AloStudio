"use client";

import { Check, ChevronDown, Minus } from "lucide-react";
import { useState } from "react";

import { NetworkIcon, networkLabel } from "@/components/publications/network-icon";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { ApiError } from "@/lib/api/errors";
import {
  type InstallationConfig,
  groupConfigs,
  useClearInstallationConfig,
  useInstallationConfigs,
  useSetInstallationConfig,
} from "@/lib/api/installation";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";

export function InstallationView() {
  const t = useT();
  const configs = useInstallationConfigs();

  if (configs.isLoading) {
    return <p className="text-sm text-fg-muted">{t("common.loading")}</p>;
  }
  if (configs.isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        {configs.error instanceof ApiError && configs.error.status === 401
          ? t("settingsInstall.operatorOnly")
          : t("settingsInstall.loadFailed")}
      </p>
    );
  }

  const groups = groupConfigs(configs.data ?? []);

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-xl font-medium text-fg">
          {t("settings.items.installation")}
        </h2>
        <p className="text-sm text-fg-muted">
          {t("settingsInstall.intro")}
        </p>
      </div>

      {groups.map((group) => (
        <ConfigGroup key={group.group} group={group.group} items={group.items} />
      ))}
    </div>
  );
}

/** One section, folded away with a click once it's filled in. */
function ConfigGroup({
  group,
  items,
}: {
  group: string;
  items: InstallationConfig[];
}) {
  const t = useT();
  const [open, setOpen] = useState(true);
  const done = items.filter((c) => c.configured).length;
  const contentId = `config-group-${group.replace(/\W+/g, "-")}`;

  return (
    <Card>
      <CardHeader className={open ? undefined : "pb-5"}>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center justify-between gap-3 rounded-control text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon"
        >
          <CardTitle>{group}</CardTitle>
          <span className="flex shrink-0 items-center gap-2 text-xs text-fg-muted">
            {t("settingsInstall.configuredCount", { done, total: items.length })}
            <ChevronDown
              className={cn("h-4 w-4 transition-transform", open && "rotate-180")}
              aria-hidden
            />
          </span>
        </button>
      </CardHeader>
      {open ? (
        <CardContent id={contentId} className="space-y-6">
          {items
            .filter((config) => !config.network)
            .map((config) => (
              <ConfigRow key={config.name} config={config} />
            ))}
          <NetworkConfigs items={items.filter((c) => c.network)} />
        </CardContent>
      ) : null}
    </Card>
  );
}

/** The settings of one network at a time, picked from a list: each network
 *  brings several, and all of them at once is a wall of inputs. */
function NetworkConfigs({ items }: { items: InstallationConfig[] }) {
  const t = useT();
  const networks = [...new Set(items.map((c) => c.network as string))];
  const [picked, setPicked] = useState<string | null>(null);
  if (networks.length === 0) return null;
  const network = picked && networks.includes(picked) ? picked : networks[0];
  const ready = (net: string) =>
    items.filter((c) => c.network === net).every((c) => c.configured);

  return (
    <div className="space-y-6 border-t border-glass pt-6">
      <div className="space-y-1.5">
        <Label htmlFor="config-network">{t("settingsInstall.network")}</Label>
        <div className="flex items-center gap-2">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-control border border-glass bg-field">
            <NetworkIcon network={network} />
          </span>
          <Select
            id="config-network"
            value={network}
            onChange={(e) => setPicked(e.target.value)}
          >
            {networks.map((net) => (
              <option key={net} value={net}>
                {networkLabel(net)}
                {" · "}
                {ready(net)
                  ? t("settingsInstall.netConfigured")
                  : t("settingsInstall.netNotConfigured")}
              </option>
            ))}
          </Select>
        </div>
      </div>
      {items
        .filter((c) => c.network === network)
        .map((config) => (
          <ConfigRow key={config.name} config={config} />
        ))}
    </div>
  );
}

function ConfigRow({ config }: { config: InstallationConfig }) {
  const t = useT();
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
      setError((e as { message?: string })?.message ?? t("settingsInboxes.saveFailed"));
    }
  }

  async function reset() {
    setError(null);
    try {
      await clear.mutateAsync(config.name);
      setDraft("");
    } catch (e) {
      setError((e as { message?: string })?.message ?? t("settingsInstall.clearFailed"));
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
            className="mt-1 h-4 w-4 shrink-0 rounded border-glass accent-neon"
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
              : t("settingsInstall.notConfigured")
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
          {t("actions.save")}
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
  const t = useT();
  return (
    <p className="flex flex-wrap items-center gap-2 pt-1 text-xs text-fg-muted">
      {config.configured ? (
        <span className="inline-flex items-center gap-1 text-success">
          <Check className="h-3 w-3" aria-hidden />
          {t("settingsInstall.configured")}
        </span>
      ) : (
        <span className="inline-flex items-center gap-1">
          <Minus className="h-3 w-3" aria-hidden />
          {t("settingsInstall.notConfigured")}
        </span>
      )}
      <span aria-hidden>·</span>
      {config.source === "database" ? (
        <>
          <span>{t("settingsInstall.savedHere")}</span>
          <button
            type="button"
            onClick={onReset}
            disabled={pending}
            className="text-lit hover:underline disabled:opacity-50"
          >
            {t("settingsInstall.resetToServer")}
          </button>
        </>
      ) : (
        <span>{t("settingsInstall.fromEnv")}</span>
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
