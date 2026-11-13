"use client";

import { FileText, Lock, Paperclip, Send, X, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  WhatsappTemplatePreview,
  renderTemplateText,
} from "@/components/settings/inboxes/whatsapp-templates-panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCannedResponses } from "@/lib/api/canned-responses";
import { useConversation, useSendMessage } from "@/lib/api/conversations";
import { uploadAttachment } from "@/lib/api/uploads";
import { useWhatsappTemplates } from "@/lib/api/whatsapp-templates";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

type PendingAttachment = {
  key: string;
  external_url: string;
  file_type: string;
  name: string;
  // Local object URL for an instant image thumbnail (revoked on remove/send).
  previewUrl?: string;
};

// Matches the backend's NUMBER_OF_PERMITTED_ATTACHMENTS cap.
const MAX_ATTACHMENTS = 15;
const MAX_TEXTAREA_HEIGHT_PX = 144; // ~6 lines

const WHATSAPP_24H_NOTICE =
  "Pasaron 24 h desde el último mensaje del contacto. Solo podés mandar una plantilla.";

export function MessageComposer({
  accountId,
  displayId,
  inboxId: inboxIdProp,
  channel: channelProp,
  canReply: canReplyProp,
}: {
  accountId: string;
  displayId: number;
  inboxId?: number | null;
  channel?: string | null;
  canReply?: boolean;
}) {
  const t = useT();
  const [content, setContent] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [templateOpen, setTemplateOpen] = useState(false);
  const [selectedTemplateName, setSelectedTemplateName] = useState("");
  const [templateVars, setTemplateVars] = useState<Record<string, string>>({});
  const [attachments, setAttachments] = useState<PendingAttachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const keyRef = useRef(0);
  const send = useSendMessage(accountId, displayId);
  const canned = useCannedResponses(accountId);
  const conv = useConversation(accountId, displayId);

  const channel = channelProp ?? conv.data?.meta?.channel ?? null;
  const inboxId = inboxIdProp ?? conv.data?.inbox_id ?? null;
  const canReply = canReplyProp ?? conv.data?.can_reply ?? true;
  const isWhatsapp = channel === "Channel::Whatsapp";
  const windowClosed = isWhatsapp && !canReply;

  const templatesQ = useWhatsappTemplates(
    accountId,
    inboxId,
    isWhatsapp && templateOpen,
  );
  const approvedTemplates = templatesQ.data?.templates ?? [];
  const selectedTemplate = approvedTemplates.find(
    (tpl) => tpl.name === selectedTemplateName,
  );
  const canSendTemplate =
    Boolean(selectedTemplate) &&
    (selectedTemplate?.variables ?? []).every((n) =>
      Boolean((templateVars[String(n)] ?? "").trim()),
    );

  // One line that grows with the text, like the agent composer.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    if (!content) {
      el.style.height = "";
      el.style.overflowY = "";
      return;
    }
    el.style.overflowY = "hidden";
    el.style.height = "auto";
    if (el.scrollHeight > 0) {
      const border = el.offsetHeight - el.clientHeight;
      const fullHeight = el.scrollHeight + border;
      el.style.height = `${Math.min(fullHeight, MAX_TEXTAREA_HEIGHT_PX)}px`;
      // Scroll only once the text is taller than the box can grow.
      el.style.overflowY =
        fullHeight > MAX_TEXTAREA_HEIGHT_PX ? "auto" : "hidden";
    }
  }, [content]);

  useEffect(() => {
    if (!pickerOpen) return;
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setPickerOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setPickerOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      window.removeEventListener("keydown", onKey);
    };
  }, [pickerOpen]);

  // Canned-response quick-insert: while the whole draft is a single
  // "/token", offer the matching responses (Chatwoot's "/" shortcut).
  const slashMatch = /^\/(\S*)$/.exec(content);
  const slashQuery = slashMatch ? slashMatch[1].toLowerCase() : null;
  const allCanned = canned.data ?? [];
  const slashMatches =
    slashQuery !== null
      ? allCanned
          .filter((c) => c.short_code.toLowerCase().includes(slashQuery))
          .slice(0, 6)
      : [];

  const showListbox =
    (slashQuery !== null && slashMatches.length > 0) || pickerOpen;
  const visibleCanned =
    slashQuery !== null ? slashMatches : allCanned.slice(0, 8);

  function insertCanned(text: string) {
    setContent(text);
    setPickerOpen(false);
    // Refocus so the agent keeps editing right after inserting.
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = [...(e.target.files ?? [])];
    e.target.value = ""; // let the same files be re-picked after removal
    if (picked.length === 0) return;
    const room = MAX_ATTACHMENTS - attachments.length;
    const files = picked.slice(0, Math.max(0, room));
    if (files.length === 0) return;

    setUploadError(false);
    setUploading(true);
    const results = await Promise.allSettled(
      files.map(async (file): Promise<PendingAttachment> => {
        const up = await uploadAttachment(accountId, file);
        const previewUrl = file.type.startsWith("image/")
          ? URL.createObjectURL(file)
          : undefined;
        return {
          ...up,
          name: file.name,
          key: String(keyRef.current++),
          previewUrl,
        };
      }),
    );
    const ok = results
      .filter(
        (r): r is PromiseFulfilledResult<PendingAttachment> =>
          r.status === "fulfilled",
      )
      .map((r) => r.value);
    if (ok.length > 0) setAttachments((prev) => [...prev, ...ok]);
    if (ok.length < files.length) setUploadError(true);
    setUploading(false);
  }

  function removeAttachment(key: string) {
    setAttachments((prev) => {
      const gone = prev.find((a) => a.key === key);
      if (gone?.previewUrl) URL.revokeObjectURL(gone.previewUrl);
      return prev.filter((a) => a.key !== key);
    });
  }

  function submit() {
    if (windowClosed && !isPrivate) return;
    const text = content.trim();
    if ((!text && attachments.length === 0) || uploading) return;
    // The thread shows it right away (and keeps it if it fails), so the box
    // is free for the next message.
    send.mutate({
      content: text || undefined,
      isPrivate,
      attachments: attachments.length
        ? attachments.map((a) => ({
            external_url: a.external_url,
            file_type: a.file_type,
          }))
        : undefined,
    });
    setContent("");
    setPickerOpen(false);
    attachments.forEach(
      (a) => a.previewUrl && URL.revokeObjectURL(a.previewUrl),
    );
    setAttachments([]);
    textareaRef.current?.focus();
  }

  function submitTemplate() {
    if (!selectedTemplate || !canSendTemplate) return;
    const bodyParams: Record<string, string> = {};
    for (const n of selectedTemplate.variables) {
      bodyParams[String(n)] = (templateVars[String(n)] ?? "").trim();
    }
    const renderedContent = renderTemplateText(
      selectedTemplate.body_text ?? selectedTemplate.name,
      bodyParams,
    );
    send.mutate({
      content: renderedContent,
      isPrivate: false,
      templateParams: {
        name: selectedTemplate.name,
        language: selectedTemplate.language ?? "es",
        processed_params: { body: bodyParams },
      },
    });
    setTemplateOpen(false);
    setSelectedTemplateName("");
    setTemplateVars({});
  }

  return (
    <div ref={wrapRef} className="relative border-t border-glass bg-surface p-3">
      {showListbox ? (
        <ul
          role="listbox"
          aria-label={t("conversations.composer.cannedResponses")}
          className="absolute bottom-full left-3 right-3 z-20 mb-1 max-h-56 overflow-auto rounded-md border border-glass bg-surface-2 shadow-menu"
        >
          {visibleCanned.length === 0 ? (
            <li className="px-3 py-2 text-xs text-fg-muted">
              {t("conversations.composer.noCanned")}
            </li>
          ) : (
            visibleCanned.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => insertCanned(c.content)}
                  className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left hover:bg-hover-glass focus-visible:bg-hover-glass focus-visible:outline-none"
                >
                  <code className="text-xs font-semibold text-lit">
                    /{c.short_code}
                  </code>
                  <span className="w-full truncate text-xs text-fg-muted">
                    {c.content}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}

      {isWhatsapp && templateOpen ? (
        <div
          role="region"
          aria-label="Selector de plantilla de WhatsApp"
          className="mb-3 space-y-3 rounded-lg border border-glass bg-surface-2 p-3"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-fg">
              Enviar plantilla de WhatsApp
            </span>
            <button
              type="button"
              aria-label="Cerrar selector de plantilla"
              onClick={() => setTemplateOpen(false)}
              className="rounded p-1 text-fg-muted hover:bg-hover-glass hover:text-fg"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>

          {templatesQ.isLoading ? (
            <p className="text-xs text-fg-muted">Cargando plantillas…</p>
          ) : approvedTemplates.length === 0 ? (
            <p className="text-xs text-fg-muted">
              No hay plantillas aprobadas en esta bandeja.
            </p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <div className="space-y-1">
                  <Label htmlFor="composer-wa-template">Elegir plantilla</Label>
                  <select
                    id="composer-wa-template"
                    className={selectClassName("sm")}
                    value={selectedTemplateName}
                    onChange={(e) => {
                      setSelectedTemplateName(e.target.value);
                      setTemplateVars({});
                    }}
                  >
                    <option value="">Elegí una plantilla…</option>
                    {approvedTemplates.map((tpl) => (
                      <option
                        key={`${tpl.name}:${tpl.language ?? ""}`}
                        value={tpl.name}
                      >
                        {tpl.name} ({tpl.language ?? "es"})
                      </option>
                    ))}
                  </select>
                </div>

                {(selectedTemplate?.variables ?? []).map((n) => (
                  <div key={n} className="space-y-1">
                    <Label htmlFor={`composer-wa-var-${n}`}>
                      {`Variable {{${n}}}`}
                    </Label>
                    <Input
                      id={`composer-wa-var-${n}`}
                      value={templateVars[String(n)] ?? ""}
                      onChange={(e) =>
                        setTemplateVars((prev) => ({
                          ...prev,
                          [String(n)]: e.target.value,
                        }))
                      }
                      placeholder={`Valor para {{${n}}}`}
                    />
                  </div>
                ))}

                <p className="text-[11px] text-fg-muted">
                  Meta cobra cada plantilla que entrega.
                </p>

                <div className="flex items-center gap-2 pt-1">
                  <Button
                    type="button"
                    size="sm"
                    onClick={submitTemplate}
                    disabled={!canSendTemplate}
                  >
                    Enviar
                  </Button>
                </div>
              </div>

              {selectedTemplate ? (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-fg-muted">
                    Vista previa
                  </p>
                  <WhatsappTemplatePreview
                    body={selectedTemplate.body_text ?? ""}
                    bodyValues={templateVars}
                  />
                </div>
              ) : null}
            </div>
          )}
        </div>
      ) : null}

      {attachments.length > 0 ? (
        <div className="mb-2 flex flex-wrap gap-2">
          {attachments.map((att) =>
            att.previewUrl ? (
              <div
                key={att.key}
                className="group relative h-20 w-20 overflow-hidden rounded-md border border-glass"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={att.previewUrl}
                  alt={att.name}
                  className="h-full w-full object-cover"
                />
                <button
                  type="button"
                  onClick={() => removeAttachment(att.key)}
                  aria-label={t("conversations.composer.removeAttachment", {
                    name: att.name,
                  })}
                  className="absolute right-1 top-1 rounded-full bg-backdrop p-0.5 text-white hover:opacity-90"
                >
                  <X className="h-3.5 w-3.5" aria-hidden />
                </button>
              </div>
            ) : (
              <span
                key={att.key}
                className="flex items-center gap-2 rounded-md border border-glass bg-surface-2 px-2 py-1 text-xs"
              >
                <Paperclip
                  className="h-3 w-3 shrink-0 text-fg-muted"
                  aria-hidden
                />
                <span className="max-w-[12rem] truncate text-fg">
                  {att.name}
                </span>
                <button
                  type="button"
                  onClick={() => removeAttachment(att.key)}
                  aria-label={t("conversations.composer.removeAttachment", {
                    name: att.name,
                  })}
                  className="rounded-sm p-0.5 text-fg-muted hover:text-danger"
                >
                  <X className="h-3 w-3" aria-hidden />
                </button>
              </span>
            ),
          )}
        </div>
      ) : null}

      {windowClosed && !isPrivate ? (
        <p className="mb-2 rounded-md border border-warning bg-surface-2 px-3 py-1.5 text-xs text-warning">
          {WHATSAPP_24H_NOTICE}
        </p>
      ) : null}

      <Textarea
        ref={textareaRef}
        value={content}
        disabled={windowClosed && !isPrivate}
        onChange={(e) => setContent(e.target.value)}
        onKeyDown={(e) => {
          // Enter sends, or takes the first quick reply while they are
          // listed; Shift+Enter is a new line.
          if (
            e.key === "Enter" &&
            !e.shiftKey &&
            !e.nativeEvent.isComposing
          ) {
            e.preventDefault();
            if (showListbox && visibleCanned[0]) {
              insertCanned(visibleCanned[0].content);
            } else {
              submit();
            }
          }
        }}
        rows={1}
        placeholder={
          isPrivate
            ? t("conversations.composer.notePlaceholder")
            : windowClosed
              ? WHATSAPP_24H_NOTICE
              : t("conversations.composer.replyPlaceholder")
        }
        aria-label={
          isPrivate
            ? t("conversations.composer.privateNote")
            : t("conversations.composer.reply")
        }
        className={cn("overflow-y-hidden", isPrivate && "border-warning")}
      />

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setIsPrivate((v) => !v)}
          aria-pressed={isPrivate}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-control border px-2.5 py-1.5 text-xs font-medium transition-colors",
            "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
            isPrivate
              ? "border-warning bg-surface-2 text-warning"
              : "border-glass bg-field text-fg-muted hover:bg-hover-glass hover:text-fg",
          )}
        >
          <Lock className="h-3.5 w-3.5" aria-hidden />
          {t("conversations.composer.privateNote")}
        </button>

        <button
          type="button"
          onClick={() => setPickerOpen((v) => !v)}
          aria-expanded={showListbox}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-control border px-2.5 py-1.5 text-xs font-medium transition-colors",
            "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
            pickerOpen
              ? "border-neon bg-focused text-lit"
              : "border-glass bg-field text-fg-muted hover:bg-hover-glass hover:text-fg",
          )}
        >
          <Zap className="h-3.5 w-3.5" aria-hidden />
          {t("conversations.composer.quickReplies")}
        </button>

        {isWhatsapp ? (
          <button
            type="button"
            onClick={() => setTemplateOpen((v) => !v)}
            aria-expanded={templateOpen}
            data-highlighted={windowClosed ? "true" : undefined}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-control border px-2.5 py-1.5 text-xs font-medium transition-colors",
              "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
              templateOpen || windowClosed
                ? "border-neon bg-focused font-semibold text-lit ring-1 ring-neon"
                : "border-glass bg-field text-fg-muted hover:bg-hover-glass hover:text-fg",
            )}
          >
            <FileText className="h-3.5 w-3.5" aria-hidden />
            Plantilla
          </button>
        ) : null}

        <input
          ref={fileRef}
          type="file"
          multiple
          onChange={onPickFile}
          className="hidden"
          aria-label={t("conversations.composer.attach")}
          tabIndex={-1}
        />
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => fileRef.current?.click()}
          loading={uploading}
          disabled={uploading || attachments.length >= MAX_ATTACHMENTS}
          aria-label={t("conversations.composer.attach")}
        >
          <Paperclip className="h-3.5 w-3.5" aria-hidden />
        </Button>

        {!templateOpen ? (
          <Button
            type="button"
            variant={isPrivate ? "ghost" : "primary"}
            size="icon"
            onClick={submit}
            disabled={
              uploading ||
              (windowClosed && !isPrivate) ||
              (!content.trim() && attachments.length === 0)
            }
            aria-label={t("actions.send")}
            title={t("actions.send")}
            className={cn(
              "ml-auto h-8 w-8 rounded-full p-0",
              isPrivate &&
                "border border-warning bg-warning text-white hover:bg-warning hover:opacity-90 dark:text-bg",
            )}
          >
            <Send className="h-4 w-4" aria-hidden />
          </Button>
        ) : null}
      </div>

      {uploadError ? (
        <p role="alert" className="mt-1 text-xs text-danger">
          {t("conversations.composer.uploadFailed")}
        </p>
      ) : null}
    </div>
  );
}
