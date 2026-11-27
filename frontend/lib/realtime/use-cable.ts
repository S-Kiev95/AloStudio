"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { type Call, upsertActiveCall } from "../api/calls";
import { playNotificationSound } from "../notification-sound";
import { createCable, type CableMessage } from "./cable";

function targetConversationDisplayId(msg: CableMessage): number | null {
  const data = msg.data as Record<string, unknown> | null;
  if (!data || typeof data !== "object") return null;
  if (msg.event.startsWith("message.") || msg.event === "first.reply.created") {
    return typeof data.conversation_id === "number" ? data.conversation_id : null;
  }
  if (msg.event.startsWith("conversation.")) {
    return typeof data.id === "number" ? data.id : null;
  }
  return null;
}

/**
 * Subscribes to the account's RoomChannel and invalidates the relevant
 * TanStack Query caches on any inbound event (coarse but robust — new
 * messages + conversation changes refetch live). No-op when the cable
 * URL or pubsub token is missing (falls back to the queries' polling).
 */
export function useCable({
  pubsubToken,
  userId,
  accountId,
}: {
  pubsubToken: string | null;
  userId: number;
  accountId: string;
}) {
  const qc = useQueryClient();
  const url = process.env.NEXT_PUBLIC_CABLE_URL;

  useEffect(() => {
    if (!url || !pubsubToken) return;
    const dispose = createCable(
      url,
      {
        channel: "RoomChannel",
        pubsub_token: pubsubToken,
        user_id: userId,
        account_id: Number(accountId),
      },
      (msg) => {
        if (
          msg.event === "conversation.typing_on" ||
          msg.event === "conversation.typing_off"
        ) {
          return;
        }
        // Coarse-but-correct: refetch the affected query buckets. The bell
        // badge tracks ``notification.created`` specifically so we don't
        // wait the 60s poll interval to update.
        if (msg.event === "notification.created") {
          qc.invalidateQueries({ queryKey: ["notifications", accountId] });
          playNotificationSound();
          return;
        }
        // A call rang, was taken or ended (F7): the event carries the call.
        if (msg.event === "call.updated") {
          const call = (msg.data as { call?: Call } | null)?.call;
          if (call) upsertActiveCall(qc, accountId, call);
          qc.invalidateQueries({ queryKey: ["messages", accountId] });
          qc.invalidateQueries({ queryKey: ["conversations", accountId] });
          return;
        }
        const displayId = targetConversationDisplayId(msg);
        qc.invalidateQueries({ queryKey: ["conversations", accountId] });
        if (displayId !== null) {
          qc.invalidateQueries({
            queryKey: ["messages", accountId, displayId],
          });
          qc.invalidateQueries({
            queryKey: ["conversation", accountId, displayId],
          });
        } else {
          qc.invalidateQueries({ queryKey: ["messages", accountId] });
          qc.invalidateQueries({ queryKey: ["conversation", accountId] });
        }
      },
    );
    return dispose;
  }, [url, pubsubToken, userId, accountId, qc]);
}
