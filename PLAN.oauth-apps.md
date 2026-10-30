# PLAN — Apps OAuth para terceros

Cuarto plan de la salida de Postiz (Fase 7): AloStudio como servidor de autorización OAuth 2.0. Una cuenta registra una app (su integración, n8n, un conector de Claude o ChatGPT…); cualquier usuario de AloStudio puede autorizarla sobre una de sus cuentas, y la app recibe un token que funciona en el **servidor MCP** de AloStudio, igual que un token de "API y MCP" pero sin copiarlo a mano.

Se divide en dos ramas que salen de `main` (`6f00724`) y se integran juntas:

- **Backend** — rama `feat/oauth-apps`, worktree `C:\Users\Zeek\Desktop\AloStudio-oauth`. Lo hace Claude.
- **Frontend** — rama `feat/oauth-apps-ui`, worktree `C:\Users\Zeek\Desktop\AloStudio-oauth-ui`. Lo hace un agente (Argon) contra el contrato de la sección 2 y lo revisa Claude.

El backend todavía no existe mientras se hace el frontend: los tests del frontend usan msw con las respuestas exactas del contrato.

## Insumos

- `docs/design-neon/postiz/21-ajustes-apps.jpg`: la pantalla de apps de la versión anterior (pestañas "Apps" y "Apps aprobadas", tarjeta "Aplicación OAuth" con "Docs" y "Crear app OAuth"). Copiá disposición y jerarquía; textos en español y con lo que hace AloStudio.
- `docs/design-neon/DESIGN.md`, `frontend/DESIGN-SYSTEM.md` y los componentes de `frontend/components/ui/`.
- Patrones a copiar: `components/settings/mcp-tokens/mcp-tokens-view.tsx` (lista de tokens, mostrar un secreto una sola vez, rotar, borrar), `components/settings/settings-sidebar.tsx` (entradas de Ajustes), `components/ui/tabs.tsx` (`NavTabs`/`Tabs`), `app/(auth)/layout.tsx` y `app/(auth)/login/page.tsx` (pantallas fuera del panel), `lib/api/*.ts` (hooks de `@tanstack/react-query` sobre `apiFetch`), `lib/api/profile.ts` (`useIsAccountAdmin`).

## Reglas para el agente

Las mismas de `PLAN.publishing-ui.md`: trabajá **solo** en `C:\Users\Zeek\Desktop\AloStudio-oauth-ui`; no leas `C:\Users\Zeek\Desktop\Postiz` (otra licencia), `C:\Users\Zeek\Desktop\AloStudio` ni los otros worktrees de AloStudio; **no toques el backend** (`app/`, `alembic/`, `tests/` de Python); sin `git push`, sin `ssh`, sin tocar archivos `.env*`, sin levantar ni migrar bases, sin borrar contenedores ni volúmenes; **sin librerías nuevas** de npm. Commits chicos en `feat/oauth-apps-ui`, en español con el estilo del repo (`feat(oauth): ...`, `test(oauth): ...`), cada uno con todo el cambio que describe su mensaje y terminado en `Co-Authored-By: Antigravity <noreply@google.com>`. Al final completá **Estado** con la salida real y completa de `npm run typecheck`, `npm run lint` y `npm test` en `frontend/`. No declares verificado algo que no corriste.

Si el contrato de la sección 2 no alcanza para algo, no lo inventes: anotalo en **Estado** y resolvelo sin ese dato.

## Notas de las revisiones anteriores (cumplilas)

- **Sin modificadores de opacidad sobre colores del tema** (`bg-danger/10`, `border-warning/30`, `bg-primary/60`…): Tailwind 3 no genera esas clases con nuestros colores. Usá tokens sólidos (`bg-surface-2`, `bg-focused`, `bg-field`, `border-glass`, `text-danger`…) u `opacity-*`.
- **Permisos**: lo que el backend le niega a un agente (rol no administrador) no se le ofrece en pantalla.
- Un error del backend se muestra cerca de lo que lo provocó, nunca solo en consola.
- Lo que solo aparece al pasar el mouse tiene que poder usarse sin mouse (pantallas táctiles y teclado).
- Cada commit tiene que contener todo el cambio que describe su mensaje.

## 1. Cómo funciona (para entender las pantallas)

