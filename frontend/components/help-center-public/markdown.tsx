import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

/**
 * Server-rendered Markdown for public Help Center articles.
 *
 * ``react-markdown`` does NOT render raw HTML by default — user-supplied
 * ``<script>`` / ``<iframe>`` get stripped, so this is XSS-safe even
 * though admin content can contain anything. ``remark-gfm`` adds tables,
 * task lists, and autolinks.
 */
export function Markdown({
  source,
  className,
}: {
  source: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        // Prose-like rhythm without bringing in @tailwindcss/typography.
        "space-y-4 text-fg",
        "[&_h1]:mt-8 [&_h1]:text-2xl [&_h1]:font-semibold",
        "[&_h2]:mt-6 [&_h2]:text-xl [&_h2]:font-semibold",
        "[&_h3]:mt-4 [&_h3]:text-lg [&_h3]:font-semibold",
        "[&_p]:leading-relaxed",
        "[&_a]:text-info [&_a:hover]:underline",
        "[&_strong]:font-semibold",
        "[&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-6",
        "[&_ol]:list-decimal [&_ol]:space-y-1 [&_ol]:pl-6",
        "[&_blockquote]:border-l-4 [&_blockquote]:border-border [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-fg-muted",
        "[&_code]:rounded [&_code]:bg-surface-2 [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-sm",
        "[&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:border [&_pre]:border-border [&_pre]:bg-surface-2 [&_pre]:p-3",
        "[&_pre_code]:bg-transparent [&_pre_code]:p-0",
        "[&_table]:w-full [&_table]:border-collapse [&_table]:text-sm",
        "[&_th]:border [&_th]:border-border [&_th]:bg-surface-2 [&_th]:p-2 [&_th]:text-left",
        "[&_td]:border [&_td]:border-border [&_td]:p-2",
        "[&_hr]:my-6 [&_hr]:border-border",
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{source}</ReactMarkdown>
    </div>
  );
}
