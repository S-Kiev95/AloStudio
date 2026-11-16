"use client";

import {
  ArrowDown,
  ArrowUp,
  Image as ImageIcon,
  Minus,
  MousePointerClick,
  PenLine,
  Trash2,
  Type,
  Upload,
} from "lucide-react";
import { type ChangeEvent, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  type Align,
  type Block,
  type BlockDocument,
  type ButtonBlock,
  type ImageBlock,
  type SignatureBlock,
  type SpacerBlock,
  type TextBlock,
  blankBlock,
  renderBlocks,
} from "@/lib/inboxes/email-blocks";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

const ADDABLE: { type: Block["type"]; icon: typeof Type }[] = [
  { type: "text", icon: Type },
  { type: "image", icon: ImageIcon },
  { type: "button", icon: MousePointerClick },
  { type: "divider", icon: Minus },
  { type: "spacer", icon: ArrowDown },
  { type: "signature", icon: PenLine },
];

const BLOCK_NAMES: Record<Block["type"], MessageKey> = {
  text: "settingsEmailTpl.blocks.text",
  image: "settingsEmailTpl.blocks.image",
  button: "settingsEmailTpl.blocks.button",
  divider: "settingsEmailTpl.blocks.divider",
  spacer: "settingsEmailTpl.blocks.spacer",
  content: "settingsEmailTpl.blocks.content",
  signature: "settingsEmailTpl.blocks.signature",
};

/**
 * A vertical stack of blocks, and a live preview of the email it makes.
 *
 * Not a canvas: Outlook renders with Word's engine, so free XY placement
 * produces layouts the medium cannot express. Rows stack, and what the
 * preview shows is what `renderBlocks` will emit.
 */
