"use client";

import { CheckCircle2, CircleAlert, Link2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useIsAccountAdmin } from "@/lib/api/profile";
import {
  useLinkWhatsappCatalog,
  useUpdateWhatsappCommerce,
  useWhatsappCommerce,
} from "@/lib/api/whatsapp-catalog";
import { useT } from "@/lib/i18n/provider";

function Step({
  done,
  title,
  children,
}: {
  done: boolean;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <li className="flex gap-3 rounded-xl border border-glass bg-surface p-4">
      {done ? (
        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" aria-hidden />
      ) : (
        <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-warning" aria-hidden />
      )}
      <div className="min-w-0 flex-1 space-y-2">
        <p className="text-sm font-semibold text-fg">{title}</p>
        {children}
      </div>
    </li>
  );
}

function Toggle({
  label,
  hint,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  disabled: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-2.5 text-sm text-fg">
      <input
        type="checkbox"
        className="mt-1"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>
        {label}
        <span className="block text-xs text-fg-muted">{hint}</span>
      </span>
    </label>
  );
}

/** The catalogue on this number: is the account's Meta catalogue linked to
 *  the WhatsApp account, is it shown on the profile, is the cart on. */
export function CatalogPanel({ accountId, inboxId }: { accountId: string; inboxId: number }) {
  const t = useT();
  const isAdmin = useIsAccountAdmin(accountId);
  const q = useWhatsappCommerce(accountId, inboxId);
  const update = useUpdateWhatsappCommerce(accountId, inboxId);
  const link = useLinkWhatsappCatalog(accountId, inboxId);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
    } catch (err) {
      setError((err as Error).message || t("whatsapp.common.metaRejected"));
    }
  }

  if (q.isLoading) {
    return <p className="text-sm text-fg-muted">{t("whatsapp.common.queryingMeta")}</p>;
  }
  if (q.isError || !q.data) {
    return (
      <p role="alert" className="text-sm text-danger">
        {(q.error as Error | null)?.message ?? t("whatsapp.catalog.loadError")}
      </p>
    );
  }
  const s = q.data;
  const busy = update.isPending || link.isPending;

  return (
    <div className="space-y-4">
      <p className="text-sm text-fg-muted">{t("whatsapp.catalog.intro")}</p>
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      <ol className="space-y-3">
        <Step done={Boolean(s.account_catalog_id)} title={t("whatsapp.catalog.step1Title")}>
          {s.account_catalog_id ? (
            <p className="text-sm text-fg-muted">
              {t("whatsapp.catalog.step1CatalogLabel")}{" "}
              <span className="font-mono">{s.account_catalog_id}</span>
              {s.products_ready === 1
                ? t("whatsapp.catalog.step1ReadyOne", { count: s.products_ready })
                : t("whatsapp.catalog.step1ReadyMany", { count: s.products_ready })}{" "}
              <Link
                href={`/accounts/${accountId}/products`}
                className="text-lit underline-offset-2 hover:underline"
              >
                {t("whatsapp.catalog.viewProducts")}
              </Link>
            </p>
          ) : (
            <p className="text-sm text-fg-muted">
              {t("whatsapp.catalog.step1ConnectPrefix")}{" "}
              <Link
                href={`/accounts/${accountId}/products`}
                className="text-lit underline-offset-2 hover:underline"
              >
                {t("whatsapp.catalog.crmProductsLink")}
              </Link>{" "}
              {t("whatsapp.catalog.step1ConnectSuffix")}
            </p>
          )}
        </Step>
        <Step done={s.catalog_linked} title={t("whatsapp.catalog.step2Title")}>
          {s.catalog_linked ? (
            <p className="text-sm text-fg-muted">{t("whatsapp.catalog.step2Done")}</p>
          ) : (
            <>
              <p className="text-sm text-fg-muted">{t("whatsapp.catalog.step2Desc")}</p>
              {isAdmin && s.account_catalog_id ? (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  loading={link.isPending}
                  onClick={() => void run(() => link.mutateAsync())}
                >
                  <Link2 className="h-3.5 w-3.5" aria-hidden />
                  {t("whatsapp.catalog.connectCatalog")}
                </Button>
              ) : null}
            </>
          )}
        </Step>
        <Step
          done={s.is_catalog_visible && s.is_cart_enabled}
          title={t("whatsapp.catalog.step3Title")}
        >
          <Toggle
            label={t("whatsapp.catalog.showInProfileLabel")}
            hint={t("whatsapp.catalog.showInProfileHint")}
            checked={s.is_catalog_visible}
            disabled={!isAdmin || busy}
            onChange={(next) =>
              void run(() => update.mutateAsync({ is_catalog_visible: next }))
            }
          />
          <Toggle
            label={t("whatsapp.catalog.cartLabel")}
            hint={t("whatsapp.catalog.cartHint")}
            checked={s.is_cart_enabled}
            disabled={!isAdmin || busy}
            onChange={(next) => void run(() => update.mutateAsync({ is_cart_enabled: next }))}
          />
        </Step>
      </ol>
    </div>
  );
}
