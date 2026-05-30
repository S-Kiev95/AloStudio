import { notFound } from "next/navigation";

import { fetchPortal } from "@/lib/hc/fetch";

import { PortalHeader } from "./portal-header";

// Cache-control for the whole portal subtree.
export const revalidate = 300;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const portal = await fetchPortal(slug);
  if (!portal) return { title: "Not found" };
  return {
    title: portal.page_title || portal.name,
    description: portal.header_text || undefined,
  };
}

export default async function PortalLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const portal = await fetchPortal(slug);
  if (!portal) notFound();

  return (
    <>
      <PortalHeader portal={portal} />
      <main className="mx-auto max-w-3xl px-4 py-8 md:px-6">{children}</main>
    </>
  );
}