export function BlockEditor({
  accountId,
  doc,
  onChange,
}: {
  accountId: string;
  doc: BlockDocument;
  onChange: (next: BlockDocument) => void;
}) {
  const t = useT();
  const [selected, setSelected] = useState<string | null>(null);

  function setBlocks(blocks: Block[]) {
    onChange({ ...doc, blocks });
  }

  function add(type: Block["type"]) {
    const block = blankBlock(type);
    setBlocks([...doc.blocks, block]);
    setSelected(block.id);
  }

  function update(id: string, patch: Partial<Block>) {
    setBlocks(
      doc.blocks.map((b) => (b.id === id ? ({ ...b, ...patch } as Block) : b)),
    );
  }

  function remove(id: string) {
    setBlocks(doc.blocks.filter((b) => b.id !== id));
    setSelected(null);
  }

  function move(id: string, delta: -1 | 1) {
    const i = doc.blocks.findIndex((b) => b.id === id);
    const j = i + delta;
    if (i < 0 || j < 0 || j >= doc.blocks.length) return;
    const next = [...doc.blocks];
    [next[i], next[j]] = [next[j], next[i]];
    setBlocks(next);
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {/* ---- the stack ---- */}
      <div className="space-y-3">
        <PageControls
          page={doc.page}
          onChange={(page) => onChange({ ...doc, page })}
        />

        <ul className="space-y-2">
          {doc.blocks.map((block, i) => (
            <li key={block.id}>
              <div
                className={cn(
                  "rounded-md border",
                  selected === block.id
                    ? "border-neon bg-focused/40"
                    : "border-glass bg-field",
                )}
              >
                <div className="flex items-center gap-1 px-2 py-1.5">
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
                    label={t("settingsEmailTpl.moveUp", { block: t(BLOCK_NAMES[block.type]) })}
                    onClick={() => move(block.id, -1)}
                    disabled={i === 0}
                  >
                    <ArrowUp className="h-3.5 w-3.5" aria-hidden />
                  </IconButton>
                  <IconButton
                    label={t("settingsEmailTpl.moveDown", { block: t(BLOCK_NAMES[block.type]) })}
                    onClick={() => move(block.id, 1)}
                    disabled={i === doc.blocks.length - 1}
                  >
                    <ArrowDown className="h-3.5 w-3.5" aria-hidden />
                  </IconButton>
                  <IconButton
                    label={t("settingsEmailTpl.removeBlock", { block: t(BLOCK_NAMES[block.type]) })}
                    onClick={() => remove(block.id)}
                  >
                    <Trash2 className="h-3.5 w-3.5 text-danger" aria-hidden />
                  </IconButton>
                </div>

                {selected === block.id ? (
                  <div className="space-y-3 border-t border-glass p-3">
                    <BlockFields
                      accountId={accountId}
                      block={block}
                      onChange={(patch) => update(block.id, patch)}
                    />
                  </div>
                ) : null}
              </div>
            </li>
          ))}
        </ul>

        <div className="flex flex-wrap gap-2">
          {ADDABLE.map(({ type, icon: Icon }) => (
            <Button
              key={type}
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => add(type)}
            >
              <Icon className="h-4 w-4" aria-hidden />
              {t(BLOCK_NAMES[type])}
            </Button>
          ))}
        </div>

        {!doc.blocks.some((b) => b.type === "content") ? (
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

      {/* ---- what it becomes ---- */}
      <div className="space-y-1.5">
        <p className="text-xs font-medium text-fg-muted">{t("settingsEmailTpl.preview")}</p>
        <div
          className="overflow-auto rounded-md border border-glass bg-white"
          // The preview is the generator's own output, so the two can
          // never drift.
          dangerouslySetInnerHTML={{
            __html: renderBlocks(doc).replace(
              /\{\{contenido\}\}/g,
              "<em>Acá va el mensaje que escriba el agente.</em>",
            ),
          }}
        />
        <p className="text-xs text-fg-muted">
          {t("settingsEmailTpl.previewNote")}
        </p>
      </div>
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
  page,
  onChange,
}: {
  page: BlockDocument["page"];
  onChange: (p: BlockDocument["page"]) => void;
}) {
  const t = useT();
  return (
    <div className="grid grid-cols-2 gap-3 rounded-md border border-glass p-3">
      <ColorField
        id="page-bg"
        label={t("settingsEmailTpl.background")}
        value={page.pageColor}
        onChange={(v) => onChange({ ...page, pageColor: v })}
      />
      <ColorField
        id="body-bg"
        label={t("settingsEmailTpl.card")}
        value={page.bodyColor}
        onChange={(v) => onChange({ ...page, bodyColor: v })}
      />
      <div className="col-span-2 space-y-1.5">
        <Label htmlFor="page-width">{t("settingsEmailTpl.widthPx", { n: page.width })}</Label>
        <input
          id="page-width"
          type="range"
          min={480}
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
  onChange,
}: {
  accountId: string;
  block: Block;
  onChange: (patch: Partial<Block>) => void;
}) {
  const t = useT();
  switch (block.type) {
    case "text":
      return <TextFields block={block} onChange={onChange} />;
    case "image":
      return (
        <ImageFields accountId={accountId} block={block} onChange={onChange} />
      );
    case "button":
      return <ButtonFields block={block} onChange={onChange} />;
    case "spacer":
      return <SpacerFields block={block} onChange={onChange} />;
    case "signature":
      return <SignatureFields block={block} onChange={onChange} />;
    case "divider":
      return (
        <ColorField
          id={`divider-${block.id}`}
          label={t("settingsEmailTpl.color")}
          value={block.color}
          onChange={(v) => onChange({ color: v } as Partial<Block>)}
        />
      );
    case "content":
      return (
        <p className="text-xs text-fg-muted">
          {t("settingsEmailTpl.contentBlockHint")}
        </p>
      );
  }
}

function TextFields({
  block,
  onChange,
}: {
  block: TextBlock;
  onChange: (patch: Partial<Block>) => void;
}) {
  const t = useT();
  return (
    <>
      <div className="space-y-1.5">
        <Label htmlFor={`text-${block.id}`}>{t("settingsEmailTpl.blocks.text")}</Label>
        <Textarea
          id={`text-${block.id}`}
          rows={3}
          value={block.text}
          onChange={(e) => onChange({ text: e.target.value } as Partial<Block>)}
        />
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
      <div className="space-y-1.5">
        <Label htmlFor={`size-${block.id}`}>{t("settingsEmailTpl.sizePx", { n: block.fontSize })}</Label>
        <input
          id={`size-${block.id}`}
          type="range"
          min={12}
          max={32}
          value={block.fontSize}
          onChange={(e) =>
            onChange({ fontSize: Number(e.target.value) } as Partial<Block>)
          }
          className="w-full accent-neon"
        />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={block.bold}
          onChange={(e) => onChange({ bold: e.target.checked } as Partial<Block>)}
          className="h-4 w-4 rounded border-glass accent-neon"
        />
        {t("settingsEmailTpl.bold")}
      </label>
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
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null as string | null);

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
      onChange({ src: json.url } as Partial<Block>);
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("settingsEmailTpl.uploadFailed"));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
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
        {block.src ? (
          <span className="text-xs text-success">{t("settingsEmailTpl.imageLoaded")}</span>
        ) : null}
      </div>
      {error ? (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}

      <div className="space-y-1.5">
        <Label htmlFor={`src-${block.id}`}>{t("settingsEmailTpl.orPasteUrl")}</Label>
        <Input
          id={`src-${block.id}`}
          value={block.src}
          onChange={(e) => onChange({ src: e.target.value } as Partial<Block>)}
          placeholder="https://…"
        />
      </div>
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
      <div className="space-y-1.5">
        <Label htmlFor={`w-${block.id}`}>{t("settingsEmailTpl.widthPct", { n: block.widthPct })}</Label>
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
      <AlignField
        id={`ialign-${block.id}`}
        value={block.align}
        onChange={(v) => onChange({ align: v } as Partial<Block>)}
      />
      <div className="space-y-1.5">
        <Label htmlFor={`href-${block.id}`}>{t("settingsEmailTpl.linkOptional")}</Label>
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
        <Label htmlFor={`label-${block.id}`}>{t("settingsEmailTpl.buttonText")}</Label>
        <Input
          id={`label-${block.id}`}
          value={block.label}
          onChange={(e) => onChange({ label: e.target.value } as Partial<Block>)}
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
      <AlignField
        id={`balign-${block.id}`}
        value={block.align}
        onChange={(v) => onChange({ align: v } as Partial<Block>)}
      />
    </>
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
      <Label htmlFor={`h-${block.id}`}>{t("settingsEmailTpl.heightPx", { n: block.height })}</Label>
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