- **Registrar una app** (un administrador, en Ajustes → Apps OAuth): nombre y una o más URL de retorno. AloStudio le da un `client_id` y, si la app es *confidencial* (tiene servidor propio), un `client_secret` que **se muestra una sola vez**. Una app *pública* (de escritorio, móvil o un script) no tiene secreto y usa PKCE.
- **Autorizarla** (cualquier usuario): la app manda al navegador a `/oauth/authorize?client_id=…&redirect_uri=…&scope=…&state=…&code_challenge=…`. AloStudio muestra la pantalla de consentimiento: qué app pide acceso, con qué permiso y sobre cuál de las cuentas del usuario. Al aceptar, el navegador vuelve a la app con un código que la app cambia por un token.
- **Permisos**: `read` (consultar publicaciones, canales, estadísticas, conversaciones y contactos) y `write` (además crear y modificar: programar publicaciones, responder conversaciones…). Un agente (rol no administrador) solo puede dar `read` en esa cuenta.
- **Revocar**: cada usuario ve en "Apps aprobadas" las apps que autorizó en la cuenta y les puede sacar el acceso. Borrar una app revoca todos sus tokens.

## 2. Contrato de la API

Todo con `apiFetch` (pasa por el BFF con la sesión del panel). Los errores traen `{"message": "texto para mostrar"}`. Fechas en ISO 8601.

### 2.1 Apps de la cuenta (solo administradores; un agente recibe 401)

`GET /api/v1/accounts/{account_id}/oauth_apps` →

```json
{
  "apps": [
    {
      "id": 3,
      "name": "Mi integración",
      "client_id": "alo_app_6f1c2b9e8a",
      "confidential": true,
      "redirect_uris": ["https://example.com/oauth/callback"],
      "authorizations_count": 2,
      "created_at": "2026-10-30T15:00:00+00:00"
    }
  ],
  "endpoints": {
    "authorization": "https://host/oauth/authorize",
    "token": "https://host/oauth/token",
    "revocation": "https://host/oauth/revoke",
    "metadata": "https://host/.well-known/oauth-authorization-server",
    "mcp": "https://host/mcp"
  }
}
```

`POST /api/v1/accounts/{account_id}/oauth_apps` con `{"name": "Mi integración", "redirect_uris": ["https://…"], "confidential": true}` → la **App** y además `"client_secret": "alo_secret_…"` (solo si es confidencial; es la única vez que se ve).

`PATCH /api/v1/accounts/{account_id}/oauth_apps/{app_id}` con `{"name"?, "redirect_uris"?}` → la **App**.

`POST /api/v1/accounts/{account_id}/oauth_apps/{app_id}/secret` → la **App** con un `client_secret` nuevo (el anterior deja de andar). 422 si la app es pública.

`DELETE /api/v1/accounts/{account_id}/oauth_apps/{app_id}` → `{}` (revoca todos sus tokens).

Validaciones (422 con `message`): nombre de 1 a 80 caracteres; de 1 a 10 URL de retorno, cada una `https://…` (o `http://localhost…` / `http://127.0.0.1…` para desarrollo), sin `#`.

### 2.2 Apps aprobadas (cada usuario, en esta cuenta)

`GET /api/v1/accounts/{account_id}/oauth_authorizations` →

```json
{
  "authorizations": [
    {
      "app": { "id": 3, "name": "Mi integración", "client_id": "alo_app_6f1c2b9e8a" },
      "scope": "write",
      "authorized_at": "2026-10-30T15:10:00+00:00",
      "last_used_at": "2026-10-30T16:02:00+00:00"
    }
  ]
}
```

`DELETE /api/v1/accounts/{account_id}/oauth_authorizations/{app_id}` → `{}` (la app pierde el acceso de este usuario a esta cuenta).

### 2.3 Consentimiento

`GET /api/v1/oauth/authorize?{los parámetros que trajo la URL}` (con la sesión) devuelve **una** de estas formas:

```json
{
  "app": { "name": "Mi integración", "client_id": "alo_app_6f1c2b9e8a", "owner_account_name": "Estudio X" },
  "scope": "write",
  "redirect_uri": "https://example.com/oauth/callback",
  "accounts": [
    { "id": 1, "name": "Tienda Salto", "role": "administrator", "can_grant": true },
    { "id": 4, "name": "Club", "role": "agent", "can_grant": false }
  ]
}
```

o `{"redirect_to": "https://example.com/oauth/callback?error=invalid_scope&state=…"}` cuando el pedido está mal pero la URL de retorno es válida: la pantalla navega ahí directamente (`window.location.assign`).

- 400 `{"message"}`: `client_id` desconocido o `redirect_uri` no registrada. **Nunca** redirigir: mostrar el error en la pantalla.
- 401 sin sesión: lo resuelve `apiFetch` (sección 3.3), que lleva al login con la URL completa en `next`.

