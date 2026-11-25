import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/lib/i18n/provider";

import { ErrorState } from "./error-state";

describe("ErrorState", () => {
  it("renders alert message and calls onRetry when clicking Reintentar", () => {
    const onRetry = vi.fn();
    render(
      <ErrorState
        message="No se pudieron cargar las métricas."
        onRetry={onRetry}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "No se pudieron cargar las métricas.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("translates the retry label with I18nProvider", () => {
    const onRetry = vi.fn();
    render(
      <I18nProvider locale="en">
        <ErrorState message="Could not load data." onRetry={onRetry} compact />
      </I18nProvider>,
    );

    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
