import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { InstallationView } from "./installation-view";

const CONFIGS = "*/api/v1/installation/configs";

const unset = {
  name: "META_APP_ID",
  title: "App ID de Facebook",
  description: "Identifica a AloStudio ante Meta.",
  group: "Meta (Facebook e Instagram)",
  kind: "text" as const,
  secret: false,
  value: "",
  configured: false,
  source: "environment" as const,
  editable: true,
};

const secret = {
  name: "META_APP_SECRET",
  title: "App Secret de Facebook",
  description: "Clave secreta de la misma app.",
  group: "Meta (Facebook e Instagram)",
  kind: "password" as const,
  secret: true,
  value: "abc••••••89",
  configured: true,
  source: "database" as const,
  editable: true,
};

const server = setupServer(
  http.get(CONFIGS, () => HttpResponse.json({ payload: [unset, secret] })),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderView() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <InstallationView />
    </QueryClientProvider>,
  );
}

describe("Configuración de la instalación", () => {
  it("distingue lo configurado de lo que falta", async () => {
    renderView();
    expect(await screen.findByText("App ID de Facebook")).toBeInTheDocument();
    expect(screen.getByText("Sin configurar")).toBeInTheDocument();
    expect(screen.getByText("Configurado")).toBeInTheDocument();
  });

  it("dice de dónde viene cada valor", async () => {
    renderView();
    await screen.findByText("App ID de Facebook");
    // Sin fila en la base, manda el archivo del servidor.
    expect(
      screen.getByText(/viene del archivo del servidor/),
    ).toBeInTheDocument();
    expect(screen.getByText("guardado desde acá")).toBeInTheDocument();
  });

  it("nunca pone un secreto en un campo de texto plano", async () => {
    renderView();
    const input = (await screen.findByLabelText(
      "App Secret de Facebook",
    )) as HTMLInputElement;
    expect(input.type).toBe("password");
    // El valor enmascarado vive en el placeholder, no en el value.
    expect(input.value).toBe("");
    expect(input.placeholder).toBe("abc••••••89");
  });

  it("no deja guardar un campo vacío", async () => {
    renderView();
    await screen.findByText("App ID de Facebook");
    const [guardar] = screen.getAllByRole("button", { name: "Guardar" });
    expect(guardar).toBeDisabled();
  });

  it("guarda lo que escribís y refresca", async () => {
    let received: unknown = null;
    server.use(
      http.put(`${CONFIGS}/META_APP_ID`, async ({ request }) => {
        received = await request.json();
        return HttpResponse.json({ ...unset, source: "database" });
      }),
    );
    renderView();
    const input = await screen.findByLabelText("App ID de Facebook");
    fireEvent.change(input, { target: { value: "1248493466251829" } });
    const [guardar] = screen.getAllByRole("button", { name: "Guardar" });
    fireEvent.click(guardar);

    await waitFor(() =>
      expect(received).toEqual({ value: "1248493466251829" }),
    );
  });

  it("explica un 401 en vez de mostrar un error genérico", async () => {
    server.use(
      http.get(CONFIGS, () =>
        HttpResponse.json(
          { error: "You are not authorized to do this action", code: "not_authorized" },
          { status: 401 },
        ),
      ),
    );
    renderView();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Sólo el operador de la instalación/,
    );
  });
});
