import { FloatingLogos } from "@/components/brand/floating-logos";
import { getT } from "@/lib/i18n/server";

export default async function ConversationsEmptyPage() {
  const t = await getT();
  return (
    <div className="relative flex flex-1 items-center justify-center overflow-hidden p-6">
      <FloatingLogos />
      <p
        data-bounce
        className="relative z-10 rounded-control px-4 py-2 text-sm text-fg-muted"
      >
        {t("conversations.emptyPane")}
      </p>
    </div>
  );
}
