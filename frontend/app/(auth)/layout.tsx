import { FloatingLogos } from "@/components/brand/floating-logos";
import { NeonWordmark } from "@/components/brand/neon-wordmark";
import { ThemeToggle } from "@/components/shell/theme-toggle";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="relative flex min-h-dvh flex-col items-center justify-center p-4 sm:p-6">
      <div className="fixed right-3 top-3 z-20">
        <ThemeToggle />
      </div>
      <FloatingLogos />
      <div
        data-bounce
        className="page-enter glass-panel relative z-10 w-full max-w-[420px] rounded-panel bg-surface p-7 sm:p-9"
      >
        <div className="mb-7">
          <NeonWordmark className="text-[38px]" />
        </div>
        {children}
      </div>
    </div>
  );
}