`POST /api/v1/oauth/authorize` con los mismos parámetros más `{"account_id": 1, "approve": true}` (o `"approve": false`) → `{"redirect_to": "https://example.com/oauth/callback?code=…&state=…"}` (o con `error=access_denied`). La pantalla navega a `redirect_to`. 403 `{"message"}` si el usuario no puede dar ese permiso en esa cuenta.

Los parámetros van tal cual vinieron en la URL (`response_type`, `client_id`, `redirect_uri`, `scope`, `state`, `code_challenge`, `code_challenge_method`); el backend los valida.

### 2.4 Lo que usan las apps (no lo llama el frontend; va en el panel de ayuda)

`POST /oauth/token` (`authorization_code` y `refresh_token`), `POST /oauth/revoke`, `GET /.well-known/oauth-authorization-server`, y el servidor MCP en `/mcp` con `Authorization: Bearer <access_token>`. Las URL completas vienen en `endpoints` (2.1).

## 3. Pantallas

### 3.1 Ajustes → Apps OAuth

- Entrada **"Apps OAuth"** en `settings-sidebar.tsx`, segmento `oauth_apps`, junto a "API y MCP". Visible para todos.
- Dos pestañas: **Apps** (solo administradores; a un agente se le muestra solo "Apps aprobadas") y **Apps aprobadas**.
- **Apps**: texto breve de qué es ("Registrá una app para que otros usuarios de AloStudio la autoricen sobre sus cuentas. La app recibe un token que funciona en el servidor MCP de AloStudio."), la lista de apps (nombre, `client_id` con botón copiar, pública/confidencial, URL de retorno, cuántas autorizaciones tiene), y por app: editar (nombre y URL de retorno, una por línea), regenerar secreto (solo confidenciales; `window.confirm`), borrar (`window.confirm` avisando que revoca todos sus tokens).
- **Crear app**: diálogo con nombre, URL de retorno (una por línea) y tipo (confidencial con secreto / pública con PKCE, con una línea que explique cuándo usar cada una). Al crear o regenerar, un diálogo muestra `client_id` y `client_secret` con botones de copiar y el aviso "Guardalo ahora: no se vuelve a mostrar" (copiá cómo lo hace `mcp-tokens-view.tsx`).
- **Panel de ayuda** ("Docs" en la captura): las URL de `endpoints` con botón copiar y los pasos en tres líneas (mandar al usuario a la URL de autorización con PKCE, cambiar el código por un token en `token`, llamar al MCP con `Authorization: Bearer`).
- **Apps aprobadas**: lista con nombre de la app, permiso ("Lectura" / "Lectura y escritura"), cuándo se autorizó y último uso ("Nunca" si `null`); botón "Quitar acceso" (`window.confirm`). Vacía: "No autorizaste ninguna app en esta cuenta."

### 3.2 Pantalla de consentimiento

- Ruta `app/(auth)/oauth/authorize/page.tsx` (usa el layout de `(auth)`, como el login).
- Al abrir, pide `GET /api/v1/oauth/authorize` con los parámetros de la URL:
  - 401 sin sesión → `apiFetch` lleva al login y el login vuelve acá (sección 3.3).
  - `redirect_to` → `window.location.assign(redirect_to)`.
  - 400 → tarjeta de error con el `message` y un enlace "Volver a AloStudio" (a `/accounts`).
  - Datos → "**{app.name}** quiere acceder a tu cuenta de AloStudio", "Creada por {owner_account_name}", el permiso explicado en una lista corta (para `read`: ver publicaciones, canales, estadísticas, conversaciones y contactos; para `write`: lo anterior y además programar y borrar publicaciones y responder conversaciones), un selector de cuenta (radios; las que tienen `can_grant: false` deshabilitadas con "Tu rol en esta cuenta no permite dar este acceso"), la URL de retorno en chico ("Te va a llevar a {host de redirect_uri}"), y botones **Autorizar** (primario) y **Cancelar**.
- Autorizar → `POST` con `approve: true`; Cancelar → `POST` con `approve: false`; en ambos casos `window.location.assign(redirect_to)`. Botones con `loading` y el error del `POST` (403 u otro) sobre los botones.
- Si el usuario tiene una sola cuenta que puede dar el acceso, viene elegida.

### 3.3 Volver a donde estabas después del login

