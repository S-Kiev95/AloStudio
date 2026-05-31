import { ContactDetailView } from "@/components/contacts/contact-detail-view";

export default async function ContactDetailPage({
  params,
}: {
  params: Promise<{ accountId: string; contactId: string }>;
}) {
  const { accountId, contactId } = await params;
  return (
    <ContactDetailView accountId={accountId} contactId={Number(contactId)} />
  );
}
