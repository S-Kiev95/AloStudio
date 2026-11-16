"use client";

import { Building2, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useCompanies, useSaveCompany, useSetContactCompany } from "@/lib/api/crm";
import { useT } from "@/lib/i18n/provider";

/** The company a contact works at, on their page: shown, changed or created
 *  on the spot. */
export function ContactCompanyCard({
  accountId,
  contactId,
}: {
  accountId: string;
  contactId: number;
}) {
  const t = useT();
  const current = useCompanies(accountId, { contact_id: contactId });
  const [picking, setPicking] = useState(false);
  const [query, setQuery] = useState("");
  const candidates = useCompanies(accountId, { q: query });
  const membership = useSetContactCompany(accountId);
  const create = useSaveCompany(accountId);
  const [error, setError] = useState<string | null>(null);
  const company = current.data?.[0] ?? null;

  async function join(companyId: number) {
    setError(null);
    try {
      await membership.mutateAsync({ contactId, companyId });
      setPicking(false);
      setQuery("");
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("companies.saveFailed"));
    }
  }

  async function createAndJoin() {
    if (!query.trim()) return;
    try {
      const created = await create.mutateAsync({ data: { name: query.trim() } });
      await join(created.id);
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("companies.saveFailed"));
    }
  }

  const exact = (candidates.data ?? []).some(
    (c) => c.name.toLowerCase() === query.trim().toLowerCase(),
  );

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Building2 className="h-4 w-4 text-fg-muted" aria-hidden />
          {t("companies.company")}
        </CardTitle>
        {company && !picking ? (
          <span className="flex gap-1">
            <Button size="sm" variant="ghost" onClick={() => setPicking(true)}>
              {t("agenda.dialog.change")}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={membership.isPending}
              onClick={() =>
                void membership.mutateAsync({ contactId, companyId: null, fromId: company.id })
              }
            >
              {t("common.remove")}
            </Button>
          </span>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-2">
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}
        {company && !picking ? (
          <Link
            href={`/accounts/${accountId}/companies/${company.id}`}
            className="text-sm font-medium text-lit hover:underline"
          >
            {company.name}
          </Link>
        ) : !picking ? (
          <Button size="sm" variant="secondary" onClick={() => setPicking(true)}>
            {t("companies.assign")}
          </Button>
        ) : (
          <div className="space-y-2">
            <div className="relative">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted"
                aria-hidden
              />
              <Input
                aria-label={t("companies.search")}
                placeholder={t("companies.search")}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <ul className="max-h-40 divide-y divide-glass overflow-y-auto rounded-md border border-glass bg-surface">
              {(candidates.data ?? []).slice(0, 20).map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => void join(c.id)}
                    className="w-full px-3 py-2 text-left text-sm text-fg hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                  >
                    {c.name}
                  </button>
                </li>
              ))}
              {query.trim() && !exact ? (
                <li>
                  <button
                    type="button"
                    onClick={() => void createAndJoin()}
                    className="w-full px-3 py-2 text-left text-sm text-lit hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                  >
                    {t("companies.createNamed", { name: query.trim() })}
                  </button>
                </li>
              ) : null}
            </ul>
            <Button size="sm" variant="ghost" onClick={() => setPicking(false)}>
              {t("actions.cancel")}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
