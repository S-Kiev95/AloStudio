"use client";

import {
  ArrowDown,
  ArrowUp,
  Columns2,
  FolderOpen,
  GripVertical,
  Image as ImageIcon,
  LayoutTemplate,
  Minus,
  MousePointerClick,
  PenLine,
  Plus,
  Redo2,
  Share2,
  Trash2,
  Type,
  Undo2,
  Upload,
} from "lucide-react";
import {
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
  useRef,
  useState,
} from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch } from "@/lib/api/fetcher";
import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";
import {
  type Align,
  type Block,
  type BlockDocument,
  type ButtonBlock,
  type CanvasKind,
  type ColumnsBlock,
  type DividerBlock,
  type HeaderBlock,
  type ImageBlock,
  type SignatureBlock,
  type SocialBlock,
  type SpacerBlock,
  type TextBlock,
  blankBlock,
  newId,
  renderBlocks,
} from "@/lib/inboxes/email-blocks";
import { cn } from "@/lib/utils";

import { EmailPreviewFrame, type SampleProfile } from "./email-preview-frame";

const TEMPLATE_PALETTE: { type: Block["type"]; icon: typeof Type }[] = [
  { type: "header", icon: LayoutTemplate },
  { type: "text", icon: Type },
  { type: "image", icon: ImageIcon },
  { type: "button", icon: MousePointerClick },
  { type: "columns", icon: Columns2 },
  { type: "social", icon: Share2 },
  { type: "divider", icon: Minus },
  { type: "spacer", icon: ArrowDown },
  { type: "signature", icon: PenLine },
];

const SIGNATURE_PALETTE: { type: Block["type"]; icon: typeof Type }[] = [
  { type: "header", icon: LayoutTemplate },
  { type: "text", icon: Type },
  { type: "image", icon: ImageIcon },
  { type: "button", icon: MousePointerClick },
  { type: "columns", icon: Columns2 },
  { type: "social", icon: Share2 },
  { type: "divider", icon: Minus },
  { type: "spacer", icon: ArrowDown },
];

const BLOCK_NAMES: Record<Block["type"], MessageKey> = {
  header: "settingsEmailTpl.blocks.header",
  text: "settingsEmailTpl.blocks.text",
  image: "settingsEmailTpl.blocks.image",
  button: "settingsEmailTpl.blocks.button",
  divider: "settingsEmailTpl.blocks.divider",
  spacer: "settingsEmailTpl.blocks.spacer",
  columns: "settingsEmailTpl.blocks.columns",
  social: "settingsEmailTpl.blocks.social",
  content: "settingsEmailTpl.blocks.content",
  signature: "settingsEmailTpl.blocks.signature",
};

const SIGNATURE_VARS = [
  "{{nombre}}",
  "{{cargo}}",
  "{{correo}}",
  "{{telefono}}",
  "{{foto}}",
] as const;

const MAX_HISTORY = 40;

type MediaItem = {
  id: number;
  filename: string;
  url: string;
  kind: string;
};

/**
 * Visual block canvas for both email templates and signatures.
 *
 * Supports drag-and-drop reordering and palette dropping, an inspector for
 * the selected block (colors, alignment, size, margins, links, media),
 * undo/redo history, and a live sandboxed iframe preview (desktop/mobile,
 * light/dark).
 */
