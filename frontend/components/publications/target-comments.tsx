"use client";

import { MessageCircle, ThumbsUp } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  parsePublicationError,
  type PublicationComment,
  useReplyTargetComment,
  useTargetComments,
} from "@/lib/api/publications";
import { useIntlTag, useT } from "@/lib/i18n/provider";

function when(iso: string | null, intlTag: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleString(intlTag, { dateStyle: "short", timeStyle: "short" });
}

function CommentBody({ comment }: { comment: PublicationComment }) {
  const intlTag = useIntlTag();
  return (
    <div className="min-w-0">
      <p className="text-xs text-fg-muted">
        <span className="font-medium text-fg">{comment.author ?? "—"}</span>
        {" · "}
        {when(comment.published_at, intlTag)}
        {comment.like_count > 0 ? (
          <span className="ml-2 inline-flex items-center gap-0.5">
            <ThumbsUp className="h-3 w-3" aria-hidden />
            {comment.like_count}
          </span>
        ) : null}
      </p>
      <p className="whitespace-pre-wrap break-words text-sm text-fg">{comment.text}</p>
    </div>
  );
}

function ReplyBox({
  accountId,
  publicationId,
  targetId,
  commentId,
  onDone,
}: {
  accountId: string;
  publicationId: number;
  targetId: number;
  commentId: string;
  onDone: () => void;
}) {
  const t = useT();
  const [text, setText] = useState("");
  const reply = useReplyTargetComment(accountId, publicationId, targetId);
  const error = reply.error ? parsePublicationError(reply.error).message : null;
  return (
    <form
      className="mt-2 space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        reply.mutate(
          { commentId, text },
          {
            onSuccess: () => {
              setText("");
              onDone();
            },
          },
        );
      }}
    >
      <Textarea
        value={text}
        rows={2}
        maxLength={10000}
        placeholder={t("publications.comments.replyPlaceholder")}
        aria-label={t("publications.comments.replyPlaceholder")}
        onChange={(e) => setText(e.target.value)}
      />
      {error ? (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onDone}>
          {t("actions.cancel")}
        </Button>
        <Button type="submit" size="sm" loading={reply.isPending} disabled={!text.trim()}>
          {t("publications.comments.send")}
        </Button>
      </div>
    </form>
  );
}

/** Comments of a published video, read live from the network, with
 *  replies from the channel (administrators). */
export function TargetComments({
  accountId,
  publicationId,
  targetId,
  canReply,
}: {
  accountId: string;
  publicationId: number;
  targetId: number;
  canReply: boolean;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [replyingTo, setReplyingTo] = useState<string | null>(null);
  const query = useTargetComments(accountId, publicationId, targetId, open);

  if (!open) {
    return (
      <Button type="button" variant="secondary" size="sm" onClick={() => setOpen(true)}>
        <MessageCircle className="mr-1.5 h-4 w-4" aria-hidden />
        {t("publications.comments.show")}
      </Button>
    );
  }

  const comments = query.data?.comments ?? [];
  return (
    <section aria-label={t("publications.comments.title")} className="space-y-2 pt-1">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-medium uppercase tracking-[0.08em] text-fg-muted">
          {t("publications.comments.title")}
        </h4>
        <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
          {t("publications.comments.hide")}
        </Button>
      </div>
      {query.isLoading ? (
        <p className="text-xs text-fg-muted">{t("common.loading")}</p>
      ) : query.isError ? (
        <p role="alert" className="text-xs text-danger">
          {parsePublicationError(query.error).message}
        </p>
      ) : comments.length === 0 ? (
        <p className="text-xs text-fg-muted">{t("publications.comments.empty")}</p>
      ) : (
        <ul className="space-y-2">
          {comments.map((comment) => (
            <li
              key={comment.id}
              className="rounded-sm border border-glass bg-field px-2.5 py-2"
            >
              <CommentBody comment={comment} />
              {comment.replies.length > 0 ? (
                <ul className="mt-2 space-y-1.5 border-l border-glass pl-3">
                  {comment.replies.map((reply) => (
                    <li key={reply.id}>
                      <CommentBody comment={reply} />
                    </li>
                  ))}
                </ul>
              ) : null}
              {canReply ? (
                replyingTo === comment.id ? (
                  <ReplyBox
                    accountId={accountId}
                    publicationId={publicationId}
                    targetId={targetId}
                    commentId={comment.id}
                    onDone={() => setReplyingTo(null)}
                  />
                ) : (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="mt-1"
                    onClick={() => setReplyingTo(comment.id)}
                  >
                    {t("publications.comments.reply")}
                  </Button>
                )
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
