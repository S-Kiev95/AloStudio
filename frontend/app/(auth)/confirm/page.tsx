import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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
    <Card>
      <CardHeader>
        <CardTitle>Confirmar email</CardTitle>
      </CardHeader>
      <CardContent>
        <ConfirmClient token={token ?? null} />
      </CardContent>
    </Card>
  );
}
