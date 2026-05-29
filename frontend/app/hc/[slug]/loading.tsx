/** Lightweight loading skeleton for the public Help Center subtree. */
export default function HelpCenterLoading() {
  return (
    <div className="space-y-6" aria-busy="true">
      <div className="h-7 w-2/3 animate-pulse rounded bg-surface-2" />
      <div className="space-y-2">
        <div className="h-4 w-full animate-pulse rounded bg-surface-2" />
        <div className="h-4 w-5/6 animate-pulse rounded bg-surface-2" />
        <div className="h-4 w-3/4 animate-pulse rounded bg-surface-2" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="h-24 animate-pulse rounded-lg bg-surface-2" />
        <div className="h-24 animate-pulse rounded-lg bg-surface-2" />
      </div>
    </div>
  );
}
