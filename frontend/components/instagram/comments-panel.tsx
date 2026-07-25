"use client";

import { CornerDownRight, Eye, EyeOff, Send, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  type IgComment,
  useComments,
  useDeleteComment,
  useHideComment,
  usePostComment,
  useReplyComment,
} from "@/lib/api/instagram-comments";
import { cn } from "@/lib/utils";

/**
 * Comments moderation for a published post. The GET does a live Meta sync and
 * needs an ``ig_media_id``, so this only renders when the post is published.
 */
export function CommentsPanel({
  accountId,
  postId,
  enabled,
}: {
  accountId: string;
  postId: number;
  enabled: boolean;
}) {
  const { data, isLoading, isError, error } = useComments(
    accountId,
    postId,
    enabled,
  );
  const post = usePostComment(accountId, postId);
  const [newComment, setNewComment] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // Group into top-level threads: a reply points at its parent's ig_comment_id.
  const threads = useMemo(() => {
    const list = data ?? [];
    const byParent = new Map<string, IgComment[]>();
    for (const c of list) {
      if (c.parent_comment_id) {
        const arr = byParent.get(c.parent_comment_id) ?? [];
        arr.push(c);
        byParent.set(c.parent_comment_id, arr);
      }
    }
    return list
      .filter((c) => !c.parent_comment_id)
      .map((c) => ({ comment: c, replies: byParent.get(c.ig_comment_id) ?? [] }));
  }, [data]);

  async function submitComment() {
    setFormError(null);
    const message = newComment.trim();
    if (!message) return;
    try {
      await post.mutateAsync(message);
      setNewComment("");
    } catch (e) {
      setFormError(
        (e as { message?: string })?.message ?? "No se pudo publicar el comentario.",
      );
    }
  }

  if (!enabled) {
    return (
      <p className="text-sm text-fg-muted">
        Los comentarios estarán disponibles cuando la publicación esté publicada.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {/* Post a new comment */}
      <div className="space-y-2">
        {formError ? (
          <p role="alert" className="text-sm text-danger">
            {formError}
          </p>
        ) : null}
        <Textarea
          aria-label="Nuevo comentario"
          rows={2}
          placeholder="Escribí un comentario…"
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          maxLength={2200}
        />
        <div className="flex justify-end">
          <Button
            size="sm"
            onClick={submitComment}
            loading={post.isPending}
            disabled={!newComment.trim()}
          >
            <Send className="h-4 w-4" aria-hidden />
            Comentar
          </Button>
        </div>
      </div>

      {/* Thread list */}
      {isLoading ? (
        <p className="text-sm text-fg-muted">Cargando comentarios…</p>
      ) : isError ? (
        <p role="alert" className="text-sm text-danger">
          {(error as { message?: string })?.message ??
            "No se pudieron cargar los comentarios."}
        </p>
      ) : threads.length === 0 ? (
        <p className="text-sm text-fg-muted">Todavía no hay comentarios.</p>
      ) : (
        <ul className="space-y-3">
          {threads.map(({ comment, replies }) => (
            <li key={comment.id} className="space-y-2">
              <CommentRow
                accountId={accountId}
                postId={postId}
                comment={comment}
                canReply
              />
              {replies.length ? (
                <ul className="space-y-2 border-l border-border pl-4">
                  {replies.map((r) => (
                    <li key={r.id}>
                      <CommentRow
                        accountId={accountId}
                        postId={postId}
                        comment={r}
                      />
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CommentRow({
  accountId,
  postId,
  comment,
  canReply = false,
}: {
  accountId: string;
  postId: number;
  comment: IgComment;
  canReply?: boolean;
}) {
  const hide = useHideComment(accountId, postId);
  const del = useDeleteComment(accountId, postId);
  const reply = useReplyComment(accountId, postId);

  const [replying, setReplying] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function run(fn: () => Promise<unknown>, fallback: string) {
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError((e as { message?: string })?.message ?? fallback);
    }
  }

  async function submitReply() {
    const message = replyText.trim();
    if (!message) return;
    await run(async () => {
      await reply.mutateAsync({ commentId: comment.id, message });
      setReplyText("");
      setReplying(false);
    }, "No se pudo responder.");
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-surface p-3",
        comment.hidden && "opacity-60",
      )}
    >
      <div className="flex items-start gap-2.5">
        <Avatar name={comment.from_username || "Usuario"} size="sm" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-fg">
            {comment.from_username ? `@${comment.from_username}` : "Usuario"}
            {comment.hidden ? (
              <span className="ml-2 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium uppercase text-fg-muted">
                Oculto
              </span>
            ) : null}
          </p>
          <p className="whitespace-pre-wrap break-words text-sm text-fg">
            {comment.text || <span className="text-fg-muted">(sin texto)</span>}
          </p>
          {comment.ig_created_at ? (
            <p className="mt-0.5 text-xs text-fg-muted">
              {new Date(comment.ig_created_at).toLocaleString()}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 gap-1">
          <IconBtn
            label={comment.hidden ? "Mostrar" : "Ocultar"}
            loading={hide.isPending}
            onClick={() =>
              run(
                () => hide.mutateAsync({ commentId: comment.id, hide: !comment.hidden }),
                "No se pudo cambiar la visibilidad.",
              )
            }
          >
            {comment.hidden ? (
              <Eye className="h-4 w-4" aria-hidden />
            ) : (
              <EyeOff className="h-4 w-4" aria-hidden />
            )}
          </IconBtn>
          <IconBtn
            label="Eliminar"
            danger
            loading={del.isPending}
            onClick={() => {
              if (!window.confirm("¿Eliminar este comentario?")) return;
              run(() => del.mutateAsync(comment.id), "No se pudo eliminar.");
            }}
          >
            <Trash2 className="h-4 w-4" aria-hidden />
          </IconBtn>
        </div>
      </div>

      {error ? (
        <p role="alert" className="mt-2 text-xs text-danger">
          {error}
        </p>
      ) : null}

      {canReply ? (
        <div className="mt-2">
          {replying ? (
            <div className="space-y-2">
              <Textarea
                aria-label="Respuesta"
                rows={2}
                placeholder="Escribí una respuesta…"
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                maxLength={2200}
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={submitReply}
                  loading={reply.isPending}
                  disabled={!replyText.trim()}
                >
                  Responder
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setReplying(false);
                    setReplyText("");
                  }}
                >
                  Cancelar
                </Button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setReplying(true)}
              className="flex items-center gap-1 text-xs font-medium text-info hover:underline"
            >
              <CornerDownRight className="h-3 w-3" aria-hidden />
              Responder
            </button>
          )}
        </div>
      ) : null}
    </div>
  );
}

function IconBtn({
  label,
  onClick,
  loading,
  danger,
  children,
}: {
  label: string;
  onClick: () => void;
  loading?: boolean;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={loading}
      className={cn(
        "rounded-md p-1.5 text-fg-muted hover:bg-surface-2 disabled:opacity-50",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        danger && "hover:text-danger",
      )}
    >
      {children}
    </button>
  );
}
