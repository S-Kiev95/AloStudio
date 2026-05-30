import { InstagramConnection } from "@/components/instagram/instagram-connection";

export default async function InstagramPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <InstagramConnection accountId={accountId} />;
}
