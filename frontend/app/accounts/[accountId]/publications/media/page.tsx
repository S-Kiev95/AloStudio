import { MediaLibraryView } from "@/components/publications/media-library-view";

export default async function PublicationsMediaPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <MediaLibraryView accountId={accountId} />;
}
