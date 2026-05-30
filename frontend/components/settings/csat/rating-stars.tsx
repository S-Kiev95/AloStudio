import { Star } from "lucide-react";

import { cn } from "@/lib/utils";

/** Renders 5 stars filled up to the given rating (1..5). */
export function RatingStars({
  rating,
  size = 16,
}: {
  rating: number;
  size?: number;
}) {
  return (
    <span className="inline-flex items-center gap-0.5" aria-label={`${rating} de 5`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          width={size}
          height={size}
          className={cn(
            "shrink-0",
            n <= rating ? "fill-warning text-warning" : "text-fg-muted",
          )}
          aria-hidden
        />
      ))}
    </span>
  );
}
