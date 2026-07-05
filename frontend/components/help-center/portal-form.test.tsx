import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PortalForm } from "./portal-form";

// The logo picker presigns + PUTs through the uploads helper; stub it.
vi.mock("@/lib/api/uploads", () => ({
  uploadAttachment: vi.fn(async () => ({
    external_url: "https://cdn.example.com/logo.png",
    file_type: "image",
  })),
}));

describe("PortalForm logo", () => {
  it("uploads a picked logo and includes its URL in the submit", async () => {
    const onSubmit = vi.fn();
    render(
      <PortalForm accountId="1" onSubmit={onSubmit} onCancel={() => {}} />,
    );

    fireEvent.change(screen.getByLabelText(/Nombre/), {
      target: { value: "Docs" },
    });

    fireEvent.change(screen.getByLabelText("Subir logo"), {
      target: {
        files: [new File(["x"], "logo.png", { type: "image/png" })],
      },
    });

    // The uploaded logo renders as a preview.
    const img = (await screen.findByAltText(
      "Logo del portal",
    )) as HTMLImageElement;
    expect(img.src).toContain("https://cdn.example.com/logo.png");

    fireEvent.click(screen.getByRole("button", { name: "Crear portal" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      name: "Docs",
      logo: "https://cdn.example.com/logo.png",
    });
  });
});
