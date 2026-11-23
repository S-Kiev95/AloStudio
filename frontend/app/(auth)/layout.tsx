import { AuthSingularityShell } from "@/components/auth/black-hole-context";
import { FloatingLogos } from "@/components/brand/floating-logos";
import { NeonWordmark } from "@/components/brand/neon-wordmark";
import { LanguageSwitcher } from "@/components/shell/language-switcher";
import { ThemeToggle } from "@/components/shell/theme-toggle";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthSingularityShell
      topControls={
        <>
          <LanguageSwitcher />
          <ThemeToggle />
        </>
      }
      background={<FloatingLogos />}
      wordmark={<NeonWordmark className="text-[38px]" />}
    >
      {children}
    </AuthSingularityShell>
  );
}
