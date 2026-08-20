import { Suspense } from "react";

import { InstagramConnection } from "@/components/instagram/instagram-connection";

export default async function InstagramPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  // The OAuth callback lands back here with the outcome in the query
  // string, and useSearchParams has to sit under a Suspense boundary.
  return (
    <Suspense>
      <InstagramConnection accountId={accountId} />
    </Suspense>
  );
}
