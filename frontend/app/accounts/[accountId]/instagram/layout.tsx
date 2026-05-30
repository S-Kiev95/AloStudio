import { InstagramTabs } from "@/components/instagram/instagram-tabs";

export default async function InstagramLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return (
    <div className="mx-auto max-w-3xl">
      <InstagramTabs accountId={accountId} />
      {children}
    </div>
  );
}
