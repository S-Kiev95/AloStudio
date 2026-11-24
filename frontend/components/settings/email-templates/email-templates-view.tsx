"use client";

import {
  Building2,
  FileUp,
  Mail,
  PenTool,
  Plus,
  Sparkles,
  Star,
  Trash2,
  User,
} from "lucide-react";
import { type ChangeEvent, type FormEvent, useMemo, useRef, useState } from "react";

import { EmailDesigner } from "@/components/settings/inboxes/email-designer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useConfirm } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ROLE_ADMINISTRATOR } from "@/lib/api/account";
import {
  type EmailSignature,
  type EmailTemplate,
  type GeneratedEmailDesign,
  type TemplateScope,
  useCreateEmailTemplate,
  useDeleteEmailTemplate,
  useEmailSignature,
  useEmailTemplates,
  useUpdateEmailSignature,
  useUpdateEmailTemplate,
} from "@/lib/api/email-templates";
import { useProfile } from "@/lib/api/profile";
import { useT } from "@/lib/i18n/provider";
import { rich } from "@/lib/i18n/rich";
import {
  type BlockDocument,
  DEFAULT_DOCUMENT,
  createDefaultSignatureDocument,
  isBlockDocument,
  renderBlocks,
} from "@/lib/inboxes/email-blocks";
import {
  DEFAULT_DESIGN,
  type TemplateDesign,
  renderDesign,
} from "@/lib/inboxes/email-template-design";
import { cn } from "@/lib/utils";

import { AiDesignDialog } from "./ai-design-dialog";
import { BlockEditor } from "./block-editor";
import { EmailPreviewFrame, type SampleProfile } from "./email-preview-frame";
import { TestSendBox } from "./test-send-box";

const CONTENT = "{{contenido}}";

const TEMPLATE_TOKENS = [
  "{{contenido}}",
  "{{firma}}",
  "{{firma_organizacion}}",
  "{{logo}}",
] as const;

const SIGNATURE_TOKENS = [
  "{{nombre}}",
  "{{cargo}}",
  "{{correo}}",
  "{{telefono}}",
  "{{foto}}",
] as const;

type ViewTab = "organization" | "personal" | "signatures";

