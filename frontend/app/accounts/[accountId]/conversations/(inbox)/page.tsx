import { FloatingLogos } from "@/components/brand/floating-logos";

export default function ConversationsEmptyPage() {
  return (
    <div className="relative flex flex-1 items-center justify-center overflow-hidden p-6">
      <FloatingLogos />
      <p
        data-bounce
        className="relative z-10 rounded-control px-4 py-2 text-sm text-fg-muted"
      >
        Elegí una conversación para empezar
      </p>
    </div>
  );
}
