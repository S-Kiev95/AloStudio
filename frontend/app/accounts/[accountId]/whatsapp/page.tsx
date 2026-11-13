import { Suspense } from "react";

import { WhatsappSection } from "@/components/whatsapp/whatsapp-section";

export default async function WhatsappPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  // useSearchParams (which inbox) has to sit under a Suspense boundary.
  return (
    <Suspense>
      <WhatsappSection accountId={accountId} />
    </Suspense>
  );
}
