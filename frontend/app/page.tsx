import Link from "next/link";

/**
 * Placeholder landing. F.1 adds real auth + redirects authenticated
 * users straight to their account dashboard.
 */
export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-3xl font-semibold">AloStudio</h1>
      <p className="text-sm opacity-70">
        Frontend scaffold (F.0). Auth + dashboard land in F.1+.
      </p>
      <Link
        href="/login"
        className="rounded-md border px-4 py-2 text-sm hover:bg-black/5"
      >
        Ir a login
      </Link>
    </main>
  );
}