export function BlockEditor({
  accountId,
  doc,
  onChange,
  kind = "template",
  sample,
}: {
  accountId: string;
  doc: BlockDocument;
  onChange: (next: BlockDocument) => void;
  kind?: CanvasKind;
  sample?: SampleProfile;
}) {
  const t = useT();
  const [selected, setSelected] = useState<string | null>(null);
  const [past, setPast] = useState<BlockDocument[]>([]);
  const [future, setFuture] = useState<BlockDocument[]>([]);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);

  const palette = kind === "signature" ? SIGNATURE_PALETTE : TEMPLATE_PALETTE;

  function commit(next: BlockDocument) {
    setPast((prev) => [...prev.slice(-(MAX_HISTORY - 1)), doc]);
    setFuture([]);
    onChange(next);
  }

  function undo() {
    if (past.length === 0) return;
    const previous = past[past.length - 1];
    setPast((prev) => prev.slice(0, -1));
    setFuture((prev) => [doc, ...prev.slice(0, MAX_HISTORY - 1)]);
    onChange(previous);
  }

  function redo() {
    if (future.length === 0) return;
    const next = future[0];
    setFuture((prev) => prev.slice(1));
    setPast((prev) => [...prev.slice(-(MAX_HISTORY - 1)), doc]);
    onChange(next);
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (!(e.ctrlKey || e.metaKey)) return;
    const key = e.key.toLowerCase();
    if (key === "z" && !e.shiftKey) {
      if (past.length > 0) {
        e.preventDefault();
        undo();
      }
    } else if (key === "y" || (key === "z" && e.shiftKey)) {
      if (future.length > 0) {
        e.preventDefault();
        redo();
      }
    }
  }

  function setBlocks(blocks: Block[]) {
    commit({ ...doc, blocks });
  }

  function add(type: Block["type"], atIndex?: number) {
    const block = blankBlock(type);
    const next = [...doc.blocks];
    if (atIndex !== undefined && atIndex >= 0 && atIndex <= next.length) {
      next.splice(atIndex, 0, block);
    } else {
      next.push(block);
    }
    setBlocks(next);
    setSelected(block.id);
  }

  function update(id: string, patch: Partial<Block>) {
    setBlocks(
      doc.blocks.map((b) => (b.id === id ? ({ ...b, ...patch } as Block) : b)),
    );
  }

  function remove(id: string) {
    setBlocks(doc.blocks.filter((b) => b.id !== id));
    if (selected === id) setSelected(null);
  }

  function move(id: string, delta: -1 | 1) {
    const i = doc.blocks.findIndex((b) => b.id === id);
    const j = i + delta;
    if (i < 0 || j < 0 || j >= doc.blocks.length) return;
    const next = [...doc.blocks];
    [next[i], next[j]] = [next[j], next[i]];
    setBlocks(next);
  }

  function moveIndex(from: number, to: number) {
    if (from === to || from < 0 || to < 0 || from >= doc.blocks.length || to >= doc.blocks.length) {
      return;
    }
    const next = [...doc.blocks];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    setBlocks(next);
  }

  function onRowDragStart(e: DragEvent<HTMLLIElement>, idx: number) {
    setDragIndex(idx);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("application/x-email-block-index", String(idx));
  }

  function onPaletteDragStart(e: DragEvent<HTMLButtonElement>, type: Block["type"]) {
    e.dataTransfer.effectAllowed = "copy";
    e.dataTransfer.setData("application/x-email-new-block", type);
  }

  function onRowDragOver(e: DragEvent<HTMLLIElement>, idx: number) {
    e.preventDefault();
    if (dropIndex !== idx) setDropIndex(idx);
  }

  function onRowDrop(e: DragEvent<HTMLLIElement>, targetIdx: number) {
    e.preventDefault();
    const newType = e.dataTransfer.getData("application/x-email-new-block") as Block["type"];
    const fromRaw = e.dataTransfer.getData("application/x-email-block-index");
    if (newType && newType in BLOCK_NAMES) {
      add(newType, targetIdx);
    } else if (fromRaw !== "") {
      moveIndex(Number(fromRaw), targetIdx);
    } else if (dragIndex !== null) {
      moveIndex(dragIndex, targetIdx);
    }
    setDragIndex(null);
    setDropIndex(null);
  }

  function onDragEnd() {
    setDragIndex(null);
    setDropIndex(null);
  }

  const previewHtml = renderBlocks(doc, { kind });

  return (
    <div onKeyDown={onKeyDown} className="grid gap-4 lg:grid-cols-2">
      {/* ---- Left column: toolbar, page settings, block stack & palette ---- */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-glass bg-surface-1 px-3 py-2">
          <span className="text-xs font-medium text-fg-muted">
            {t("settingsEmailTpl.dragHint")}
          </span>
          <div className="flex items-center gap-1">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={undo}
              disabled={past.length === 0}
              aria-label={t("settingsEmailTpl.undo")}
              title={t("settingsEmailTpl.undo")}
            >
              <Undo2 className="h-3.5 w-3.5" aria-hidden />
              {t("settingsEmailTpl.undo")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={redo}
              disabled={future.length === 0}
              aria-label={t("settingsEmailTpl.redo")}
              title={t("settingsEmailTpl.redo")}
            >
              <Redo2 className="h-3.5 w-3.5" aria-hidden />
              {t("settingsEmailTpl.redo")}
            </Button>
          </div>
        </div>

        <PageControls
          kind={kind}
          page={doc.page}
          onChange={(page) => commit({ ...doc, page })}
        />

        {kind === "signature" ? (
          <div className="rounded-md border border-glass bg-surface-1 p-2.5">
            <p className="mb-1.5 text-xs font-medium text-fg">
              {t("settingsEmailTpl.signatureVarsTitle")}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {SIGNATURE_VARS.map((token) => (
                <code
                  key={token}
                  className="rounded-sm border border-glass bg-surface-2 px-1.5 py-0.5 text-xs text-lit"
                >
                  {token}
                </code>
              ))}
            </div>
          </div>
        ) : null}

        <ul className="space-y-2" aria-label={t("settingsEmailTpl.blockList")}>
          {doc.blocks.map((block, i) => (
            <li
              key={block.id}
              draggable
              onDragStart={(e) => onRowDragStart(e, i)}
              onDragOver={(e) => onRowDragOver(e, i)}
              onDrop={(e) => onRowDrop(e, i)}
              onDragEnd={onDragEnd}
              className={cn(
                "rounded-md border transition-colors",
                dropIndex === i
                  ? "border-neon bg-focused"
                  : selected === block.id
                    ? "border-neon bg-focused"
                    : "border-glass bg-field",
              )}
            >
              <div className="flex items-center gap-1 px-2 py-1.5">
                <span
                  className="cursor-grab text-fg-muted"
                  aria-hidden
                  title={t("settingsEmailTpl.dragHint")}
                >
                  <GripVertical className="h-4 w-4" />
                </span>
                <button
                  type="button"
                  onClick={() =>
                    setSelected(selected === block.id ? null : block.id)
                  }
                  className="flex-1 text-left text-sm font-medium text-fg"
                  aria-expanded={selected === block.id}
                >
                  {t(BLOCK_NAMES[block.type])}
                </button>
                <IconButton
                  label={t("settingsEmailTpl.moveUp", {
                    block: t(BLOCK_NAMES[block.type]),
                  })}
                  onClick={() => move(block.id, -1)}
                  disabled={i === 0}
                >
                  <ArrowUp className="h-3.5 w-3.5" aria-hidden />
                </IconButton>
                <IconButton
                  label={t("settingsEmailTpl.moveDown", {
                    block: t(BLOCK_NAMES[block.type]),
                  })}
                  onClick={() => move(block.id, 1)}
                  disabled={i === doc.blocks.length - 1}
                >
                  <ArrowDown className="h-3.5 w-3.5" aria-hidden />
                </IconButton>
                <IconButton
                  label={t("settingsEmailTpl.removeBlock", {
                    block: t(BLOCK_NAMES[block.type]),
                  })}
                  onClick={() => remove(block.id)}
                >
                  <Trash2 className="h-3.5 w-3.5 text-danger" aria-hidden />
                </IconButton>
              </div>

              {selected === block.id ? (
                <div className="space-y-3 border-t border-glass bg-surface p-3">
                  <BlockFields
                    accountId={accountId}
                    block={block}
                    kind={kind}
                    onChange={(patch) => update(block.id, patch)}
                  />
                </div>
              ) : null}
            </li>
          ))}
        </ul>

        <div className="space-y-1.5 rounded-md border border-glass bg-surface-1 p-3">
          <p className="text-xs font-medium text-fg-muted">
            {t("settingsEmailTpl.addBlock")}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {palette.map(({ type, icon: Icon }) => (
              <Button
                key={type}
                type="button"
                size="sm"
                variant="secondary"
                draggable
                onDragStart={(e) => onPaletteDragStart(e, type)}
                onClick={() => add(type)}
              >
                <Icon className="h-3.5 w-3.5" aria-hidden />
                {t(BLOCK_NAMES[type])}
              </Button>
            ))}
          </div>
        </div>

        {kind === "template" && !doc.blocks.some((b) => b.type === "content") ? (
          <p role="alert" className="text-xs text-warning">
            {t("settingsEmailTpl.missingContentBlock")}
            <button
              type="button"
              onClick={() => add("content")}
              className="ml-1 underline"
            >
              {t("settingsEmailTpl.addIt")}
            </button>
          </p>
        ) : null}
      </div>

      {/* ---- Right column: sandboxed preview ---- */}
      <EmailPreviewFrame
        html={previewHtml}
        kind={kind}
        sample={sample}
        height={kind === "signature" ? 320 : 520}
      />
    </div>
  );
}

function IconButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className="rounded-sm p-1 text-fg-muted hover:bg-hover-glass hover:text-fg disabled:opacity-40"
    >
      {children}
    </button>
  );
}

