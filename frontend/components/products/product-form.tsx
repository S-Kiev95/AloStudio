"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Product, ProductInput } from "@/lib/api/products";

export function ProductForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  initial?: Product;
  submitting?: boolean;
  onSubmit: (input: ProductInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [sku, setSku] = useState(initial?.sku ?? "");
  const [price, setPrice] = useState(
    initial?.price != null ? String(initial.price) : "",
  );
  const [currency, setCurrency] = useState(initial?.currency ?? "");
  const [url, setUrl] = useState(initial?.url ?? "");
  const [imageUrl, setImageUrl] = useState(initial?.image_url ?? "");
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (!name.trim()) return setError("El nombre es obligatorio.");
    let priceValue: number | null = null;
    if (price.trim()) {
      const n = Number(price);
      if (Number.isNaN(n) || n < 0) return setError("El precio no es válido.");
      priceValue = n;
    }

    const input: ProductInput = {
      name: name.trim(),
      description: description.trim() || null,
      sku: sku.trim() || null,
      price: priceValue,
      currency: currency.trim() || null,
      url: url.trim() || null,
      image_url: imageUrl.trim() || null,
      enabled,
    };

    try {
      await onSubmit(input);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo guardar el producto.",
      );
    }
  }

  return (
    <div className="space-y-4">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="space-y-1.5">
        <Label htmlFor="p-name" required>
          Nombre
        </Label>
        <Input
          id="p-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={255}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="p-desc">Descripción</Label>
        <Textarea
          id="p-desc"
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="p-price">Precio</Label>
          <Input
            id="p-price"
            type="number"
            min={0}
            step="0.01"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="p-currency">Moneda</Label>
          <Input
            id="p-currency"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            placeholder="UYU"
            maxLength={8}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="p-sku">SKU</Label>
          <Input id="p-sku" value={sku} onChange={(e) => setSku(e.target.value)} />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="p-url">URL del producto</Label>
        <Input
          id="p-url"
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://…"
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="p-img">URL de imagen</Label>
        <Input
          id="p-img"
          type="url"
          value={imageUrl}
          onChange={(e) => setImageUrl(e.target.value)}
          placeholder="https://…"
        />
      </div>

      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
        Activo (visible en el catálogo)
      </label>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? "Guardar cambios" : "Crear producto"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
