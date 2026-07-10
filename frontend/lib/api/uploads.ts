/** The attachment ref sent with a message (`{file_type, external_url}`). */
export type UploadedAttachment = { external_url: string; file_type: string };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/backend";

/** Map a browser MIME type to the backend's attachment `file_type` enum. */
export function mimeToFileType(mime: string | undefined): string {
  if (!mime) return "file";
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("audio/")) return "audio";
  if (mime.startsWith("video/")) return "video";
  return "file";
}

/**
 * Upload an attachment through our API (multipart POST → the backend stores
 * it in the object store). The browser can't reach the internal object store
 * directly, so the bytes transit our backend. Returns the attachment ref to
 * include when sending the message.
 */
export async function uploadAttachment(
  accountId: string,
  file: File,
): Promise<UploadedAttachment> {
  const form = new FormData();
  form.append("file", file, file.name);
  // No explicit Content-Type — the browser sets the multipart boundary. The
  // httpOnly auth cookie rides along same-origin; the BFF bridges it to the
  // devise headers the backend expects.
  const res = await fetch(
    `${API_BASE}/api/v1/accounts/${accountId}/uploads/blob`,
    { method: "POST", body: form },
  );
  if (!res.ok) {
    throw new Error(`upload failed (${res.status})`);
  }
  const data = (await res.json()) as { file_url: string };
  return { external_url: data.file_url, file_type: mimeToFileType(file.type) };
}