function PageControls({
  kind,
  page,
  onChange,
}: {
  kind: CanvasKind;
  page: BlockDocument["page"];
  onChange: (p: BlockDocument["page"]) => void;
}) {
  const t = useT();
  return (
    <div className="grid grid-cols-2 gap-3 rounded-md border border-glass p-3">
      {kind === "template" ? (
        <ColorField
          id="page-bg"
          label={t("settingsEmailTpl.background")}
          value={page.pageColor}
          onChange={(v) => onChange({ ...page, pageColor: v })}
        />
      ) : null}
      <ColorField
        id="body-bg"
        label={t("settingsEmailTpl.card")}
        value={page.bodyColor}
        onChange={(v) => onChange({ ...page, bodyColor: v })}
      />
      <div className="col-span-2 space-y-1.5">
        <Label htmlFor="page-width">
          {t("settingsEmailTpl.widthPx", { n: page.width })}
        </Label>
        <input
          id="page-width"
          type="range"
          min={kind === "signature" ? 320 : 480}
          max={700}
          step={20}
          value={page.width}
          onChange={(e) => onChange({ ...page, width: Number(e.target.value) })}
          className="w-full accent-neon"
        />
      </div>
    </div>
  );
}

function BlockFields({
  accountId,
  block,
  kind,
  onChange,
}: {
  accountId: string;
  block: Block;
  kind: CanvasKind;
  onChange: (patch: Partial<Block>) => void;
}) {
  const t = useT();
  switch (block.type) {
    case "header":
      return (
        <HeaderFields accountId={accountId} block={block} onChange={onChange} />
      );
    case "text":
      return <TextFields block={block} kind={kind} onChange={onChange} />;
    case "image":
      return (
        <ImageFields accountId={accountId} block={block} onChange={onChange} />
      );
    case "button":
      return <ButtonFields block={block} onChange={onChange} />;
    case "columns":
      return (
        <ColumnsFields accountId={accountId} block={block} onChange={onChange} />
      );
    case "social":
      return <SocialFields block={block} onChange={onChange} />;
    case "spacer":
      return <SpacerFields block={block} onChange={onChange} />;
    case "signature":
      return <SignatureFields block={block} onChange={onChange} />;
    case "divider":
      return <DividerFields block={block} onChange={onChange} />;
    case "content":
      return (
        <p className="text-xs text-fg-muted">
          {t("settingsEmailTpl.contentBlockHint")}
        </p>
      );
  }
}