export function EmailTemplatesView({ accountId }: { accountId: string }) {
  const t = useT();
  const profile = useProfile();

  const targetAccountId = Number(accountId);
  const membership = profile.data?.accounts?.find(
    (a) => a.id === targetAccountId,
  );
  // If profile loaded and user is explicitly a non-admin agent, hide org admin tabs.
  // When profile hasn't loaded (or in isolated tests), keep org tab available.
  const canManageOrg =
    membership !== undefined ? membership.role === ROLE_ADMINISTRATOR : true;

  const [tab, setTab] = useState<ViewTab | null>(null);
  const activeTab: ViewTab =
    tab ?? (canManageOrg ? "organization" : "personal");

  const sampleProfile: SampleProfile = useMemo(() => {
    const p = profile.data;
    if (!p) return {};
    const phone =
      typeof p.custom_attributes?.phone_number === "string"
        ? p.custom_attributes.phone_number
        : undefined;
    return {
      name: p.available_name || p.name,
      jobTitle: p.job_title ?? undefined,
      email: p.email,
      phone,
      avatarUrl: p.avatar_url ?? undefined,
    };
  }, [profile.data]);

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-xl font-medium text-fg">
          {t("settings.items.email_templates")}
        </h2>
        <p className="text-sm text-fg-muted">{t("settingsEmailTpl.intro")}</p>
      </div>

      {/* Scope navigation tabs */}
      <div
        role="tablist"
        aria-label={t("settingsEmailTpl.tabsLabel")}
        className="flex flex-wrap gap-1 rounded-control border border-glass bg-field p-1"
      >
        {canManageOrg ? (
          <TabButton
            active={activeTab === "organization"}
            onClick={() => setTab("organization")}
          >
            <Building2 className="h-4 w-4" aria-hidden />
            {t("settingsEmailTpl.tabOrg")}
          </TabButton>
        ) : null}
        <TabButton
          active={activeTab === "personal"}
          onClick={() => setTab("personal")}
        >
          <User className="h-4 w-4" aria-hidden />
          {t("settingsEmailTpl.tabPersonal")}
        </TabButton>
        <TabButton
          active={activeTab === "signatures"}
          onClick={() => setTab("signatures")}
        >
          <PenTool className="h-4 w-4" aria-hidden />
          {t("settingsEmailTpl.tabSignatures")}
        </TabButton>
      </div>

      {activeTab === "organization" && canManageOrg ? (
        <TemplateListSection
          key="org"
          accountId={accountId}
          scope="organization"
          sampleProfile={sampleProfile}
        />
      ) : activeTab === "personal" ? (
        <TemplateListSection
          key="personal"
          accountId={accountId}
          scope="personal"
          sampleProfile={sampleProfile}
        />
      ) : (
        <SignaturesSection
          accountId={accountId}
          canManageOrg={canManageOrg}
          sampleProfile={sampleProfile}
        />
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "inline-flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
        active
          ? "bg-focused text-lit"
          : "text-fg-muted hover:bg-hover-glass hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

function TemplateListSection({
  accountId,
  scope,
  sampleProfile,
}: {
  accountId: string;
  scope: TemplateScope;
  sampleProfile: SampleProfile;
}) {
  const t = useT();
  const templates = useEmailTemplates(accountId, { scope });
  const create = useCreateEmailTemplate(accountId, scope);
  const [selected, setSelected] = useState<number | null>(null);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const list = templates.data ?? [];
  const current = list.find((item) => item.id === selected) ?? null;

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const created = await create.mutateAsync({
        name: newName.trim(),
        // Starts from the built-in design rather than a blank page, so a
        // new template is already sendable.
        template_html: renderDesign(DEFAULT_DESIGN),
      });
      setNewName("");
      setSelected(created.id);
    } catch (err) {
      setError(
        (err as { message?: string })?.message ??
          t("settingsEmailTpl.createFailed"),
      );
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>
            {scope === "personal"
              ? t("settingsEmailTpl.personalTitle")
              : t("settingsEmailTpl.yours")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {scope === "personal" ? (
            <p className="text-xs text-fg-muted">
              {t("settingsEmailTpl.personalHint")}
            </p>
          ) : null}

          {templates.isLoading ? (
            <p className="text-sm text-fg-muted">{t("common.loading")}</p>
          ) : list.length === 0 ? (
            <p className="text-sm text-fg-muted">
              {scope === "personal"
                ? t("settingsEmailTpl.personalEmpty")
                : t("settingsEmailTpl.empty")}
            </p>
          ) : (
            <ul className="space-y-2">
              {list.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() =>
                      setSelected(item.id === selected ? null : item.id)
                    }
                    aria-pressed={item.id === selected}
                    className={cn(
                      "flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors",
                      item.id === selected
                        ? "border-neon bg-focused text-lit"
                        : "border-glass bg-field text-fg hover:bg-hover-glass",
                    )}
                  >
                    <span className="flex items-center gap-2">
                      <Mail
                        className="h-4 w-4 shrink-0 text-fg-muted"
                        aria-hidden
                      />
                      <span className="font-medium">{item.name}</span>
                    </span>
                    {scope === "personal" && item.is_default ? (
                      <span className="inline-flex items-center gap-1 rounded-sm border border-neon bg-surface-2 px-2 py-0.5 text-xs font-medium text-lit">
                        <Star className="h-3 w-3" aria-hidden />
                        {t("settingsEmailTpl.defaultBadge")}
                      </span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          )}

          <form onSubmit={onCreate} className="flex flex-wrap items-end gap-2">
            <div className="min-w-[12rem] flex-1 space-y-1.5">
              <Label htmlFor={`new-template-${scope}`}>
                {t("settingsEmailTpl.new")}
              </Label>
              <Input
                id={`new-template-${scope}`}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder={t("settingsEmailTpl.namePlaceholder")}
              />
            </div>
            <Button
              type="submit"
              loading={create.isPending}
              disabled={newName.trim() === ""}
            >
              <Plus className="h-4 w-4" aria-hidden />
              {t("settingsEmailTpl.create")}
            </Button>
          </form>
          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {current ? (
        <TemplateEditor
          key={`${scope}-${current.id}`}
          accountId={accountId}
          scope={scope}
          template={current}
          sampleProfile={sampleProfile}
          onDeleted={() => setSelected(null)}
        />
      ) : null}
    </div>
  );
}

function TemplateEditor({
  accountId,
  scope,
  template,
  sampleProfile,
  onDeleted,
}: {
  accountId: string;
  scope: TemplateScope;
  template: EmailTemplate;
  sampleProfile: SampleProfile;
  onDeleted: () => void;
}) {
  const confirm = useConfirm();
  const t = useT();
  const update = useUpdateEmailTemplate(accountId, scope);
  const remove = useDeleteEmailTemplate(accountId, scope);
  const importRef = useRef<HTMLInputElement>(null);

  const [name, setName] = useState(template.name);
  const [isDefault, setIsDefault] = useState(Boolean(template.is_default));
  const [html, setHtml] = useState(template.template_html);
  const savedDesign = template.template_design;
  const [design, setDesign] = useState<TemplateDesign>({
    ...DEFAULT_DESIGN,
    ...(isBlockDocument(savedDesign)
      ? {}
      : ((savedDesign ?? {}) as Partial<TemplateDesign>)),
  });
  const [blocks, setBlocks] = useState<BlockDocument>(
    isBlockDocument(savedDesign) ? savedDesign : DEFAULT_DOCUMENT,
  );
  // Open on whatever produced the saved HTML. Hand-written markup has no
  // design behind it, so opening on an editor would show controls that do
  // not describe it — and saving would silently replace it.
  const [mode, setMode] = useState<"blocks" | "design" | "code">(
    isBlockDocument(savedDesign)
      ? "blocks"
      : template.template_html && !savedDesign
        ? "code"
        : "design",
  );
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [aiNote, setAiNote] = useState<string | null>(null);

  const missingContent = html.trim().length > 0 && !html.includes(CONTENT);

  function touched() {
    setDirty(true);
    setSaved(false);
  }

  async function onImportHtml(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      const text = await file.text();
      setHtml(text);
      setMode("code");
      touched();
    } catch {
      setError(t("settingsEmailTpl.importFailed"));
    }
  }

  function onAiGenerated(result: GeneratedEmailDesign) {
    setHtml(result.html);
    setMode("code");
    setAiNote(result.notes || t("settingsEmailTpl.ai.appliedNote"));
    touched();
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    try {
      await update.mutateAsync({
        id: template.id,
        patch: {
          name: name.trim(),
          ...(scope === "personal" ? { is_default: isDefault } : {}),
          ...(mode === "blocks"
            ? {
                template_html: renderBlocks(blocks, { kind: "template" }),
                template_design: blocks,
              }
            : mode === "design"
              ? { template_html: renderDesign(design), template_design: design }
              : { template_html: html, template_design: null }),
        },
      });
      setSaved(true);
      setDirty(false);
    } catch (err) {
      setError(
        (err as { message?: string })?.message ??
          t("settingsInboxes.saveFailed"),
      );
    }
  }

  async function onDelete() {
    if (
      !(await confirm(
        t("settingsEmailTpl.deleteConfirm", { name: template.name }),
      ))
    ) {
      return;
    }
    setError(null);
    try {
      await remove.mutateAsync(template.id);
      onDeleted();
    } catch (err) {
      setError(
        (err as { message?: string })?.message ?? t("actions.deleteFailed"),
      );
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>
            {t("settingsEmailTpl.editTitle", { name: template.name })}
          </CardTitle>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => setAiOpen(true)}
          >
            <Sparkles className="h-4 w-4 text-lit" aria-hidden />
            {t("settingsEmailTpl.ai.button")}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={save} className="space-y-4">
          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          ) : null}

          {aiNote ? (
            <div
              role="status"
              className="rounded-md border border-neon bg-surface-2 px-3 py-2 text-xs text-fg"
            >
              <strong className="text-lit">{t("settingsEmailTpl.ai.title")}:</strong>{" "}
              {aiNote}
            </div>
          ) : null}

          <div className="grid gap-4 sm:grid-cols-2 sm:items-end">
            <div className="space-y-1.5">
              <Label htmlFor="tpl-name" required>
                {t("profile.name")}
              </Label>
              <Input
                id="tpl-name"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  touched();
                }}
              />
            </div>

            {scope === "personal" ? (
              <label className="flex items-center gap-2 pb-2 text-sm text-fg">
                <input
                  type="checkbox"
                  checked={isDefault}
                  onChange={(e) => {
                    setIsDefault(e.target.checked);
                    touched();
                  }}
                  className="h-4 w-4 rounded border-glass accent-neon"
                />
                {t("settingsEmailTpl.useAsMyDefault")}
              </label>
            ) : null}
          </div>

          <div className="flex gap-1 rounded-control border border-glass bg-field p-1">
            {(
              [
                ["blocks", t("settingsEmailTpl.modeBlocks")],
                ["design", t("settingsEmailTpl.modeSimple")],
                ["code", "HTML"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                aria-pressed={mode === value}
                onClick={() => {
                  if (value === "code" && mode !== "code") {
                    setHtml(
                      mode === "blocks"
                        ? renderBlocks(blocks, { kind: "template" })
                        : renderDesign(design),
                    );
                  }
                  setMode(value);
                  setSaved(false);
                }}
                className={cn(
                  "flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
                  mode === value
                    ? "bg-focused text-lit"
                    : "text-fg-muted hover:bg-hover-glass hover:text-fg",
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {mode === "blocks" ? (
            <BlockEditor
              accountId={accountId}
              doc={blocks}
              kind="template"
              sample={sampleProfile}
              onChange={(next) => {
                setBlocks(next);
                touched();
              }}
            />
          ) : mode === "design" ? (
            <EmailDesigner
              design={design}
              onChange={(d) => {
                setDesign(d);
                touched();
              }}
              logoUrl=""
              signature=""
            />
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Label htmlFor="tpl-html">
                    {t("settingsInboxes.templateHtml")}
                  </Label>
                  <div>
                    <input
                      ref={importRef}
                      type="file"
                      accept=".html,.htm,text/html"
                      onChange={onImportHtml}
                      className="hidden"
                      aria-label={t("settingsEmailTpl.importHtml")}
                    />
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      onClick={() => importRef.current?.click()}
                    >
                      <FileUp className="h-3.5 w-3.5" aria-hidden />
                      {t("settingsEmailTpl.importHtml")}
                    </Button>
                  </div>
                </div>
                <Textarea
                  id="tpl-html"
                  rows={16}
                  value={html}
                  onChange={(e) => {
                    setHtml(e.target.value);
                    touched();
                  }}
                  spellCheck={false}
                  className="font-mono text-xs"
                />
                <div className="flex flex-wrap gap-1">
                  {TEMPLATE_TOKENS.map((token) => (
                    <button
                      key={token}
                      type="button"
                      onClick={() => {
                        setHtml((prev) => `${prev}${prev ? "\n" : ""}${token}`);
                        touched();
                      }}
                      className="rounded-sm border border-glass bg-surface-2 px-1.5 py-0.5 text-[11px] text-lit hover:bg-hover-glass"
                    >
                      + {token}
                    </button>
                  ))}
                </div>
                {missingContent ? (
                  <p role="alert" className="text-xs text-danger">
                    {t("settingsEmailTpl.missingContent", { token: CONTENT })}
                  </p>
                ) : (
                  <p className="text-xs text-fg-muted">
                    {rich(t("settingsEmailTpl.stylesHint"), {
                      style: <code>style</code>, // i18n-ignore
                      styleTag: <code>&lt;style&gt;</code>, // i18n-ignore
                    })}
                  </p>
                )}
              </div>

              <EmailPreviewFrame
                html={html}
                kind="template"
                sample={sampleProfile}
                height={420}
              />
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" loading={update.isPending}>
              {t("actions.save")}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={onDelete}
              loading={remove.isPending}
              className="text-danger hover:bg-hover-glass"
            >
              <Trash2 className="h-4 w-4" aria-hidden />
              {t("actions.delete")}
            </Button>
            {saved ? (
              <span role="status" className="text-sm text-success">
                {t("settingsEmailTpl.savedDot")}
              </span>
            ) : null}
          </div>
        </form>

        <TestSendBox
          accountId={accountId}
          templateId={template.id}
          scope={scope}
          disabled={dirty}
        />

        <AiDesignDialog
          accountId={accountId}
          kind="template"
          open={aiOpen}
          onClose={() => setAiOpen(false)}
          onGenerated={onAiGenerated}
        />
      </CardContent>
    </Card>
  );
}

function SignaturesSection({
  accountId,
  canManageOrg,
  sampleProfile,
}: {
  accountId: string;
  canManageOrg: boolean;
  sampleProfile: SampleProfile;
}) {
  const t = useT();
  const personalSig = useEmailSignature(accountId, "personal");
  const orgSig = useEmailSignature(accountId, "organization");

  return (
    <div className="space-y-6">
      {personalSig.isLoading ? (
        <p className="text-sm text-fg-muted">{t("common.loading")}</p>
      ) : personalSig.data ? (
        <SignatureCard
          key={`personal-${personalSig.data.updated_at ?? "new"}`}
          accountId={accountId}
          scope="personal"
          signature={personalSig.data}
          canEdit
          sampleProfile={sampleProfile}
        />
      ) : null}

      {orgSig.isLoading ? (
        <p className="text-sm text-fg-muted">{t("common.loading")}</p>
      ) : orgSig.data ? (
        <SignatureCard
          key={`org-${orgSig.data.updated_at ?? "new"}`}
          accountId={accountId}
          scope="organization"
          signature={orgSig.data}
          canEdit={canManageOrg}
          sampleProfile={sampleProfile}
        />
      ) : null}
    </div>
  );
}

function SignatureCard({
  accountId,
  scope,
  signature,
  canEdit,
  sampleProfile,
}: {
  accountId: string;
  scope: TemplateScope;
  signature: EmailSignature;
  canEdit: boolean;
  sampleProfile: SampleProfile;
}) {
  const t = useT();
  const saveSig = useUpdateEmailSignature(accountId, scope);
  const importRef = useRef<HTMLInputElement>(null);

  const [blocks, setBlocks] = useState<BlockDocument>(() =>
    isBlockDocument(signature.signature_design)
      ? signature.signature_design
      : createDefaultSignatureDocument(),
  );
  const [html, setHtml] = useState(signature.signature_html);
  const [text, setText] = useState(signature.signature_text);
  const [mode, setMode] = useState<"blocks" | "code">(
    signature.signature_html && !isBlockDocument(signature.signature_design)
      ? "code"
      : "blocks",
  );
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aiOpen, setAiOpen] = useState(false);
  const [aiNote, setAiNote] = useState<string | null>(null);

  async function onImportHtml(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      const content = await file.text();
      setHtml(content);
      setMode("code");
      setSaved(false);
    } catch {
      setError(t("settingsEmailTpl.importFailed"));
    }
  }

  function onAiGenerated(result: GeneratedEmailDesign) {
    setHtml(result.html);
    setMode("code");
    setAiNote(result.notes || t("settingsEmailTpl.ai.appliedNote"));
    setSaved(false);
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    try {
      await saveSig.mutateAsync(
        mode === "blocks"
          ? {
              signature_html: renderBlocks(blocks, { kind: "signature" }),
              signature_design: blocks,
              signature_text: text,
            }
          : {
              signature_html: html,
              signature_design: null,
              signature_text: text,
            },
      );
      setSaved(true);
    } catch (err) {
      setError(
        (err as { message?: string })?.message ??
          t("settingsInboxes.saveFailed"),
      );
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle>
              {scope === "personal"
                ? t("settingsEmailTpl.mySignatureTitle")
                : t("settingsEmailTpl.orgSignatureTitle")}
            </CardTitle>
            <p className="mt-1 text-xs text-fg-muted">
              {scope === "personal"
                ? t("settingsEmailTpl.mySignatureHint")
                : t("settingsEmailTpl.orgSignatureHint")}
            </p>
          </div>
          {canEdit ? (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => setAiOpen(true)}
            >
              <Sparkles className="h-4 w-4 text-lit" aria-hidden />
              {t("settingsEmailTpl.ai.button")}
            </Button>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {!canEdit ? (
          <EmailPreviewFrame
            html={
              signature.signature_html ||
              `<p style="color:#5b6470">${t("settingsEmailTpl.noOrgSignatureYet")}</p>`
            }
            kind="signature"
            sample={sampleProfile}
            height={220}
            compact
          />
        ) : (
          <form onSubmit={onSave} className="space-y-4">
            {error ? (
              <p role="alert" className="text-sm text-danger">
                {error}
              </p>
            ) : null}
            {aiNote ? (
              <div
                role="status"
                className="rounded-md border border-neon bg-surface-2 px-3 py-2 text-xs text-fg"
              >
                <strong className="text-lit">
                  {t("settingsEmailTpl.ai.title")}:
                </strong>{" "}
                {aiNote}
              </div>
            ) : null}

            <div className="flex gap-1 rounded-control border border-glass bg-field p-1">
              {(
                [
                  ["blocks", t("settingsEmailTpl.modeBlocks")],
                  ["code", "HTML"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={mode === value}
                  onClick={() => {
                    if (value === "code" && mode === "blocks") {
                      setHtml(renderBlocks(blocks, { kind: "signature" }));
                    }
                    setMode(value);
                    setSaved(false);
                  }}
                  className={cn(
                    "flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
                    mode === value
                      ? "bg-focused text-lit"
                      : "text-fg-muted hover:bg-hover-glass hover:text-fg",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>

            {mode === "blocks" ? (
              <BlockEditor
                accountId={accountId}
                doc={blocks}
                kind="signature"
                sample={sampleProfile}
                onChange={(next) => {
                  setBlocks(next);
                  setSaved(false);
                }}
              />
            ) : (
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Label htmlFor={`sig-html-${scope}`}>
                      {t("settingsEmailTpl.signatureHtmlLabel")}
                    </Label>
                    <div>
                      <input
                        ref={importRef}
                        type="file"
                        accept=".html,.htm,text/html"
                        onChange={onImportHtml}
                        className="hidden"
                        aria-label={t("settingsEmailTpl.importHtml")}
                      />
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        onClick={() => importRef.current?.click()}
                      >
                        <FileUp className="h-3.5 w-3.5" aria-hidden />
                        {t("settingsEmailTpl.importHtml")}
                      </Button>
                    </div>
                  </div>
                  <Textarea
                    id={`sig-html-${scope}`}
                    rows={10}
                    value={html}
                    onChange={(e) => {
                      setHtml(e.target.value);
                      setSaved(false);
                    }}
                    spellCheck={false}
                    className="font-mono text-xs"
                  />
                  <div className="flex flex-wrap gap-1">
                    {SIGNATURE_TOKENS.map((token) => (
                      <button
                        key={token}
                        type="button"
                        onClick={() => {
                          setHtml((prev) => `${prev}${prev ? " " : ""}${token}`);
                          setSaved(false);
                        }}
                        className="rounded-sm border border-glass bg-surface-2 px-1.5 py-0.5 text-[11px] text-lit hover:bg-hover-glass"
                      >
                        + {token}
                      </button>
                    ))}
                  </div>
                </div>

                <EmailPreviewFrame
                  html={html}
                  kind="signature"
                  sample={sampleProfile}
                  height={280}
                />
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor={`sig-text-${scope}`}>
                {t("settingsEmailTpl.signaturePlainLabel")}
              </Label>
              <Textarea
                id={`sig-text-${scope}`}
                rows={3}
                value={text}
                onChange={(e) => {
                  setText(e.target.value);
                  setSaved(false);
                }}
                placeholder={
                  signature.fallback_text ||
                  t("settingsEmailTpl.signaturePlainPlaceholder")
                }
              />
              <p className="text-xs text-fg-muted">
                {t("settingsEmailTpl.signaturePlainHint")}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Button type="submit" loading={saveSig.isPending}>
                {t("actions.save")}
              </Button>
              {saved ? (
                <span role="status" className="text-sm text-success">
                  {t("settingsEmailTpl.savedDot")}
                </span>
              ) : null}
            </div>
          </form>
        )}

        <AiDesignDialog
          accountId={accountId}
          kind="signature"
          open={aiOpen}
          onClose={() => setAiOpen(false)}
          onGenerated={onAiGenerated}
        />
      </CardContent>
    </Card>
  );
}
