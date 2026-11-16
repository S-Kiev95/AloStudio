"use client";

import { ArrowLeft, ExternalLink, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useChannelSettings } from "@/lib/api/instagram";
import {
  type Container,
  type InstagramPost,
  type Product,
  useDeletePost,
  useInstagramPost,
} from "@/lib/api/instagram-posts";
import { relativeTime } from "@/lib/time";

import { CommentsPanel } from "./comments-panel";
import { PostAutoreplyRules } from "./post-autoreply-rules";
import { PostMediaPreview } from "./post-media";
import { StateBadge } from "./state-badge";
import { useIntlTag, useLocale, useT } from "@/lib/i18n/provider";

export function PostDetail({
  accountId,
  postId,
}: {
  accountId: string;
  postId: number;
}) {
  const t = useT();
  const { data: post, isLoading, isError } = useInstagramPost(accountId, postId);

  if (isLoading) {
    return <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>;
  }
  if (isError || !post) {
    return (
      <p role="alert" className="p-8 text-center text-sm text-danger">
        {t("instagram.post.loadFailed")}
      </p>
    );
  }

  const published = post.state === "published" && Boolean(post.ig_media_id);

  return (
    <div className="space-y-4">
      <Link
        href={`/accounts/${accountId}/instagram/posts`}
        className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        {t("instagram.post.back")}
      </Link>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <CardTitle className="flex items-center gap-2">
              <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium uppercase text-fg-muted">
                {post.media_type}
              </span>
              <StateBadge state={post.state} />
            </CardTitle>
            <DeletePostButton accountId={accountId} post={post} />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <PostMediaPreview post={post} />

          <PostMeta post={post} />

          {post.caption?.trim() ? (
            <div>
              <p className="mb-1 text-xs font-medium uppercase text-fg-muted">
                {t("instagram.caption")}
              </p>
              <p className="whitespace-pre-wrap break-words text-sm text-fg">
                {post.caption}
              </p>
            </div>
          ) : null}

          {post.state === "failed" && post.error_message ? (
            <div
              role="alert"
              className="rounded-md border border-danger/30 bg-danger/5 p-3 text-sm text-danger"
            >
              <p className="font-medium">{t("instagram.post.publishError")}</p>
              <p>{post.error_message}</p>
              {post.error_code ? (
                <p className="mt-1 text-xs opacity-80">{t("instagram.post.code")} {post.error_code}</p>
              ) : null}
            </div>
          ) : null}

          {post.products?.length ? <ProductList products={post.products} /> : null}

          {post.containers?.length ? (
            <ContainerList containers={post.containers} />
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("instagram.tabs.autoreplies")}</CardTitle>
        </CardHeader>
        <CardContent>
          <PostAutoreplyRules accountId={accountId} postId={postId} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("publications.metrics.comments")}</CardTitle>
        </CardHeader>
        <CardContent>
          <CommentsPanel
            accountId={accountId}
            postId={postId}
            enabled={published}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function PostMeta({ post }: { post: InstagramPost }) {
  const intlTag = useIntlTag();
  const locale = useLocale();
  const t = useT();
  const rows: { label: string; value: React.ReactNode }[] = [];

  if (post.published_at) {
    rows.push({
      label: t("instagram.post.published"),
      value: new Date(post.published_at).toLocaleString(intlTag),
    });
  }
  if (post.scheduled_for) {
    rows.push({
      label: t("instagram.post.scheduled"),
      value: new Date(post.scheduled_for).toLocaleString(intlTag),
    });
  }
  rows.push({ label: t("contacts.filters.attr.created"), value: relativeTime(post.created_at, locale) });
  if (post.ig_media_id) {
    rows.push({ label: "Media ID", value: post.ig_media_id });
  }

  return (
    <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
      {rows.map((r) => (
        <div key={r.label} className="flex gap-2">
          <dt className="shrink-0 text-fg-muted">{r.label}:</dt>
          <dd className="min-w-0 truncate text-fg">{r.value}</dd>
        </div>
      ))}
      {post.ig_permalink ? (
        <div className="flex gap-2 sm:col-span-2">
          <dt className="shrink-0 text-fg-muted">{t("instagram.post.link")}</dt>
          <dd className="min-w-0">
            <a
              href={post.ig_permalink}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 truncate text-info hover:underline"
            >
              {t("instagram.post.viewOnInstagram")}
              <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

function ProductList({ products }: { products: Product[] }) {
  const t = useT();
  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase text-fg-muted">
        {t("instagram.linkedProducts")}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {products.map((p) => (
          <span
            key={p.id}
            className="rounded-full border border-border px-2 py-0.5 text-xs text-fg"
          >
            {p.name}
            {p.price != null
              ? ` · ${p.price}${p.currency ? ` ${p.currency}` : ""}`
              : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

function ContainerList({ containers }: { containers: Container[] }) {
  const t = useT();
  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase text-fg-muted">
        {t("instagram.post.containers")}
      </p>
      <ul className="space-y-1 text-xs text-fg-muted">
        {containers
          .slice()
          .sort((a, b) => a.position - b.position)
          .map((c) => (
            <li key={c.id} className="flex gap-2">
              <span className="font-mono">#{c.position}</span>
              <span>{c.ig_container_id}</span>
              <span className="text-fg">{c.status_code}</span>
              {c.poll_count ? <span>{t("instagram.post.checks", { count: c.poll_count })}</span> : null}
            </li>
          ))}
      </ul>
    </div>
  );
}

function DeletePostButton({
  accountId,
  post,
}: {
  accountId: string;
  post: InstagramPost;
}) {
  const t = useT();
  const router = useRouter();
  const del = useDeletePost(accountId);
  const settings = useChannelSettings(accountId, post.channel_instagram_id);
  const [error, setError] = useState<string | null>(null);

  if (post.state === "deleted") return null;

  // Meta's DELETE only exists on the Facebook-Login API. Offering the
  // button on an Instagram-Login channel just produces a 422 after the
  // confirm dialog — say so up front instead.
  if (settings.data && !settings.data.can_delete_media) {
    return (
      <p className="max-w-xs text-right text-xs text-fg-muted">
        {t("instagram.post.cannotDelete")}
      </p>
    );
  }

  async function onDelete() {
    if (!window.confirm(t("instagram.post.deleteConfirm"))) return;
    setError(null);
    try {
      await del.mutateAsync(post.id);
      router.push(`/accounts/${accountId}/instagram/posts`);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? t("instagram.post.deleteFailed"),
      );
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        size="sm"
        variant="ghost"
        onClick={onDelete}
        loading={del.isPending}
        className="text-danger hover:bg-danger/10"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
        {t("actions.delete")}
      </Button>
      {error ? (
        <p role="alert" className="max-w-xs text-right text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