function HeaderFields({
  accountId,
  block,
  onChange,
}: {
  accountId: string;
  block: HeaderBlock;
  onChange: (patch: Partial<Block>) => void;
}) {
  const t = useT();
  return (
    <>
      <ImageUploadControls
        accountId={accountId}
        idPrefix={`hdr-${block.id}`}
        value={block.logoUrl}
        onChange={(url) => onChange({ logoUrl: url } as Partial<Block>)}
      />
      <div className="space-y-1.5">
        <Label htmlFor={`hdr-title-${block.id}`}>
          {t("settingsEmailTpl.headerTitle")}
        </Label>
        <Input
          id={`hdr-title-${block.id}`}
          value={block.title}
          onChange={(e) => onChange({ title: e.target.value } as Partial<Block>)}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`hdr-sub-${block.id}`}>
          {t("settingsEmailTpl.headerSubtitle")}
        </Label>
        <Input
          id={`hdr-sub-${block.id}`}
          value={block.subtitle}
          onChange={(e) =>
            onChange({ subtitle: e.target.value } as Partial<Block>)
          }
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <ColorField
          id={`hdr-bg-${block.id}`}
          label={t("settingsEmailTpl.background")}
          value={block.background}
          onChange={(v) => onChange({ background: v } as Partial<Block>)}
        />
        <ColorField
          id={`hdr-fg-${block.id}`}
          label={t("settingsEmailTpl.blocks.text")}
          value={block.textColor}
          onChange={(v) => onChange({ textColor: v } as Partial<Block>)}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <AlignField
          id={`hdr-align-${block.id}`}
          value={block.align}
          onChange={(v) => onChange({ align: v } as Partial<Block>)}
        />
        <PaddingField
          id={`hdr-pad-${block.id}`}
          value={block.paddingY ?? 20}
          onChange={(v) => onChange({ paddingY: v } as Partial<Block>)}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`hdr-lw-${block.id}`}>
          {t("settingsEmailTpl.logoWidthPx", { n: block.logoWidth })}
        </Label>
        <input
          id={`hdr-lw-${block.id}`}
          type="range"
          min={40}
          max={260}
          step={10}
          value={block.logoWidth}
          onChange={(e) =>
            onChange({ logoWidth: Number(e.target.value) } as Partial<Block>)
          }
          className="w-full accent-neon"
        />
      </div>
    </>
  );
}

