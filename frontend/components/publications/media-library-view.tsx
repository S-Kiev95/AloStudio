"use client";

import { Film, ImageIcon, Images, Plus, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { SegmentedControl } from "@/components/ui/segmented-control";
import {
  formatBytes,
  type MediaAsset,
  type MediaKind,
  useDeleteMedia,
  useInfiniteMediaAssets,
  useUploadMedia,
  validateMediaFile,
} from "@/lib/api/media";
import { useIsAccountAdmin } from "@/lib/api/profile";
import {
  type ParsedPublicationError,
  parsePublicationError,
} from "@/lib/api/publications";
import { cn } from "@/lib/utils";

import { PublicationErrorAlert } from "./publication-error-alert";

const KIND_FILTERS: { value: MediaKind | undefined; label: string }[] = [
  { value: undefined, label: "Todo" },
  { value: "image", label: "Imágenes" },
  { value: "video", label: "Videos" },
];

export function MediaLibraryView({ accountId }: { accountId: string }) {
  const isAdmin = useIsAccountAdmin(accountId);
  const [kindFilter, setKindFilter] = useState<MediaKind | undefined>(undefined);
  const [dragging, setDragging] = useState(false);
  const [uploadingCount, setUploadingCount] = useState(0);
  const [error, setError] = useState<ParsedPublicationError | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const mediaQuery = useInfiniteMediaAssets(accountId, { kind: kindFilter });
  const uploadMutation = useUploadMedia(accountId);
  const deleteMutation = useDeleteMedia(accountId);

  const items: MediaAsset[] =
    mediaQuery.data?.pages.flatMap((page) => page) ?? [];
  const isUploading = uploadingCount > 0 || uploadMutation.isPending;

  async function handleFiles(fileList: FileList | File[]) {
    const files = Array.from(fileList);
    if (files.length === 0) return;

    setError(null);
    for (const file of files) {
      const validationMessage = validateMediaFile(file);
      if (validationMessage) {
        setError({ message: validationMessage, errors: [] });
        return;
      }
    }

    setUploadingCount((c) => c + files.length);
    try {
      for (const file of files) {
        await uploadMutation.mutateAsync(file);
      }
    } catch (err) {
      setError(parsePublicationError(err, "No se pudo subir el archivo."));
    } finally {
      setUploadingCount((c) => Math.max(0, c - files.length));
    }
  }

  async function handleDelete(asset: MediaAsset) {
    const label = asset.filename || `archivo #${asset.id}`;
    if (!window.confirm(`¿Borrar "${label}" de la biblioteca?`)) return;
    setError(null);
    try {
      await deleteMutation.mutateAsync(asset.id);
    } catch (err) {
      setError(parsePublicationError(err, "No se pudo borrar el archivo."));
    }
  }

  return (
    <div
      className="space-y-4"
      onDragOver={(e) => {
        e.preventDefault();
        if (!dragging) setDragging(true);
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setDragging(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (e.dataTransfer.files?.length) {
          void handleFiles(e.dataTransfer.files);
        }
      }}
    >
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept="image/*,video/*"
        aria-label="Seleccionar archivos para subir"
        className="hidden"
        tabIndex={-1}
        onChange={(e) => {
          const picked = e.target.files;
          if (picked && picked.length > 0) {
            void handleFiles(picked);
          }
          e.target.value = "";
        }}
      />

      <PageHeader
        title="Medios"
        actions={
          <Button
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
          >
            <Upload className="h-4 w-4" aria-hidden />
            {isUploading ? "Subiendo…" : "Subir"}
          </Button>
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <SegmentedControl
          ariaLabel="Filtrar tipo de medio"
          size="sm"
          value={kindFilter}
          onValueChange={setKindFilter}
          options={KIND_FILTERS}
        />
        {isUploading ? (
          <p role="status" className="text-xs font-medium text-lit">
            Subiendo…
          </p>
        ) : null}
      </div>

      <PublicationErrorAlert error={error} onDismiss={() => setError(null)} />

      <div
        data-testid="media-dropzone"
        className={cn(
          "min-h-[380px] rounded-md border bg-surface p-5 transition-colors",
          dragging
            ? "border-neon bg-focused/40"
            : "border-glass",
        )}
      >
        {mediaQuery.isLoading ? (
          <p className="py-16 text-center text-sm text-fg-muted">
            Cargando medios…
          </p>
        ) : mediaQuery.isError ? (
          <p role="alert" className="py-16 text-center text-sm text-danger">
            No se pudo cargar la biblioteca de medios.
          </p>
        ) : items.length === 0 ? (
          <div className="flex min-h-[320px] flex-col items-center justify-center px-4 py-12 text-center">
            <div className="relative mb-5 flex items-center justify-center">
              <span className="-mr-2 -rotate-6 grid h-12 w-12 place-items-center rounded-control border border-glass bg-surface-2 text-fg-muted">
                <Film className="h-5 w-5" aria-hidden />
              </span>
              <span className="z-10 grid h-16 w-16 place-items-center rounded-panel border border-glass bg-surface-2 text-fg">
                <Images className="h-7 w-7" aria-hidden />
              </span>
            </div>
            <h2 className="text-base font-medium text-fg">
              {kindFilter
                ? "No hay archivos para este filtro"
                : "Todavía no tenés medios"}
            </h2>
            <p className="mt-1.5 max-w-md text-xs text-fg-muted">
              Seleccioná o arrastrá imágenes (máximo 30 MB) o videos (máximo
              200 MB) a esta pantalla.
            </p>
            <div className="mt-5">
              <Button
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
              >
                <Plus className="h-4 w-4" aria-hidden />
                {isUploading ? "Subiendo…" : "Subir"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-5">
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
              {items.map((asset) => {
                const label = asset.filename || `Archivo #${asset.id}`;
                return (
                  <li
                    key={asset.id}
                    className="group flex flex-col overflow-hidden rounded-md border border-glass bg-surface-2"
                  >
                    <div className="relative aspect-square w-full overflow-hidden bg-field">
                      {asset.kind === "video" ? (
                        <>
                          <video
                            src={asset.url}
                            preload="metadata"
                            muted
                            className="h-full w-full object-cover"
                          />
                          <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-sm bg-backdrop/80 px-1.5 py-0.5 text-[10px] font-medium uppercase text-fg">
                            <Film className="h-3 w-3" aria-hidden />
                            Video
                          </span>
                        </>
                      ) : (
                        <>
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={asset.url}
                            alt={label}
                            loading="lazy"
                            className="h-full w-full object-cover"
                          />
                          <span className="sr-only">
                            <ImageIcon className="h-3 w-3" aria-hidden />
                            Imagen
                          </span>
                        </>
                      )}
                    </div>
                    <div className="flex items-center justify-between gap-2 px-3 py-2">
                      <div className="min-w-0 flex-1">
                        <p
                          className="truncate text-xs font-medium text-fg"
                          title={label}
                        >
                          {label}
                        </p>
                        <p className="font-numeric text-[11px] tabular-nums text-fg-muted">
                          {formatBytes(asset.size_bytes)}
                        </p>
                      </div>
                      {isAdmin ? (
                        <button
                          type="button"
                          aria-label={`Borrar ${label}`}
                          title="Borrar"
                          disabled={deleteMutation.isPending}
                          onClick={() => handleDelete(asset)}
                          className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass hover:text-danger disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                        >
                          <Trash2 className="h-3.5 w-3.5" aria-hidden />
                        </button>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ul>

            {mediaQuery.hasNextPage ? (
              <div className="flex justify-center pt-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  loading={mediaQuery.isFetchingNextPage}
                  onClick={() => mediaQuery.fetchNextPage()}
                >
                  Cargar más
                </Button>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
