import { ContactNewView } from "@/components/contacts/contact-new-view";

export default async function ContactNewPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <ContactNewView accountId={accountId} />;
}