function TextFields({
  block,
  kind,
  onChange,
}: {
  block: TextBlock;
  kind: CanvasKind;
  onChange: (patch: Partial<Block>) => void;
}) {
  const t = useT();
  return (
    <>
      <div className="space-y-1.5">
        <Label htmlFor={`text-${block.id}`}>
          {t("settingsEmailTpl.blocks.text")}
        </Label>
        <Textarea
          id={`text-${block.id}`}
          rows={3}
          value={block.text}
          onChange={(e) => onChange({ text: e.target.value } as Partial<Block>)}
        />
        {kind === "signature" ? (
          <div className="flex flex-wrap gap-1">
            {SIGNATURE_VARS.map((token) => (
              <button
                key={token}
                type="button"
                onClick={() =>
                  onChange({
                    text: block.text ? `${block.text} ${token}` : token,
                  } as Partial<Block>)
                }
                className="rounded-sm border border-glass bg-surface-2 px-1.5 py-0.5 text-[11px] text-lit hover:bg-hover-glass"
              >
                + {token}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <AlignField
          id={`align-${block.id}`}
          value={block.align}
          onChange={(v) => onChange({ align: v } as Partial<Block>)}
        />
        <ColorField
          id={`color-${block.id}`}
          label={t("settingsEmailTpl.color")}
          value={block.color}
          onChange={(v) => onChange({ color: v } as Partial<Block>)}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor={`size-${block.id}`}>
            {t("settingsEmailTpl.sizePx", { n: block.fontSize })}
          </Label>
          <input
            id={`size-${block.id}`}
            type="range"
            min={11}
            max={32}
            value={block.fontSize}
            onChange={(e) =>
              onChange({ fontSize: Number(e.target.value) } as Partial<Block>)
            }
            className="w-full accent-neon"
          />
        </div>
        <PaddingField
          id={`tpad-${block.id}`}
          value={block.paddingY ?? 6}
          onChange={(v) => onChange({ paddingY: v } as Partial<Block>)}
        />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={block.bold}
          onChange={(e) =>
            onChange({ bold: e.target.checked } as Partial<Block>)
          }
          className="h-4 w-4 rounded border-glass accent-neon"
        />
        {t("settingsEmailTpl.bold")}
      </label>
    </>
  );
}

function ImageUploadControls({
  accountId,
  idPrefix,
  value,
  onChange,
}: {
  accountId: string;
  idPrefix: string;
  value: string;
  onChange: (url: string) => void;
}) {
  const t = useT();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [media, setMedia] = useState<MediaItem[]>([]);
  const [loadingMedia, setLoadingMedia] = useState(false);

  async function upload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch(
        `/api/backend/api/v1/accounts/${accountId}/uploads/email_asset`,
        { method: "POST", body },
      );
      const json = (await res.json()) as { url?: string; message?: string };
      if (!res.ok || !json.url) {
        throw new Error(json.message ?? t("settingsEmailTpl.imageUploadFailed"));
      }
      onChange(json.url);
    } catch (err) {
      setError(
        (err as { message?: string })?.message ??
          t("settingsEmailTpl.uploadFailed"),
      );
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function toggleMediaPicker() {
    if (pickerOpen) {
      setPickerOpen(false);
      return;
    }
    setPickerOpen(true);
    setLoadingMedia(true);
    try {
      const items = await apiFetch<MediaItem[]>(
        `/api/v1/accounts/${accountId}/media?kind=image`,
      );
      setMedia(Array.isArray(items) ? items : []);
    } catch {
      setMedia([]);
    } finally {
      setLoadingMedia(false);
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          onChange={upload}
          className="hidden"
          aria-label={t("settingsEmailTpl.uploadImage")}
        />
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() => fileRef.current?.click()}
          loading={uploading}
        >
          <Upload className="h-4 w-4" aria-hidden />
          {t("settingsEmailTpl.uploadImage")}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => void toggleMediaPicker()}
        >
          <FolderOpen className="h-4 w-4" aria-hidden />
          {t("settingsEmailTpl.fromMediaLibrary")}
        </Button>
        {value ? (
          <span className="text-xs text-success">
            {t("settingsEmailTpl.imageLoaded")}
          </span>
        ) : null}
      </div>
      {error ? (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}

      {pickerOpen ? (
        <div className="rounded-md border border-glass bg-surface-1 p-2">
          {loadingMedia ? (
            <p className="text-xs text-fg-muted">{t("common.loading")}</p>
          ) : media.length === 0 ? (
            <p className="text-xs text-fg-muted">
              {t("settingsEmailTpl.mediaEmpty")}
            </p>
          ) : (
            <div className="grid max-h-40 grid-cols-4 gap-2 overflow-auto">
              {media.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    onChange(item.url);
                    setPickerOpen(false);
                  }}
                  className="overflow-hidden rounded-sm border border-glass bg-surface-2 hover:border-neon"
                  title={item.filename}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={item.url}
                    alt={item.filename}
                    className="h-14 w-full object-cover"
                  />
                </button>
              ))}
            </div>
          )}
        </div>
      ) : null}

      <div className="space-y-1.5">
        <Label htmlFor={`${idPrefix}-src`}>{t("settingsEmailTpl.orPasteUrl")}</Label>
        <Input
          id={`${idPrefix}-src`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="https://…"
        />
      </div>
    </>
  );
}

function ImageFields({
  accountId,
  block,
  onChange,
}: {
  accountId: string;
  block: ImageBlock;
  onChange: (patch: Partial<Block>) => void;
}) {
  const t = useT();
  return (
    <>
      <ImageUploadControls
        accountId={accountId}
        idPrefix={`img-${block.id}`}
        value={block.src}
        onChange={(src) => onChange({ src } as Partial<Block>)}
      />
      <div className="space-y-1.5">
        <Label htmlFor={`alt-${block.id}`}>{t("settingsEmailTpl.altText")}</Label>
        <Input
          id={`alt-${block.id}`}
          value={block.alt}
          onChange={(e) => onChange({ alt: e.target.value } as Partial<Block>)}
        />
        <p className="text-xs text-fg-muted">
          {t("settingsEmailTpl.altTextHint")}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor={`w-${block.id}`}>
            {t("settingsEmailTpl.widthPct", { n: block.widthPct })}
          </Label>
          <input
            id={`w-${block.id}`}
            type="range"
            min={10}
            max={100}
            step={5}
            value={block.widthPct}
            onChange={(e) =>
              onChange({ widthPct: Number(e.target.value) } as Partial<Block>)
            }
            className="w-full accent-neon"
          />
        </div>
        <PaddingField
          id={`ipad-${block.id}`}
          value={block.paddingY ?? 8}
          onChange={(v) => onChange({ paddingY: v } as Partial<Block>)}
        />
      </div>
      <AlignField
        id={`ialign-${block.id}`}
        value={block.align}
        onChange={(v) => onChange({ align: v } as Partial<Block>)}
      />
      <div className="space-y-1.5">
        <Label htmlFor={`href-${block.id}`}>
          {t("settingsEmailTpl.linkOptional")}
        </Label>
        <Input
          id={`href-${block.id}`}
          value={block.href}
          onChange={(e) => onChange({ href: e.target.value } as Partial<Block>)}
          placeholder="https://…"
        />
      </div>
    </>
  );
}

function ButtonFields({
  block,
  onChange,
}: {
  block: ButtonBlock;
  onChange: (patch: Partial<Block>) => void;
}) {
  const t = useT();
  return (
    <>
      <div className="space-y-1.5">
        <Label htmlFor={`label-${block.id}`}>
          {t("settingsEmailTpl.buttonText")}
        </Label>
        <Input
          id={`label-${block.id}`}
          value={block.label}
          onChange={(e) =>
            onChange({ label: e.target.value } as Partial<Block>)
          }
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`bhref-${block.id}`}>{t("settingsEmailTpl.link")}</Label>
        <Input
          id={`bhref-${block.id}`}
          value={block.href}
          onChange={(e) => onChange({ href: e.target.value } as Partial<Block>)}
          placeholder="https://…"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <ColorField
          id={`bbg-${block.id}`}
          label={t("settingsEmailTpl.background")}
          value={block.background}
          onChange={(v) => onChange({ background: v } as Partial<Block>)}
        />
        <ColorField
          id={`bfg-${block.id}`}
          label={t("settingsEmailTpl.blocks.text")}
          value={block.color}
          onChange={(v) => onChange({ color: v } as Partial<Block>)}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <AlignField
          id={`balign-${block.id}`}
          value={block.align}
          onChange={(v) => onChange({ align: v } as Partial<Block>)}
        />
        <PaddingField
          id={`bpad-${block.id}`}
          value={block.paddingY ?? 8}
          onChange={(v) => onChange({ paddingY: v } as Partial<Block>)}
        />
      </div>
    </>
  );
}

function ColumnsFields({
  accountId,
  block,
  onChange,
}: {
  accountId: string;
  block: ColumnsBlock;
  onChange: (patch: Partial<Block>) => void;
}) {
  const t = useT();
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-2 rounded-sm border border-glass p-2">
          <p className="text-xs font-semibold text-fg">
            {t("settingsEmailTpl.columnLeft")}
          </p>
          <Input
            aria-label={t("settingsEmailTpl.columnLeftTitle")}
            value={block.leftTitle}
            onChange={(e) =>
              onChange({ leftTitle: e.target.value } as Partial<Block>)
            }
            placeholder={t("settingsEmailTpl.headerTitle")}
          />
          <Textarea
            aria-label={t("settingsEmailTpl.columnLeftText")}
            rows={2}
            value={block.leftText}
            onChange={(e) =>
              onChange({ leftText: e.target.value } as Partial<Block>)
            }
          />
          <ImageUploadControls
            accountId={accountId}
            idPrefix={`col-l-${block.id}`}
            value={block.leftImage}
            onChange={(url) => onChange({ leftImage: url } as Partial<Block>)}
          />
        </div>
        <div className="space-y-2 rounded-sm border border-glass p-2">
          <p className="text-xs font-semibold text-fg">
            {t("settingsEmailTpl.columnRight")}
          </p>
          <Input
            aria-label={t("settingsEmailTpl.columnRightTitle")}
            value={block.rightTitle}
            onChange={(e) =>
              onChange({ rightTitle: e.target.value } as Partial<Block>)
            }
            placeholder={t("settingsEmailTpl.headerTitle")}
          />
          <Textarea
            aria-label={t("settingsEmailTpl.columnRightText")}
            rows={2}
            value={block.rightText}
            onChange={(e) =>
              onChange({ rightText: e.target.value } as Partial<Block>)
            }
          />
          <ImageUploadControls
            accountId={accountId}
            idPrefix={`col-r-${block.id}`}
            value={block.rightImage}
            onChange={(url) => onChange({ rightImage: url } as Partial<Block>)}
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <ColorField
          id={`col-color-${block.id}`}
          label={t("settingsEmailTpl.color")}
          value={block.textColor}
          onChange={(v) => onChange({ textColor: v } as Partial<Block>)}
        />
        <PaddingField
          id={`col-pad-${block.id}`}
          value={block.paddingY ?? 10}
          onChange={(v) => onChange({ paddingY: v } as Partial<Block>)}
        />
      </div>
    </div>
  );
}

