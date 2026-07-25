export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-bg p-4">
      {/* Brand mark over the auth card — the lit accent gradient + a soft glow,
          the first thing a signed-out visitor sees. */}
      <span className="flex items-center gap-2.5">
        <span
          className="grid h-9 w-9 place-items-center rounded-lg text-base font-bold text-primary-fg shadow-[0_2px_12px_rgb(252_213_53/0.4)]"
          style={{ background: "var(--gradient-primary)" }}
        >
          A
        </span>
        <span className="text-xl font-semibold tracking-tight text-fg">
          AloStudio
        </span>
      </span>
      <div className="w-full max-w-sm">{children}</div>
    </div>
  );
}
