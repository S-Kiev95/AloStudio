import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  type FBLoginResponse,
  WhatsappEmbeddedSignup,
} from "./whatsapp-embedded-signup";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const ENDPOINT = "*/api/v1/accounts/1/whatsapp/embedded_signup";
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  push.mockClear();
  delete window.FB;
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderButton() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <WhatsappEmbeddedSignup accountId="1" />
    </QueryClientProvider>,
  );
}

describe("WhatsappEmbeddedSignup", () => {
  it("deshabilita el botón y lista los ajustes faltantes cuando ready es false", async () => {
    server.use(
      http.get(ENDPOINT, () =>
        HttpResponse.json({
          ready: false,
          missing: ["META_APP_ID", "WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID"],
          app_id: "",
          config_id: "",
          graph_api_version: "v23.0",
        }),
      ),
    );

    renderButton();

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Falta configurar en Ajustes → Instalación: META_APP_ID, WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID",
    );
    expect(
      screen.getByRole("button", { name: "Conectar WhatsApp" }),
    ).toBeDisabled();
  });

  it("inicia FB.login, combina el code con el evento WA_EMBEDDED_SIGNUP y abre la bandeja", async () => {
    let postedBody: unknown = null;
    server.use(
      http.get(ENDPOINT, () =>
        HttpResponse.json({
          ready: true,
          missing: [],
          app_id: "111",
          config_id: "cfg-1",
          graph_api_version: "v23.0",
        }),
      ),
      http.post(ENDPOINT, async ({ request }) => {
        postedBody = await request.json();
        return HttpResponse.json({
          created: true,
          inbox: {
            id: 42,
            channel_id: 9,
            name: "WhatsApp +59892111222",
            channel_type: "Channel::Whatsapp",
          },
        });
      }),
    );

    const init = vi.fn();
    let loginCallback: ((res: FBLoginResponse) => void) | null = null;
    const login = vi.fn((cb: (res: FBLoginResponse) => void) => {
      loginCallback = cb;
    });
    window.FB = { init, login };

    renderButton();

    const btn = await screen.findByRole("button", {
      name: "Conectar WhatsApp",
    });
    await waitFor(() => expect(btn).not.toBeDisabled());
    fireEvent.click(btn);

    await waitFor(() =>
      expect(init).toHaveBeenCalledWith({
        appId: "111",
        version: "v23.0",
        xfbml: false,
      }),
    );
    expect(login).toHaveBeenCalledWith(expect.any(Function), {
      config_id: "cfg-1",
      response_type: "code",
      override_default_response_type: true,
      extras: { setup: {}, sessionInfoVersion: "3" },
    });

    // Mensaje de un origen ajeno se ignora.
    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: "https://evil.example",
          data: JSON.stringify({
            type: "WA_EMBEDDED_SIGNUP",
            event: "FINISH",
            data: { phone_number_id: "pn-bad", waba_id: "waba-bad" },
          }),
        }),
      );
    });

    // Mensaje legítimo de Meta con los ids elegidos.
    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: "https://www.facebook.com",
          data: JSON.stringify({
            type: "WA_EMBEDDED_SIGNUP",
            event: "FINISH",
            data: { phone_number_id: "pn-1", waba_id: "waba-1" },
          }),
        }),
      );
      loginCallback?.({ authResponse: { code: "code-1" } });
    });

    await waitFor(() =>
      expect(postedBody).toEqual({
        code: "code-1",
        waba_id: "waba-1",
        phone_number_id: "pn-1",
      }),
    );
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/accounts/1/settings/inboxes/42"),
    );
  });

  it("muestra el paso cancelado o el error del evento message y el error del POST", async () => {
    server.use(
      http.get(ENDPOINT, () =>
        HttpResponse.json({
          ready: true,
          missing: [],
          app_id: "111",
          config_id: "cfg-1",
          graph_api_version: "v23.0",
        }),
      ),
      http.post(ENDPOINT, () =>
        HttpResponse.json(
          { message: "Ese número ya está conectado en otra cuenta." },
          { status: 422 },
        ),
      ),
    );

    window.FB = {
      init: vi.fn(),
      login: vi.fn((cb: (res: FBLoginResponse) => void) => {
        cb({ authResponse: { code: "code-err" } });
      }),
    };

    renderButton();

    const btn = await screen.findByRole("button", {
      name: "Conectar WhatsApp",
    });
    await waitFor(() => expect(btn).not.toBeDisabled());

    // Cancelación en el popup de Meta.
    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: "https://web.facebook.com",
          data: JSON.stringify({
            type: "WA_EMBEDDED_SIGNUP",
            event: "CANCEL",
            data: { current_step: "VERIFY_NUMBER" },
          }),
        }),
      );
    });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Cancelaste la conexión (VERIFY_NUMBER).",
    );

    // Flujo completo donde el POST falla con 422.
    fireEvent.click(btn);
    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: "https://www.facebook.com",
          data: JSON.stringify({
            type: "WA_EMBEDDED_SIGNUP",
            event: "FINISH_ONLY_WABA",
            data: { phone_number_id: "pn-2", waba_id: "waba-2" },
          }),
        }),
      );
    });

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Ese número ya está conectado en otra cuenta.",
      ),
    );
    expect(push).not.toHaveBeenCalled();
  });
});
