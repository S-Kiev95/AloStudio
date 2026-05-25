import { PublishingView } from "@/components/instagram/publishing-view";

export default async function InstagramPostsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <PublishingView accountId={accountId} />;
}
