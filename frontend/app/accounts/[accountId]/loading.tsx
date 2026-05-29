/**
 * Dashboard-wide loading skeleton. Next.js shows this while the route's
 * server components stream — keeps the sidebar/topbar interactive and
 * gives a hint that the page itself is loading instead of an empty space.
 */
export default function AccountLoading() {
  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6" aria-busy="true">
      <div className="h-7 w-48 animate-pulse rounded bg-surface-2" />
      <div className="space-y-2">
        <div className="h-4 w-full animate-pulse rounded bg-surface-2" />
        <div className="h-4 w-5/6 animate-pulse rounded bg-surface-2" />
        <div className="h-4 w-4/6 animate-pulse rounded bg-surface-2" />
      </div>
      <div className="h-40 animate-pulse rounded-lg bg-surface-2" />
    </div>
  );
}
