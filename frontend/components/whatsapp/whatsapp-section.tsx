"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { PageHeader } from "@/components/shell/page-header";
import { NavTabs } from "@/components/ui/tabs";
import { useInbox, useInboxes } from "@/lib/api/inboxes";
import { useT } from "@/lib/i18n/provider";

import { BroadcastsPanel } from "./broadcasts-panel";
import { BusinessProfilePanel } from "./business-profile-panel";
import { CatalogPanel } from "./catalog-panel";
import { LinkQrPanel } from "./link-qr-panel";
import { NumberStatusPanel } from "./number-status-panel";
import { WhatsappTemplatesPanel } from "./templates-panel";

export const WHATSAPP_CHANNEL_TYPE = "Channel::Whatsapp";

const TAB_KEYS = [
  { key: "plantillas", labelKey: "whatsapp.section.tabs.templates" },
  { key: "envios", labelKey: "whatsapp.section.tabs.broadcasts" },
  { key: "catalogo", labelKey: "whatsapp.section.tabs.catalog" },
  { key: "numero", labelKey: "whatsapp.section.tabs.number" },
  { key: "perfil", labelKey: "whatsapp.section.tabs.profile" },
  { key: "link", labelKey: "whatsapp.section.tabs.linkQr" },
] as const;

type TabKey = (typeof TAB_KEYS)[number]["key"];

/** WhatsApp section: everything about the account's WhatsApp numbers, one
 *  at a time (``?inbox=``), split in tabs (``?tab=``). */
export function WhatsappSection({ accountId }: { accountId: string }) {
  const t = useT();
  const inboxesQ = useInboxes(accountId);
  const search = useSearchParams();
  const inboxes = (inboxesQ.data ?? []).filter(
    (inbox) => inbox.channel_type === WHATSAPP_CHANNEL_TYPE,
  );
  const wanted = Number(search?.get("inbox"));
  const current = inboxes.find((inbox) => inbox.id === wanted) ?? inboxes[0];
  const tabParam = search?.get("tab");
  const tab: TabKey = TAB_KEYS.some((item) => item.key === tabParam)
    ? (tabParam as TabKey)
    : "plantillas";
  const detailQ = useInbox(accountId, current?.id ?? Number.NaN);
  const base = `/accounts/${accountId}/whatsapp`;
  const href = (inboxId: number, tabKey: TabKey) =>
    `${base}?inbox=${inboxId}&tab=${tabKey}`;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        title={t("whatsapp.section.title")}
        description={t("whatsapp.section.description")}
      />

      {inboxesQ.isLoading ? (
        <p className="text-sm text-fg-muted">{t("whatsapp.section.loading")}</p>
      ) : !current ? (
        <p className="rounded-xl border border-glass bg-surface px-4 py-6 text-center text-sm text-fg-muted">
          {t("whatsapp.section.noInboxesPrefix")}{" "}
          <Link
            href={`/accounts/${accountId}/settings/inboxes`}
            className="text-lit underline-offset-2 hover:underline"
          >
            {t("whatsapp.section.settingsInboxesLink")}
          </Link>
          .
        </p>
      ) : (
        <>
          {inboxes.length > 1 ? (
            <div className="space-y-1.5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">
                {t("whatsapp.section.numberLabel")}
              </p>
              <NavTabs
                ariaLabel={t("whatsapp.section.numbersAria")}
                items={inboxes.map((inbox) => ({
                  href: href(inbox.id, tab),
                  label: inbox.name,
                  active: inbox.id === current.id,
                }))}
              />
            </div>
          ) : null}
          <NavTabs
            ariaLabel={t("whatsapp.section.sectionsAria")}
            items={TAB_KEYS.map((item) => ({
              href: href(current.id, item.key),
              label: t(item.labelKey),
              active: item.key === tab,
            }))}
          />
          <section
            key={`${current.id}-${tab}`}
            className="rounded-xl border border-glass bg-surface p-5 sm:p-6"
          >
            {tab === "plantillas" ? (
              <WhatsappTemplatesPanel
                accountId={accountId}
                inboxId={current.id}
                inboxName={current.name}
              />
            ) : tab === "envios" ? (
              <BroadcastsPanel
                accountId={accountId}
                inboxId={current.id}
                inboxName={current.name}
              />
            ) : tab === "catalogo" ? (
              <CatalogPanel accountId={accountId} inboxId={current.id} />
            ) : tab === "numero" ? (
              <NumberStatusPanel accountId={accountId} inboxId={current.id} />
            ) : tab === "perfil" ? (
              <BusinessProfilePanel
                accountId={accountId}
                inboxId={current.id}
                inboxName={current.name}
              />
            ) : (
              <LinkQrPanel
                accountId={accountId}
                inboxId={current.id}
                phoneNumber={detailQ.data?.phone_number ?? null}
              />
            )}
          </section>
        </>
      )}
    </div>
  );
}
