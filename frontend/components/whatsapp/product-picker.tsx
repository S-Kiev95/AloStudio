"use client";

import { Search, Send, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  formatPrice,
  useCatalogProducts,
  useSendProducts,
} from "@/lib/api/whatsapp-catalog";
import { cn } from "@/lib/utils";

const MAX_ITEMS = 30;

/** Pick catalogue products and send them in the open WhatsApp chat: one goes
 *  as a product card, several as a list the contact can order from. */
export function ProductPicker({
  accountId,
  displayId,
  onClose,
}: {
  accountId: string;
  displayId: number;
  onClose: () => void;
}) {
  const productsQ = useCatalogProducts(accountId);
  const send = useSendProducts(accountId, displayId);
  const [selected, setSelected] = useState<number[]>([]);
  const [query, setQuery] = useState("");
  const [header, setHeader] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);

  const products = productsQ.data?.products ?? [];
  const q = query.trim().toLowerCase();
  const visible = q ? products.filter((p) => p.name.toLowerCase().includes(q)) : products;
  const many = selected.length > 1;

  function toggle(id: number) {
    setSelected((prev) =>
      prev.includes(id)
        ? prev.filter((x) => x !== id)
        : prev.length >= MAX_ITEMS
          ? prev
          : [...prev, id],
    );
  }

  async function submit() {
    setError(null);
    try {
      await send.mutateAsync({ productIds: selected, body, header: many ? header : undefined });
      onClose();
    } catch (err) {
      setError((err as Error).message || "No se pudieron mandar los productos.");
    }
  }

  return (
    <div
      role="region"
      aria-label="Mandar productos del catálogo"
      className="mb-3 space-y-3 rounded-lg border border-glass bg-surface-2 p-3"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-fg">Mandar productos del catálogo</span>
        <button
          type="button"
          aria-label="Cerrar selector de productos"
          onClick={onClose}
          className="rounded p-1 text-fg-muted hover:bg-hover-glass hover:text-fg"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>

      {productsQ.isLoading ? (
        <p className="text-xs text-fg-muted">Cargando productos…</p>
      ) : !productsQ.data?.catalog_id ? (
        <p className="text-xs text-fg-muted">
          La cuenta no tiene un catálogo de Meta conectado. Se conecta en{" "}
          <Link
            href={`/accounts/${accountId}/products`}
            className="text-lit underline-offset-2 hover:underline"
          >
            CRM → Productos
          </Link>
          .
        </p>
      ) : products.length === 0 ? (
        <p className="text-xs text-fg-muted">
          Todavía no hay productos aceptados por Meta en el catálogo.
        </p>
      ) : (
        <>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-muted"
              aria-hidden
            />
            <Input
              aria-label="Buscar producto"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar…"
              className="pl-8"
            />
          </div>
          <ul className="max-h-56 space-y-1 overflow-y-auto">
            {visible.map((p) => {
              const on = selected.includes(p.id);
              return (
                <li key={p.id}>
                  <label
                    className={cn(
                      "flex cursor-pointer items-center gap-2.5 rounded-md border px-2 py-1.5",
                      on ? "border-neon bg-focused" : "border-transparent hover:bg-hover-glass",
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => toggle(p.id)}
                      aria-label={p.name}
                    />
                    {p.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element -- product images live on any host
                      <img src={p.image_url} alt="" className="h-9 w-9 rounded object-cover" />
                    ) : null}
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-fg">{p.name}</span>
                      <span className="block text-xs text-fg-muted">
                        {formatPrice(p.price, p.currency)}
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
          {many ? (
            <Input
              aria-label="Título de la lista"
              value={header}
              maxLength={60}
              onChange={(e) => setHeader(e.target.value)}
              placeholder="Título de la lista (ej.: Cursos de marzo)"
            />
          ) : null}
          <Input
            aria-label="Mensaje"
            value={body}
            maxLength={1024}
            onChange={(e) => setBody(e.target.value)}
            placeholder={many ? "Mensaje (ej.: Elegí y mandanos tu pedido)" : "Mensaje (opcional)"}
          />
          {error ? (
            <p role="alert" className="text-xs text-danger">
              {error}
            </p>
          ) : null}
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-fg-muted">
              {selected.length === 0
                ? "Elegí uno o más (hasta 30)."
                : many
                  ? `${selected.length} productos: le llega una lista para armar un pedido.`
                  : "1 producto: le llega como tarjeta."}
            </span>
            <Button
              type="button"
              size="sm"
              loading={send.isPending}
              disabled={selected.length === 0}
              onClick={() => void submit()}
            >
              <Send className="h-3.5 w-3.5" aria-hidden />
              Enviar
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