- `lib/api/fetcher.ts`: ante un 401 de sesión vencida (no ante uno de permiso, que ya distingue `isDenial`), ir a `/login?next=` + `encodeURIComponent(location.pathname + location.search)` en vez de a `/login` pelado, salvo que ya esté en `/login`.
- `app/(auth)/login/page.tsx` hoy siempre va a la cuenta. Que lea `next` de la URL y, si es una ruta interna (empieza con `/`, no con `//` ni con `/\`), vaya ahí después de entrar; si no, como ahora.

Así el consentimiento (y cualquier pantalla con la sesión vencida) vuelve sola después del login.

**No pidas `/oauth_apps` si el usuario no es administrador** (`useIsAccountAdmin`): para un agente esa pestaña no existe.

## 4. Hooks y tests

- `frontend/lib/api/oauth.ts`: tipos del contrato y un hook por pedido (`useOAuthApps`, `useCreateOAuthApp`, `useUpdateOAuthApp`, `useRotateOAuthAppSecret`, `useDeleteOAuthApp`, `useOAuthAuthorizations`, `useRevokeOAuthAuthorization`, `useOAuthConsent`, `useSubmitOAuthConsent`).
- Tests con msw como el resto del frontend, como mínimo: la entrada de Ajustes; crear una app y ver el secreto una sola vez; regenerar y borrar con confirmación; un agente no ve la pestaña Apps; Apps aprobadas y quitar acceso; consentimiento con datos (cuenta deshabilitada, autorizar y cancelar navegan al `redirect_to`), con 400 (no navega), y con `redirect_to` directo; `apiFetch` ante un 401 de sesión (va a `/login?next=` con la ruta y los parámetros) y ante uno de permiso (no navega); el login con `next` interno y con uno externo (se ignora).

## Fuera de alcance

Registro dinámico de clientes (RFC 7591), logos de apps, permisos por herramienta, usar los tokens en la API REST, y cualquier cambio de backend.

## Backend (lo hace Claude en `feat/oauth-apps`, para referencia)

- Modelos `oauth_applications`, `oauth_authorization_codes` y `oauth_tokens` (secretos y tokens guardados con hash), con su migración.
- Endpoints de las secciones 2.1 a 2.3, y `POST /oauth/token` (código con PKCE S256, refresh token rotativo), `POST /oauth/revoke`, metadatos RFC 8414 y del recurso protegido (RFC 9728) para clientes MCP.
- El servidor MCP montado en el backend en `/mcp`, aceptando los tokens de OAuth además de los de "API y MCP", con el permiso que dio el usuario.

## Terminado cuando

Frontend: todo lo de las secciones 3 y 4 con typecheck, lint y tests en verde. Backend: el contrato con tests de integración (flujo completo con PKCE, refresh, revocación y uso del token en el MCP). Integrados: una app registrada en Ajustes obtiene un token tras el consentimiento y con él lista las publicaciones por MCP.

## Estado

Argon se quedó sin cuota al empezar (el primer intento se cortó con un reinicio de la PC; los siguientes, con `429 Individual quota reached`), así que el frontend lo hizo Claude, en `5788130`, `aaf6100` y `0cc8e9b`.

- Hecho: todo lo de las secciones 3 y 4. Ajustes → Apps OAuth con las pestañas Apps (solo administradores) y Apps aprobadas; crear app confidencial o pública, secreto visible una sola vez, regenerar, editar y borrar con confirmación; la guía de conexión con las URL de `endpoints`; `/oauth/authorize` con el permiso explicado, el selector de cuenta (las que no pueden dar el acceso, deshabilitadas) y la vuelta a la app; `apiFetch` lleva al login con `next` y el login vuelve ahí si es una ruta interna.
- Verificado: `npm run typecheck` y `npm run lint` sin errores; `npm test` con 87 archivos y 361 tests en verde (21 nuevos: Apps OAuth, consentimiento, login y `apiFetch`).
- Probado en el navegador junto al backend (`feat/oauth-apps`): crear la app y ver el secreto una vez; entrar al consentimiento sin sesión, pasar por el login y volver con todos los parámetros; autorizar; canjear el código con PKCE; usar el token en `/mcp` (actúa como el usuario, con permiso de escritura) y verlo en Apps aprobadas con su último uso; quitarle el acceso.
- Corregido en la prueba: mientras cargaba el perfil, un administrador veía primero la vista de agente (`0cc8e9b`).
- Pendiente para producción: en el VPS, que `/oauth/token`, `/oauth/revoke`, `/.well-known/oauth-*` y `/mcp` vayan al backend (rutas de Tailscale Funnel); `/oauth/authorize` sigue yendo al panel.
