"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { createCable } from "./cable";

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
      () => {
        qc.invalidateQueries({ queryKey: ["conversations", accountId] });
        qc.invalidateQueries({ queryKey: ["messages", accountId] });
        qc.invalidateQueries({ queryKey: ["conversation", accountId] });
      },
    );
    return dispose;
  }, [url, pubsubToken, userId, accountId, qc]);
}
