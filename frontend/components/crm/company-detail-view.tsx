"use client";

import { ArrowLeft, Trash2, UserMinus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type CompanyInput,
  useCompany,
  useDeleteCompany,
  useOpportunities,
  usePipelines,
  useSaveCompany,
  useSetContactCompany,
} from "@/lib/api/crm";
import { useIsAccountAdmin } from "@/lib/api/profile";
import { useIntlTag, useT } from "@/lib/i18n/provider";

import { CompanyForm } from "./company-form";
import { ContactPicker } from "./contact-picker";
import { formatMoney } from "./money";
import { stageLabel } from "./stage-label";

/** One company: its details, its people, and their opportunities. */
export function CompanyDetailView({
  accountId,
  companyId,
}: {
  accountId: string;
  companyId: number;
}) {
  const t = useT();
  const intlTag = useIntlTag();
  const router = useRouter();
  const isAdmin = useIsAccountAdmin(accountId);
  const { data: company, isLoading, isError } = useCompany(accountId, companyId);
  const opportunities = useOpportunities(accountId, { company_id: companyId });
  const pipelines = usePipelines(accountId);
  const save = useSaveCompany(accountId);
  const remove = useDeleteCompany(accountId);
  const membership = useSetContactCompany(accountId);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stages = new Map(
    (pipelines.data ?? []).flatMap((p) => p.stages.map((s) => [s.id, s] as const)),
  );

  async function handleSave(input: CompanyInput) {
    setSaved(false);
    await save.mutateAsync({ id: companyId, data: input });
    setSaved(true);
  }

  async function handleDelete() {
    if (!company) return;
    if (!window.confirm(t("companies.deleteConfirm", { name: company.name }))) return;
    try {
      await remove.mutateAsync(companyId);
      router.push(`/accounts/${accountId}/companies`);
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("actions.deleteFailed"));
    }
  }

  async function changeMember(contactId: number, join: boolean) {
    setError(null);
    try {
      await membership.mutateAsync({
        contactId,
        companyId: join ? companyId : null,
        fromId: join ? null : companyId,
      });
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("companies.saveFailed"));
    }
  }

  if (isLoading) return <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>;
  if (isError || !company) {
    return (
      <p role="alert" className="p-8 text-center text-sm text-danger">
        {t("companies.loadFailed")}
      </p>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link
        href={`/accounts/${accountId}/companies`}
        className="inline-flex items-center gap-1.5 text-sm text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        {t("companies.back")}
      </Link>
      <PageHeader
        title={company.name}
        signTitle={t("companies.pageTitle")}
        actions={
          isAdmin ? (
            <Button size="sm" variant="ghost" onClick={handleDelete} disabled={remove.isPending}>
              <Trash2 className="h-4 w-4" aria-hidden />
              {t("actions.delete")}
            </Button>
          ) : undefined
        }
      />
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("companies.people")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {company.contacts.length === 0 ? (
            <p className="text-sm text-fg-muted">{t("companies.noPeople")}</p>
          ) : (
            <ul className="divide-y divide-glass">
              {company.contacts.map((c) => (
                <li key={c.id} className="flex items-center gap-3 py-2">
                  <Avatar name={c.name ?? "?"} src={c.avatar_url} size="sm" />
                  <Link
                    href={`/accounts/${accountId}/contacts/${c.id}`}
                    className="min-w-0 flex-1 hover:underline"
                  >
                    <span className="block truncate text-sm font-medium text-fg">
                      {c.name || t("conversations.contact.fallbackName", { id: c.id })}
                    </span>
                    {c.email || c.phone_number ? (
                      <span className="block truncate text-xs text-fg-muted">
                        {[c.email, c.phone_number].filter(Boolean).join(" · ")}
                      </span>
                    ) : null}
                  </Link>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={t("companies.removePerson", { name: c.name ?? String(c.id) })}
                    onClick={() => void changeMember(c.id, false)}
                    disabled={membership.isPending}
                  >
                    <UserMinus className="h-4 w-4" aria-hidden />
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <ContactPicker
            accountId={accountId}
            inputId="company-add-person"
            pickLabel={t("companies.addPerson")}
            value={null}
            onChange={(c) => {
              if (c) void changeMember(c.id, true);
            }}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("opportunities.pageTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          {(opportunities.data?.length ?? 0) === 0 ? (
            <p className="text-sm text-fg-muted">{t("companies.noOpportunities")}</p>
          ) : (
            <ul className="divide-y divide-glass">
              {opportunities.data?.map((o) => {
                const stage = stages.get(o.stage_id);
                return (
                  <li key={o.id} className="flex items-center justify-between gap-3 py-2">
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-fg">{o.title}</span>
                      <span className="block truncate text-xs text-fg-muted">
                        {[o.contact?.name, stage ? stageLabel(t, stage) : null]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </span>
                    <span className="shrink-0 font-numeric text-sm tabular-nums text-fg">
                      {o.value != null ? formatMoney(o.value, o.currency, intlTag) : ""}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("companies.details")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {saved ? (
            <p role="status" className="text-sm text-success">
              {t("common.changesSaved")}
            </p>
          ) : null}
          <CompanyForm
            key={company.id}
            initial={company}
            submitting={save.isPending}
            onSubmit={handleSave}
          />
        </CardContent>
      </Card>
    </div>
  );
}
