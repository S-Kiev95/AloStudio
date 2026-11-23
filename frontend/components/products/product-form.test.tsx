import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProductForm } from "./product-form";

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(new RegExp(`^${label}`)), { target: { value } });
}

describe("ProductForm — Meta catalogue", () => {
  it("doesn't offer the catalogue when the account has none", () => {
    const onSubmit = vi.fn();
    render(<ProductForm onSubmit={onSubmit} onCancel={() => {}} />);
    expect(screen.queryByLabelText("Publicar en el catálogo de Meta")).toBeNull();
    fill("Nombre", "Taller");
    fireEvent.click(screen.getByRole("button", { name: "Crear producto" }));
    expect(onSubmit).toHaveBeenCalledWith(expect.not.objectContaining({ meta_sync: expect.anything() }));
  });

  it("asks for what Meta needs before publishing a product", async () => {
    const onSubmit = vi.fn();
    render(<ProductForm catalogConnected onSubmit={onSubmit} onCancel={() => {}} />);
    fill("Nombre", "Taller de cerámica");
    fireEvent.click(screen.getByLabelText("Publicar en el catálogo de Meta"));
    fireEvent.click(screen.getByRole("button", { name: "Crear producto" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Para publicarlo en Meta falta: descripción, precio y moneda, enlace, imagen.",
    );
    expect(onSubmit).not.toHaveBeenCalled();

    fill("Descripción", "Ocho semanas");
    fill("Precio", "4500");
    fill("Moneda", "UYU");
    fill("URL del producto", "https://ctc.example/ceramica");
    fill("URL de imagen", "https://ctc.example/ceramica.jpg");
    fireEvent.click(screen.getByRole("button", { name: "Crear producto" }));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ meta_sync: true, price: 4500 }));
  });

  it("unticking takes a published product out of the catalogue", () => {
    const onSubmit = vi.fn();
    render(
      <ProductForm
        catalogConnected
        initial={{
          id: 1,
          account_id: 1,
          name: "Taller",
          description: null,
          sku: null,
          price: null,
          currency: null,
          url: null,
          image_url: null,
          enabled: true,
          created_at: null,
          meta_sync: true,
        }}
        onSubmit={onSubmit}
        onCancel={() => {}}
      />,
    );
    const box = screen.getByLabelText("Publicar en el catálogo de Meta");
    expect(box).toBeChecked();
    fireEvent.click(box);
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ meta_sync: false }));
  });
});
