import { ConfirmClient } from "./confirm-client";

/**
 * Email confirmation landing. Reads the token server-side and lets the
 * client component consume it (auto sign-in on success).
 */
export default async function ConfirmPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const raw = sp.confirmation_token ?? sp.token;
  const token = Array.isArray(raw) ? raw[0] : raw;

  return (
    <div className="space-y-6">
      <div className="neon-sign">
        <h1 className="text-[28px] leading-[1.2]">Confirmar email</h1>
      </div>
      <ConfirmClient token={token ?? null} />
    </div>
  );
}