function SocialFields({
  block,
  onChange,
}: {
  block: SocialBlock;
  onChange: (patch: Partial<Block>) => void;
}) {
  const t = useT();

  function updateLink(id: string, patch: { label?: string; url?: string }) {
    onChange({
      links: block.links.map((l) => (l.id === id ? { ...l, ...patch } : l)),
    } as Partial<Block>);
  }

  function addLink() {
    onChange({
      links: [...block.links, { id: newId(), label: "", url: "https://" }],
    } as Partial<Block>);
  }

  function removeLink(id: string) {
    onChange({
      links: block.links.filter((l) => l.id !== id),
    } as Partial<Block>);
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {block.links.map((link) => (
          <div key={link.id} className="flex items-center gap-1.5">
            <Input
              aria-label={t("settingsEmailTpl.socialLabel")}
              value={link.label}
              onChange={(e) => updateLink(link.id, { label: e.target.value })}
              placeholder="Instagram"
              className="w-28 shrink-0"
            />
            <Input
              aria-label={t("settingsEmailTpl.link")}
              value={link.url}
              onChange={(e) => updateLink(link.id, { url: e.target.value })}
              placeholder="https://…"
            />
            <IconButton
              label={t("common.remove")}
              onClick={() => removeLink(link.id)}
            >
              <Trash2 className="h-3.5 w-3.5 text-danger" aria-hidden />
            </IconButton>
          </div>
        ))}
        <Button type="button" size="sm" variant="ghost" onClick={addLink}>
          <Plus className="h-3.5 w-3.5" aria-hidden />
          {t("settingsEmailTpl.addSocialLink")}
        </Button>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <AlignField
          id={`soc-align-${block.id}`}
          value={block.align}
          onChange={(v) => onChange({ align: v } as Partial<Block>)}
        />
        <ColorField
          id={`soc-color-${block.id}`}
          label={t("settingsEmailTpl.color")}
          value={block.color}
          onChange={(v) => onChange({ color: v } as Partial<Block>)}
        />
        <PaddingField
          id={`soc-pad-${block.id}`}
          value={block.paddingY ?? 10}
          onChange={(v) => onChange({ paddingY: v } as Partial<Block>)}
        />
      </div>
    </div>
  );
}

