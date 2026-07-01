import { apiFetch } from "./fetcher";

/** The attachment ref sent with a message (`{file_type, external_url}`). */
export type UploadedAttachment = { external_url: string; file_type: string };

type PresignResponse = {
  key: string;
  upload_url: string;
  file_url: string;
  expires_in: number;
};

/** Map a browser MIME type to the backend's attachment `file_type` enum. */
export function mimeToFileType(mime: string | undefined): string {
  if (!mime) return "file";
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("audio/")) return "audio";
  if (mime.startsWith("video/")) return "video";
  return "file";
}

/**
 * Two-step direct upload: presign via our API, then PUT the bytes straight
 * to the object store (they never transit our backend). Returns the
 * attachment ref to include when sending the message.
 */
export async function uploadAttachment(
  accountId: string,
  file: File,
): Promise<UploadedAttachment> {
  const contentType = file.type || "application/octet-stream";
  const presign = await apiFetch<PresignResponse>(
    `/api/v1/accounts/${accountId}/uploads`,
    {
      method: "POST",
      body: JSON.stringify({ filename: file.name, content_type: contentType }),
    },
  );

  const res = await fetch(presign.upload_url, {
    method: "PUT",
    body: file,
    headers: { "Content-Type": contentType },
  });
  if (!res.ok) {
    throw new Error(`upload failed (${res.status})`);
  }

  return { external_url: presign.file_url, file_type: mimeToFileType(file.type) };
}
