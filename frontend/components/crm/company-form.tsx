"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Company, CompanyInput } from "@/lib/api/crm";
import { useT } from "@/lib/i18n/provider";

/** The fields of a company, for creating or editing it. */
export function CompanyForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  initial?: Company | null;
  submitting: boolean;
  onSubmit: (data: CompanyInput) => Promise<void>;
  onCancel?: () => void;
}) {
  const t = useT();
  const [name, setName] = useState(initial?.name ?? "");
  const [website, setWebsite] = useState(initial?.website ?? "");
  const [email, setEmail] = useState(initial?.email ?? "");
  const [phone, setPhone] = useState(initial?.phone ?? "");
  const [taxId, setTaxId] = useState(initial?.tax_id ?? "");
  const [address, setAddress] = useState(initial?.address ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError(t("companies.nameRequired"));
      return;
    }
    try {
      await onSubmit({
        name: name.trim(),
        website: website.trim() || null,
        email: email.trim() || null,
        phone: phone.trim() || null,
        tax_id: taxId.trim() || null,
        address: address.trim() || null,
        notes: notes.trim() || null,
      });
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("companies.saveFailed"));
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      <div className="space-y-1.5">
        <Label htmlFor="company-name" required>
          {t("profile.name")}
        </Label>
        <Input id="company-name" value={name} maxLength={255} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="company-website">{t("companies.website")}</Label>
          <Input id="company-website" value={website} onChange={(e) => setWebsite(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="company-tax">{t("companies.taxId")}</Label>
          <Input id="company-tax" value={taxId} maxLength={64} onChange={(e) => setTaxId(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="company-email">{t("common.email")}</Label>
          <Input id="company-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="company-phone">{t("profile.phone")}</Label>
          <Input id="company-phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="company-address">{t("companies.address")}</Label>
        <Input id="company-address" value={address} onChange={(e) => setAddress(e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="company-notes">{t("opportunities.notes")}</Label>
        <Textarea id="company-notes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>
      <div className="flex justify-end gap-2">
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
            {t("actions.cancel")}
          </Button>
        ) : null}
        <Button type="submit" loading={submitting}>
          {initial ? t("common.saveChanges") : t("companies.create")}
        </Button>
      </div>
    </form>
  );
}