function DividerFields({
  block,
  onChange,
}: {
  block: DividerBlock;
  onChange: (patch: Partial<Block>) => void;
}) {
  const t = useT();
  return (
    <div className="grid grid-cols-2 gap-3">
      <ColorField
        id={`divider-${block.id}`}
        label={t("settingsEmailTpl.color")}
        value={block.color}
        onChange={(v) => onChange({ color: v } as Partial<Block>)}
      />
      <PaddingField
        id={`dpad-${block.id}`}
        value={block.paddingY ?? 12}
        onChange={(v) => onChange({ paddingY: v } as Partial<Block>)}
      />
    </div>
  );
}

function SpacerFields({
  block,
  onChange,
}: {
  block: SpacerBlock;
  onChange: (patch: Partial<Block>) => void;
}) {
  const t = useT();
  return (
    <div className="space-y-1.5">
      <Label htmlFor={`h-${block.id}`}>
        {t("settingsEmailTpl.heightPx", { n: block.height })}
      </Label>
      <input
        id={`h-${block.id}`}
        type="range"
        min={8}
        max={80}
        step={4}
        value={block.height}
        onChange={(e) =>
          onChange({ height: Number(e.target.value) } as Partial<Block>)
        }
        className="w-full accent-neon"
      />
    </div>
  );
}

