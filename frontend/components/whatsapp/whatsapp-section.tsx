"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { PageHeader } from "@/components/shell/page-header";
import { NavTabs } from "@/components/ui/tabs";
import { useInboxes } from "@/lib/api/inboxes";

import { WhatsappTemplatesPanel } from "./templates-panel";

export const WHATSAPP_CHANNEL_TYPE = "Channel::Whatsapp";

/** WhatsApp section: everything about the account's WhatsApp inboxes, one
 *  inbox at a time (``?inbox=`` picks it when there are several). For now,
 *  its message templates. */
export function WhatsappSection({ accountId }: { accountId: string }) {
  const inboxesQ = useInboxes(accountId);
  const search = useSearchParams();
  const inboxes = (inboxesQ.data ?? []).filter(
    (inbox) => inbox.channel_type === WHATSAPP_CHANNEL_TYPE,
  );
  const wanted = Number(search?.get("inbox"));
  const current = inboxes.find((inbox) => inbox.id === wanted) ?? inboxes[0];
  const base = `/accounts/${accountId}/whatsapp`;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        title="WhatsApp"
        description="Plantillas de mensajes de cada número de WhatsApp: las que Meta aprobó se pueden mandar aunque hayan pasado 24 h del último mensaje del contacto."
      />

      {inboxesQ.isLoading ? (
        <p className="text-sm text-fg-muted">Cargando…</p>
      ) : !current ? (
        <p className="rounded-xl border border-glass bg-surface px-4 py-6 text-center text-sm text-fg-muted">
          Esta cuenta no tiene bandejas de WhatsApp. Conectá una en{" "}
          <Link
            href={`/accounts/${accountId}/settings/inboxes`}
            className="text-lit underline-offset-2 hover:underline"
          >
            Ajustes → Bandejas
          </Link>
          .
        </p>
      ) : (
        <>
          {inboxes.length > 1 ? (
            <NavTabs
              ariaLabel="Números de WhatsApp"
              items={inboxes.map((inbox) => ({
                href: `${base}?inbox=${inbox.id}`,
                label: inbox.name,
                active: inbox.id === current.id,
              }))}
            />
          ) : null}
          <section className="rounded-xl border border-glass bg-surface p-5 sm:p-6">
            <h2 className="mb-4 text-base font-semibold text-fg">
              Plantillas de {current.name}
            </h2>
            <WhatsappTemplatesPanel
              key={current.id}
              accountId={accountId}
              inboxId={current.id}
              inboxName={current.name}
            />
          </section>
        </>
      )}
    </div>
  );
}
