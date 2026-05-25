"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { PostComposer } from "./post-composer";
import { PostList } from "./post-list";

export function PublishingView({ accountId }: { accountId: string }) {
  const [composing, setComposing] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-fg">Publicaciones</h2>
        <Button size="sm" onClick={() => setComposing((v) => !v)}>
          <Plus className="h-4 w-4" aria-hidden />
          Nueva publicación
        </Button>
      </div>

      {composing ? (
        <Card>
          <CardHeader>
            <CardTitle>Nueva publicación</CardTitle>
          </CardHeader>
          <CardContent>
            <PostComposer
              accountId={accountId}
              onCreated={() => setComposing(false)}
            />
          </CardContent>
        </Card>
      ) : null}

      <PostList accountId={accountId} />
    </div>
  );
}