function SignatureFields({
  block,
  onChange,
}: {
  block: SignatureBlock;
  onChange: (patch: Partial<Block>) => void;
}) {
  const t = useT();
  return (
    <div className="space-y-2">
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={block.showAgent}
          onChange={(e) =>
            onChange({ showAgent: e.target.checked } as Partial<Block>)
          }
          className="h-4 w-4 rounded border-glass accent-neon"
        />
        {t("settingsEmailTpl.replierSignature")}
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={block.showMailbox}
          onChange={(e) =>
            onChange({ showMailbox: e.target.checked } as Partial<Block>)
          }
          className="h-4 w-4 rounded border-glass accent-neon"
        />
        {t("settingsEmailTpl.mailboxSignature")}
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={Boolean(block.showOrg)}
          onChange={(e) =>
            onChange({ showOrg: e.target.checked } as Partial<Block>)
          }
          className="h-4 w-4 rounded border-glass accent-neon"
        />
        {t("settingsEmailTpl.orgSignatureVar")}
      </label>
    </div>
  );
}

function PaddingField({
  id,
  value,
  onChange,
}: {
  id: string;
  value: number;
  onChange: (v: number) => void;
}) {
  const t = useT();
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{t("settingsEmailTpl.marginPx", { n: value })}</Label>
      <input
        id={id}
        type="range"
        min={0}
        max={40}
        step={2}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-neon"
      />
    </div>
  );
}

function AlignField({
  id,
  value,
  onChange,
}: {
  id: string;
  value: Align;
  onChange: (v: Align) => void;
}) {
  const t = useT();
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{t("settingsEmailTpl.alignment")}</Label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value as Align)}
        className={cn(selectClassName("sm"), "w-full")}
      >
        <option value="left">{t("settingsEmailTpl.left")}</option>
        <option value="center">{t("settingsEmailTpl.center")}</option>
        <option value="right">{t("settingsEmailTpl.right")}</option>
      </select>
    </div>
  );
}

function ColorField({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <input
        id={id}
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 w-full cursor-pointer rounded-control border border-glass bg-field"
      />
    </div>
  );
}
