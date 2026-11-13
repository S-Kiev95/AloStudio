"use client";

import { Building2, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { type CompanyInput, useCompanies, useSaveCompany } from "@/lib/api/crm";
import { useT } from "@/lib/i18n/provider";

import { CompanyForm } from "./company-form";

/** CRM → Empresas: the organizations the account sells to. */
export function CompaniesView({ accountId }: { accountId: string }) {
  const t = useT();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const { data, isLoading, isError } = useCompanies(accountId, { q: query });
  const save = useSaveCompany(accountId);

  async function handleCreate(input: CompanyInput) {
    const company = await save.mutateAsync({ data: input });
    setCreating(false);
    router.push(`/accounts/${accountId}/companies/${company.id}`);
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={t("companies.pageTitle")}
        actions={
          creating ? undefined : (
            <Button size="sm" onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" aria-hidden />
              {t("companies.new")}
            </Button>
          )
        }
      />

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("companies.new")}</CardTitle>
          </CardHeader>
          <CardContent>
            <CompanyForm
              submitting={save.isPending}
              onSubmit={handleCreate}
              onCancel={() => setCreating(false)}
            />
          </CardContent>
        </Card>
      ) : null}

      <div className="relative w-72 max-w-full">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted"
          aria-hidden
        />
        <Input
          aria-label={t("companies.search")}
          placeholder={t("companies.search")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="h-9 pl-9"
        />
      </div>

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            {t("companies.loadFailed")}
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {query.trim() ? t("companies.noneFound") : t("companies.empty")}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {data?.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/accounts/${accountId}/companies/${c.id}`}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                >
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-control border border-glass bg-surface-2">
                    <Building2 className="h-4 w-4 text-fg-muted" aria-hidden />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-fg">{c.name}</span>
                    {c.website || c.phone ? (
                      <span className="block truncate text-xs text-fg-muted">
                        {[c.website, c.phone].filter(Boolean).join(" · ")}
                      </span>
                    ) : null}
                  </span>
                  <span className="shrink-0 font-numeric text-xs tabular-nums text-fg-muted">
                    {t(c.contacts_count === 1 ? "companies.peopleOne" : "companies.peopleMany", {
                      count: c.contacts_count,
                    })}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
