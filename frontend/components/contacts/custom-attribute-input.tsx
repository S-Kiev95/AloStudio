"use client";

import { Input } from "@/components/ui/input";
import type { CustomAttribute } from "@/lib/api/custom-attributes";
import { cn } from "@/lib/utils";

const selectClass =
  "h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/**
 * Typed input for one custom-attribute value, dispatching on the
 * attribute's ``display_type``. Used inside the contact form so each
 * defined attribute renders the right control instead of a raw text
 * field for everything.
 */
export function CustomAttributeInput({
  attribute,
  value,
  onChange,
}: {
  attribute: CustomAttribute;
  value: unknown;
  onChange: (next: unknown) => void;
}) {
  const id = `ca-${attribute.attribute_key}`;
  const type = attribute.attribute_display_type;

  if (type === "checkbox") {
    return (
      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          id={id}
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
        />
        {attribute.attribute_description ?? attribute.attribute_display_name}
      </label>
    );
  }

  if (type === "list") {
    const values = attribute.attribute_values ?? [];
    return (
      <select
        id={id}
        className={selectClass}
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
      >
        <option value="">Sin valor</option>
        {values.map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </select>
    );
  }

  if (type === "number" || type === "currency" || type === "percent") {
    return (
      <Input
        id={id}
        type="number"
        step={type === "currency" ? "0.01" : "any"}
        value={value === null || value === undefined ? "" : String(value)}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === "") {
            onChange(null);
            return;
          }
          const n = Number(raw);
          onChange(Number.isNaN(n) ? raw : n);
        }}
        placeholder={attribute.regex_cue ?? undefined}
      />
    );
  }

  if (type === "date") {
    return (
      <Input
        id={id}
        type="date"
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
      />
    );
  }

  if (type === "link") {
    return (
      <Input
        id={id}
        type="url"
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        placeholder={attribute.regex_cue ?? "https://…"}
      />
    );
  }

  // text — default.
  return (
    <Input
      id={id}
      type="text"
      value={(value as string) ?? ""}
      onChange={(e) => onChange(e.target.value || null)}
      placeholder={attribute.regex_cue ?? undefined}
      className={cn(
        attribute.regex_pattern ? "" : "",
      )}
    />
  );
}
