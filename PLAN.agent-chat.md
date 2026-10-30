# PLAN — Agente con chat

Tercer plan de la salida de Postiz (Fase 7): una pantalla de chat donde una IA arma, programa y consulta publicaciones usando las herramientas MCP que ya existen. Proveedor elegido por el dueño (2026-10-30): **OpenAI**, con la clave que ya está cargada en la instalación.

Se divide en dos ramas que salen de `main` (`6f00724`) y se integran juntas:

- **Backend** — rama `feat/agent-chat`, worktree `C:\Users\Zeek\Desktop\AloStudio-agent`. Lo hace Claude.
- **Frontend** — rama `feat/agent-chat-ui`, worktree `C:\Users\Zeek\Desktop\AloStudio-agent-ui`. Lo hace un agente (Argon) contra el contrato de la sección 2 y lo revisa Claude.

El backend todavía no existe mientras se hace el frontend: los tests del frontend usan msw con las respuestas exactas del contrato.

## Insumos

- `docs/design-neon/postiz/03-agente.jpg`: la pantalla del agente de la versión anterior. Copiá disposición y jerarquía (columna de chats con "Nuevo chat" arriba, conversación al centro, composer abajo). La columna "Select Channels" de la derecha queda fuera de alcance.
- `docs/design-neon/DESIGN.md`, `frontend/DESIGN-SYSTEM.md` y los componentes de `frontend/components/ui/`.
- Patrones a copiar: `components/conversations/inbox-shell.tsx` (lista que queda montada al cambiar de chat), `components/conversations/message-bubble.tsx` y `message-composer.tsx` (estilo de burbujas y composer; copiá el estilo, no los reutilices si te obligan a fabricar un mensaje de la bandeja), `components/publications/network-icon.tsx` (`NetworkIcon`, `networkLabel`), `lib/api/publications.ts` (hooks de `@tanstack/react-query` sobre `apiFetch`), `lib/api/profile.ts` (`useIsAccountAdmin`).

## Reglas para el agente

Las mismas de `PLAN.publishing-ui.md`: trabajá **solo** en `C:\Users\Zeek\Desktop\AloStudio-agent-ui`; no leas `C:\Users\Zeek\Desktop\Postiz` (otra licencia) ni `C:\Users\Zeek\Desktop\AloStudio` ni `C:\Users\Zeek\Desktop\AloStudio-agent`; **no toques el backend** (`app/`, `alembic/`, `tests/` de Python); sin `git push`, sin `ssh`, sin tocar archivos `.env*`, sin levantar ni migrar bases, sin borrar contenedores ni volúmenes; **sin librerías nuevas** de npm (ni markdown, ni chat UI, ni fechas). Commits chicos en `feat/agent-chat-ui`, en español con el estilo del repo (`feat(agente): ...`, `test(agente): ...`), cada uno con todo el cambio que describe su mensaje y terminado en `Co-Authored-By: Antigravity <noreply@google.com>`. Al final completá **Estado** con la salida real y completa de `npm run typecheck`, `npm run lint` y `npm test` en `frontend/`. No declares verificado algo que no corriste.

Si el contrato de la sección 2 no alcanza para algo, no lo inventes: anotalo en **Estado** y resolvelo sin ese dato.

## Notas de las revisiones anteriores (cumplilas)

- **Sin modificadores de opacidad sobre colores del tema** (`bg-danger/10`, `border-warning/30`, `bg-primary/60`…): los colores son `var(--…)` con un hex adentro y Tailwind 3 no genera ninguna regla para esas clases. Usá tokens sólidos (`bg-surface-2`, `bg-focused`, `bg-field`, `border-glass`, `text-danger`…) u `opacity-*`.
- **Fechas**: mostralas en la hora local del navegador. Si mandás un instante, ISO con zona.
- **Permisos**: lo que el backend le niega a un agente (rol no administrador) no se le ofrece en pantalla. Acá lo decide `can_write` (sección 2.1).
- Un error del backend se muestra cerca de lo que lo provocó (el composer o la tarjeta de confirmación), nunca solo en consola.
- Cada commit tiene que contener todo el cambio que describe su mensaje.

## 1. Cómo funciona (para entender la pantalla)

- Cada usuario tiene **sus** chats (no se comparten con el resto de la cuenta). Un chat guarda todo el historial.
- El usuario escribe; el backend llama a OpenAI, que puede usar herramientas antes de responder: consultar canales, medios, calendario y estadísticas (se ejecutan solas) o **crear y borrar publicaciones**, que **nunca** se ejecutan sin que el usuario las confirme en una tarjeta.
- Cuando el modelo quiere crear o borrar una publicación, el turno termina con una **acción pendiente**: la pantalla muestra la vista previa y los botones. Confirmar la ejecuta y el agente sigue; rechazarla la descarta. Si en vez de confirmar el usuario escribe otro mensaje ("cambiala a las 11"), la acción pendiente se descarta sola y el agente arma una nueva propuesta.
- Un administrador puede todo. Un agente (rol no administrador) solo consulta: el backend no le ofrece al modelo las herramientas que escriben.
- Las respuestas no son en streaming: cada pedido devuelve el chat completo actualizado. Un turno puede tardar de 5 a 40 segundos.

## 2. Contrato de la API

Base: `/api/v1/accounts/{account_id}/agent` (con `apiFetch`, igual que el resto). Todas las respuestas de error traen `{"message": "texto para mostrar"}`. Fechas en ISO 8601 UTC (`2026-10-30T14:02:11Z`).

### 2.1 Estado

`GET /agent` →

```json
{ "enabled": true, "model": "gpt-5.4-mini", "can_write": true }
```

- `enabled: false`: falta la clave de OpenAI. La pantalla muestra un aviso y deshabilita el composer (los chats viejos se pueden leer).
- `can_write: false`: el usuario no es administrador.

### 2.2 Chats

`GET /agent/threads` → los chats del usuario, el más reciente primero:

```json
{ "threads": [ { "id": 7, "title": "Post para el lunes", "updated_at": "2026-10-30T14:02:11Z", "has_pending_action": false } ] }
```

`POST /agent/threads` con `{"content": "texto", "timezone": "America/Montevideo"}` → crea el chat con ese primer mensaje, corre el turno y devuelve el **Chat** (2.3). El título lo pone el backend.

`GET /agent/threads/{thread_id}` → el **Chat**. 404 si no es del usuario.

`POST /agent/threads/{thread_id}/messages` con `{"content": "texto", "timezone": "America/Montevideo"}` → corre un turno y devuelve el **Chat**.

`POST /agent/threads/{thread_id}/actions/{action_id}/confirm` → ejecuta la acción pendiente, el agente sigue y devuelve el **Chat**.

`POST /agent/threads/{thread_id}/actions/{action_id}/reject` → descarta la acción pendiente y devuelve el **Chat** (sin respuesta nueva del agente).

`DELETE /agent/threads/{thread_id}` → `{}`.

`timezone` es la zona del navegador (`Intl.DateTimeFormat().resolvedOptions().timeZone`): el agente la usa para entender "mañana a las 10". `content` va de 1 a 4000 caracteres.

### 2.3 Chat

```json
{
  "id": 7,
  "title": "Post para el lunes",
  "created_at": "2026-10-30T14:00:02Z",
  "updated_at": "2026-10-30T14:02:11Z",
  "items": [
    { "id": 31, "kind": "user", "content": "Armame un post para el lunes a las 10 en Instagram", "created_at": "2026-10-30T14:00:02Z" },
    { "id": 33, "kind": "tool", "tool": "list_publication_channels", "status": "done", "label": "Consultó tus canales", "detail": null, "publication_id": null, "created_at": "2026-10-30T14:00:05Z" },
    { "id": 35, "kind": "tool", "tool": "create_publication", "status": "pending", "label": "Espera tu confirmación", "detail": null, "publication_id": null, "created_at": "2026-10-30T14:00:09Z" }
  ],
  "pending_action": {
    "id": "call_Q2x9",
    "tool": "create_publication",
    "title": "Programar publicación",
    "confirm_label": "Programar",
    "publication": {
      "id": null,
      "content": "¡Arrancamos la semana con todo! …",
      "scheduled_for": "2026-11-02T13:00:00Z",
      "channels": [ { "id": 4, "name": "Tienda Salto", "network": "instagram" } ],
      "media": [ { "id": 9, "type": "image", "url": "https://…/foto.jpg" } ]
    }
  }
}
```

`items` va del más viejo al más nuevo y tiene tres tipos:

- `kind: "user"` y `kind: "assistant"`: `content` es **texto plano** (párrafos y listas con guiones; el backend le pide al modelo que no use markdown). Mostralo con `whitespace-pre-wrap`.
- `kind: "tool"`: algo que hizo el agente. `status` es `done`, `error`, `rejected` o `pending`; `label` ya viene en español ("Consultó tus canales", "Programó la publicación", "No se pudo programar"…); `detail` es texto opcional (por ejemplo el error); `publication_id` viene cuando la acción creó o tocó una publicación.

`pending_action` es `null` o la acción que espera confirmación (como mucho una). Su `id` es el `action_id` de confirm/reject. `tool` es `create_publication` o `cancel_publication`; `title` y `confirm_label` ya vienen en español ("Programar", "Publicar ahora" cuando `scheduled_for` es `null`, "Borrar"). En `publication`, `scheduled_for: null` significa que sale en los próximos minutos; para `cancel_publication`, `publication.id` es la publicación que se va a borrar.

### 2.4 Errores que la pantalla tiene que manejar

| Código | Cuándo | Qué hacer |
|---|---|---|
| 503 | No hay clave de OpenAI | Mostrar `message`. |
| 502 | OpenAI falló o tardó demasiado | Mostrar `message` cerca del composer. El mensaje del usuario **quedó guardado**: volvé a pedir el chat en vez de reponer el texto en el composer. En `POST /agent/threads` el cuerpo trae además `thread_id`, el chat que quedó creado: mostralo. |
| 409 | El agente todavía está respondiendo en ese chat, o la acción ya no está pendiente | Mostrar `message` y volver a pedir el chat. |
| 422 | Texto vacío o de más de 4000 caracteres, zona inválida | Mostrar `message` junto al composer. |

## 3. Pantalla

### 3.1 Menú

Ítem **"Agente"** en `components/shell/nav.ts` (icono `Sparkles` de `lucide-react`), segmento `agent`, ubicado justo después de "Calendario" como en la captura. Visible para todos los usuarios.

### 3.2 Rutas y disposición

- `/accounts/[accountId]/agent`: chat nuevo (estado vacío). `/accounts/[accountId]/agent/[threadId]`: un chat.
- Un `layout.tsx` con la columna de chats (como `inbox-shell.tsx`, que no se recarga al cambiar de chat) y la conversación a la derecha.
- **Columna de chats** (≈ 16 rem): botón primario "Nuevo chat" arriba; debajo la lista (título truncado y fecha relativa corta), el activo resaltado, un punto o etiqueta "Por confirmar" si `has_pending_action`, y borrar con un icono que aparece al pasar el mouse (con `window.confirm`). Sin chats: "Todavía no tenés chats."
- **Conversación**: encabezado con el título; los ítems con scroll que baja solo al llegar algo nuevo; el composer fijo abajo.
- En pantallas angostas (< `md`) la columna de chats se oculta y se abre con un botón "Chats" en el encabezado (copiá cómo lo resuelve la bandeja).

### 3.3 Estado vacío (chat nuevo)

Saludo breve: "Hola, soy el agente de AloStudio. Puedo armar y programar publicaciones en tus canales, revisar tu calendario y contarte cómo les fueron tus posts." y tres sugerencias que se envían al tocarlas:

- "Armá una publicación para mañana a las 10 en todos mis canales"
- "¿Qué tengo programado esta semana?"
- "¿Cómo les fue a mis publicaciones del último mes?"

Con `can_write: false` la primera sugerencia no aparece.

### 3.4 Mensajes y actividad

- Usuario: burbuja a la derecha. Agente: burbuja a la izquierda. Texto con `whitespace-pre-wrap` y `break-words`.
- `kind: "tool"`: una fila chica y discreta (no una burbuja) con icono según `status` (`Check`, `X`, `Clock`, `Ban` para `rejected`) y el `label`; `detail` debajo en `text-fg-muted`. Si trae `publication_id`, un enlace "Ver en el calendario" a `/accounts/{accountId}/publications?publication={id}`.
- Mientras se espera la respuesta: la burbuja del usuario aparece al instante (optimista) y debajo una burbuja del agente con "Pensando…" animada (`animate-pulse`). Al responder, todo se reemplaza por el **Chat** que devolvió el backend.

### 3.5 Tarjeta de confirmación

Si `pending_action` no es `null`, al final de la conversación va una tarjeta con borde (`border-glass`, `bg-surface-2`):

- Título (`pending_action.title`).
- Canales con `NetworkIcon` y nombre.
- El texto de la publicación (`whitespace-pre-wrap`, hasta ~8 líneas con "Ver más").
- Medios: miniaturas chicas (imagen, o `<video>` sin controles con `preload="metadata"`).
- Cuándo sale: fecha y hora locales ("Sale el lun 2 nov, 10:00") o "Sale en los próximos minutos" si `scheduled_for` es `null`. Para `cancel_publication`: "Se va a borrar esta publicación".
- Botones: primario con `confirm_label` (`variant="destructive"` para `cancel_publication`) y secundario "Cancelar" (reject). Ambos con `loading` mientras esperan; al confirmar puede tardar como un turno.
- Debajo, en `text-fg-muted`: "Si querés cambiar algo, escribilo y el agente arma una nueva propuesta."

Después de confirmar o rechazar, invalidá las consultas de publicaciones (`["publications", accountId]`, `["publication", accountId, id]` y `["publication-analytics", accountId]`, como `invalidatePublications` en `lib/api/publications.ts`; exportala si te sirve) para que el calendario se actualice.

### 3.6 Composer

`<textarea>` que crece hasta ~6 líneas; Enter envía, Shift+Enter hace salto de línea; botón de enviar (icono `ArrowUp`) deshabilitado si está vacío o esperando. Contador "N/4000" visible desde los 3500 caracteres; más de 4000 no se envía. Manda siempre `timezone`.

### 3.7 Avisos

- `enabled: false`: aviso en lugar del estado vacío: "El agente todavía no está configurado. Un operador de la instalación tiene que cargar la clave de OpenAI en Ajustes → Instalación → Inteligencia artificial." y el composer deshabilitado.
- `can_write: false`: nota fija bajo el encabezado: "Podés consultar publicaciones y estadísticas. Crear o borrar publicaciones lo hace un administrador."

### 3.8 Calendario: abrir una publicación desde la URL

`/accounts/{accountId}/publications?publication={id}` abre el detalle de esa publicación (el mismo diálogo que al hacer clic en el calendario; usá `usePublication` si no está en el rango cargado) y saca el parámetro de la URL al cerrarlo, como ya hace `calendar-view.tsx` con `connected`/`channel`.

## 4. Hooks y tests

- `frontend/lib/api/agent.ts`: tipos del contrato y un hook por pedido (`useAgentStatus`, `useAgentThreads`, `useAgentThread`, `useCreateAgentThread`, `useSendAgentMessage`, `useConfirmAgentAction`, `useRejectAgentAction`, `useDeleteAgentThread`). Las mutaciones dejan el **Chat** devuelto en la caché de `useAgentThread` (`setQueryData`) e invalidan la lista de chats.
- Tests con msw como el resto del frontend, como mínimo: el ítem del menú; la lista de chats; enviar un mensaje (burbuja optimista, "Pensando…", resultado); la tarjeta de confirmación (confirmar y cancelar pegan a la URL correcta y se ve el resultado); un error 502 que vuelve a pedir el chat; `enabled: false`; `can_write: false`; `?publication=` en el calendario.

## Fuera de alcance

Streaming de la respuesta, adjuntar o subir medios desde el chat, generar imágenes o videos, el selector de canales de la derecha de la captura, herramientas de bandeja y contactos, 👍/👎, renombrar chats, y cualquier cambio de backend.

## Backend (lo hace Claude en `feat/agent-chat`, para referencia)

- Modelos `agent_threads` y `agent_messages` con su migración; `app/domains/agent/` con el router de la sección 2, el bucle del turno y los presentadores.
- El modelo de OpenAI recibe como funciones las herramientas MCP de publicación (`list_publication_channels`, `list_media`, `list_publications`, `get_publishing_analytics`, y si el usuario es administrador `create_publication` y `cancel_publication`); se ejecutan en el proceso con el usuario, la cuenta y el permiso de quien chatea. Las que escriben quedan pendientes hasta la confirmación.
- `OPENAI_API_KEY` y `OPENAI_AGENT_MODEL` (por defecto `gpt-5.4-mini`) editables en Ajustes → Instalación, grupo "Inteligencia artificial".
- Límites: hasta 6 llamadas al modelo por turno, 90 s por llamada, los últimos 40 mensajes como contexto, un turno a la vez por chat (409).

## Terminado cuando

Frontend: todo lo de las secciones 3 y 4 con typecheck, lint y tests en verde. Backend: el contrato de la sección 2 con tests de integración (OpenAI simulado). Integrados: se puede pedir en el chat "programá un post para mañana a las 10 en Instagram", ver la tarjeta, confirmarla y encontrar la publicación en el calendario.

## Estado

### Qué se hizo

- **Cliente de API, tipos del contrato y hooks (`frontend/lib/api/agent.ts` y `frontend/lib/api/publications.ts`)**:
  - Tipos completos para la sección 2 (`AgentStatus`, `AgentThreadSummary`, `AgentThreadsResponse`, `AgentTextItem`, `AgentToolItem`, `AgentItem`, `AgentPendingChannel`, `AgentPendingMedia`, `AgentPendingPublication`, `AgentPendingAction`, `AgentThread`, `AgentMessageInput`) y utilidades `getBrowserTimezone`, `getAgentErrorMessage` e `isAgentErrorStatus`.
  - Los 8 hooks pedidos: `useAgentStatus`, `useAgentThreads`, `useAgentThread` (`staleTime: 30_000` para reutilizar el chat recién creado sin pedirlo de nuevo al navegar), `useCreateAgentThread`, `useSendAgentMessage`, `useConfirmAgentAction`, `useRejectAgentAction` y `useDeleteAgentThread`.
  - Las mutaciones actualizan la caché de `useAgentThread` con `setQueryData`, invalidan `["agent-threads", accountId]`, vuelven a pedir el chat ante `502` o `409`, y al confirmar o rechazar una acción llaman a `invalidatePublications` (exportada desde `frontend/lib/api/publications.ts`) sobre `["publications", accountId]`, `["publication", accountId, id]` y `["publication-analytics", accountId]`.
- **3.1 Menú lateral (`frontend/components/shell/nav.ts`)**:
  - Agregado el ítem `"Agente"` (`key: "agent"`, icono `Sparkles`, `segment: "agent"`) justo después de `"Calendario"` en `NAV_ITEMS` y `NAV_GROUPS`, visible para todos los usuarios.
- **3.2 Rutas y disposición en dos columnas**:
  - Rutas `frontend/app/accounts/[accountId]/agent/layout.tsx`, `page.tsx` y `[threadId]/page.tsx`.
  - `frontend/components/agent/agent-shell.tsx`: contenedor de dos columnas siguiendo `InboxShell`, manteniendo montada la columna de chats al cambiar de ruta y ocultándola en `< md` para abrirla desde el botón `"Chats"` del encabezado.
  - `frontend/components/agent/agent-thread-list.tsx` y `agent-time.ts`: columna de chats (`md:w-64`, 16 rem) con botón primario `"Nuevo chat"` arriba, título truncado, fecha relativa corta en hora local, resaltado del chat activo (`bg-focused`, `text-lit`), indicador `"Por confirmar"` cuando `has_pending_action` es `true`, borrado al pasar el mouse con `window.confirm`, estado vacío `"Todavía no tenés chats."` y errores de borrado visibles en la columna.
- **3.3 a 3.7 Pantalla de chat, actividad, tarjeta de confirmación, composer y avisos**:
  - `frontend/components/agent/agent-chat-view.tsx`: encabezado con título y botón `"Chats"` en móvil; nota fija para `can_write: false`; aviso para `enabled: false` (conservando legibles los chats anteriores y deshabilitando el composer); estado vacío con saludo y las 3 sugerencias clicables (ocultando la primera si `can_write: false`); burbujas de usuario y asistente en texto plano (`whitespace-pre-wrap break-words`); filas discretas de `tool` con iconos `Check` / `X` / `Clock` / `Ban`, `detail` en `text-fg-muted` y enlace `"Ver en el calendario"` cuando hay `publication_id`; burbuja optimista del usuario + `"Pensando…"` (`animate-pulse`) durante el turno; auto-scroll al llegar nuevos ítems; manejo de errores `503`, `502` (sin reponer el texto en el composer y refetcheando el chat), `409` (incluyendo alerta visible cuando al refetchear desaparece `pending_action`) y `422`.
  - `frontend/components/agent/pending-action-card.tsx`: tarjeta con `border-glass bg-surface-2`, título, canales con `NetworkIcon` y `networkLabel`, texto con `whitespace-pre-wrap` colapsable a ~8 líneas con `"Ver más"`, miniaturas de imagen y `<video preload="metadata">` sin controles, horario en zona local (`"Sale el lun 2 nov, 10:00"`, `"Sale en los próximos minutos"` o `"Se va a borrar esta publicación"`), botones `confirm_label` (`variant="destructive"` en `cancel_publication`) y `"Cancelar"` con `loading`, leyenda en `text-fg-muted` y error en línea.
  - `frontend/components/agent/agent-composer.tsx`: `<textarea>` auto-ajustable hasta ~6 líneas, `Enter` envía y `Shift+Enter` inserta salto de línea, botón `ArrowUp` deshabilitado si está vacío o esperando, conteo por puntos de código (`Array.from(value).length`) mostrando `"N/4000"` desde 3500 y bloqueando `> 4000`, envío siempre con `timezone` del navegador y error junto al composer.
- **3.8 Calendario — `?publication={id}` (`frontend/components/publications/calendar-view.tsx`)**:
  - Abre `PublicationDetailDialog` al entrar a `/accounts/{accountId}/publications?publication={id}` reutilizando la publicación del rango cargado o pidiéndola con `usePublication`, y limpia `publication` de la URL con `router.replace` al cerrar el diálogo (o el aviso de error si no existe).
- **4. Tests (`msw`)**:
  - `frontend/components/shell/nav.test.tsx`: verifica la presencia, orden (justo después de `"Calendario"`) y activación de `"Agente"` en `/agent` y `/agent/{id}`.
  - `frontend/components/publications/calendar-view.test.tsx`: verifica la apertura del detalle desde `?publication=`, el pedido a `GET /publications/{id}` fuera de rango y la limpieza del query param al cerrar.
  - `frontend/components/agent/agent-chat.test.tsx`: 13 tests con `msw` (`onUnhandledRequest: "error"`) cubriendo lista de chats sin recarga al navegar, estado vacío de lista, borrado con confirmación, creación de chat desde sugerencia y desde composer (`timezone`, burbuja optimista, `"Pensando…"`, `setQueryData` sin segundo `GET`), filas `tool` y link `"Ver en el calendario"`, contador `N/4000` (con puntos de código Unicode y bloqueo `> 4000`), confirmar/cancelar en `PendingActionCard` (incluyendo `cancel_publication` e invalidación de publicaciones), errores `502` / `409` / `422` / `503`, `enabled: false` y `can_write: false`.
  - `frontend/vitest.setup.ts`: configurado `asyncUtilTimeout: 4000` en Testing Library (debajo del `testTimeout` de 5000 ms de Vitest) para evitar falsos negativos por contención de CPU al correr los 84 archivos en paralelo.

### Qué quedó pendiente / fuera de alcance

- Ningún punto de las secciones 2 a 4 del frontend quedó pendiente, y el contrato de la sección 2 cubrió todos los datos necesarios sin inventar campos ni rutas.
- Queda fuera del alcance de esta rama: el backend en `feat/agent-chat` (a cargo de Claude), la prueba integrada en navegador contra el backend real una vez unidas ambas ramas, y los puntos listados en **Fuera de alcance** (streaming, adjuntar o subir medios en el chat, generar imágenes/videos, selector de canales a la derecha, herramientas de bandeja/contactos, 👍/👎 y renombrar chats).

### Qué se revisó a mano

- Revisión visual de `docs/design-neon/postiz/03-agente.jpg` junto con `docs/design-neon/DESIGN.md`, `frontend/DESIGN-SYSTEM.md` y los componentes de referencia (`inbox-shell.tsx`, `conversation-list.tsx`, `message-bubble.tsx`, `message-composer.tsx`, `network-icon.tsx`, `calendar-view.tsx`, `publication-detail-dialog.tsx`, `publications.ts`, `profile.ts`).
- Verificación del cumplimiento de las notas de revisiones anteriores: cero modificadores de opacidad `color/NN` sobre variables CSS del tema en todo el diff, fechas formateadas en hora local del navegador y envío de `timezone`, conteo por puntos de código (`Array.from`), permisos regidos por `can_write`, y errores del backend visibles junto al composer o la tarjeta de confirmación.
- Revisión de `git diff 70eb722..HEAD --stat` confirmando que solo se modificaron archivos dentro de `frontend/` y `PLAN.agent-chat.md` (sin tocar backend, `.env*` ni `package.json`).

### Salida completa de los comandos de verificación

#### 1. `npm run typecheck`

```text
> alostudio-frontend@0.1.0 typecheck
> tsc --noEmit
```

#### 2. `npm run lint`

```text
> alostudio-frontend@0.1.0 lint
> next lint

`next lint` is deprecated and will be removed in Next.js 16.
For new projects, use create-next-app to choose your preferred linter.
For existing projects, migrate to the ESLint CLI:
npx @next/codemod@canary next-lint-to-eslint-cli .

✔ No ESLint warnings or errors
```

#### 3. `npm test`

```text

> alostudio-frontend@0.1.0 test
> vitest run


 RUN  v2.1.9 C:/Users/Zeek/Desktop/AloStudio-agent-ui/frontend

 ✓ lib/inboxes/email-blocks.test.ts (15 tests) 16ms
 ✓ components/publications/network-rules.test.ts (3 tests) 12ms
 ✓ components/reports/summary-table.test.tsx (3 tests) 375ms
 ✓ components/publications/media-library-view.test.tsx (3 tests) 2574ms
   ✓ MediaLibraryView > sube un archivo válido y muestra el 422 del backend si se intenta borrar uno en uso 2200ms
 ✓ components/publications/analytics-view.test.tsx (3 tests) 2578ms
   ✓ PublicationsAnalyticsView > muestra tarjetas de totales, '—' para cifras ausentes (y '0' cuando viene 0), desglose por canal y mejores publicaciones 2178ms
 ✓ components/publications/publication-detail-dialog.test.tsx (2 tests) 2695ms
   ✓ PublicationDetailDialog > muestra cifras, 'actualizado hace…', error del destino y link, y oculta acciones a un agente 334ms
   ✓ PublicationDetailDialog > habilita Reintentar y Actualizar estadísticas para un administrador en partially_published y Borrar en failed 2353ms
 ✓ components/instagram/post-reply-picker.test.tsx (11 tests) 2871ms
   ✓ PostReplyPicker > offers to save only after something changed 505ms
   ✓ PostReplyPicker > discards an edit without sending it 1511ms
 ✓ components/conversations/conversation-list.test.tsx (4 tests) 2800ms
   ✓ ConversationList > renders conversations returned by the API 2229ms
 ✓ components/instagram/instagram-connection.test.tsx (8 tests) 2863ms
   ✓ InstagramConnection — vuelta del OAuth > nombra la cuenta recién conectada 2039ms
 ✓ components/settings/signatures/signatures-view.test.tsx (2 tests) 3136ms
   ✓ SignaturesView > lista firmas, crea (cuerpo correcto y conteo de puntos de código), edita y borra 2870ms
 ✓ components/agenda/week-view.test.tsx (3 tests) 3041ms
   ✓ WeekView > renders Monday-to-Sunday columns and groups appointments by local day in chronological order 2260ms
   ✓ AgendaView > loads the current week in weekly view, navigates weeks, and filters by status 645ms
 ✓ components/contacts/contacts-view.test.tsx (4 tests) 3207ms
   ✓ ContactsView > filters the list when a company chip is clicked 2362ms
   ✓ ContactsView > applies an advanced filter via the builder 322ms
 ✓ components/settings/inboxes/email-transport-panel.test.tsx (13 tests) 3452ms
   ✓ EmailTransportPanel > sends the IMAP settings that make mail arrive 2108ms
 ✓ components/settings/autoposts/autoposts-view.test.tsx (2 tests) 3314ms
   ✓ AutopostsView > lista feeds con revisado hace y último error, prueba el feed (entradas y error 422), crea, edita y borra 3264ms
stderr | components/settings/inboxes/email-template-panel.test.tsx > EmailTemplatePanel, the visual designer > saves the generated HTML together with its settings
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined

 ✓ components/settings/sets/sets-view.test.tsx (2 tests) 3343ms
   ✓ SetsView > lista sets con canales y fecha, crea en modo set con el editor, edita y borra 3307ms
stderr | components/settings/inboxes/email-template-panel.test.tsx > EmailTemplatePanel, the visual designer > saves the generated HTML together with its settings
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined

 ✓ components/settings/inboxes/email-template-panel.test.tsx (15 tests) 3608ms
   ✓ EmailTemplatePanel > saves the authored HTML 399ms
   ✓ EmailTemplatePanel > refuses a template that would send an empty message 2014ms
stderr | components/settings/inboxes/email-template-panel.test.tsx
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined

stderr | VirtualConsole.<anonymous> (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\virtual-console.js:29:45)
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\email-templates.ts:27:19) undefined

 ✓ components/settings/plugs/plugs-view.test.tsx (3 tests) 4013ms
   ✓ PlugsView > sin canales compatibles muestra 'Conectá Threads para usar acciones automáticas' con link al calendario 2306ms
   ✓ PlugsView > pide mensaje solo cuando la acción tiene message_max, cuenta UTF-8 de Threads y permite listar, crear, editar y borrar 1445ms
 ✓ components/instagram/post-autoreply-rules.test.tsx (17 tests) 4310ms
   ✓ PostAutoreplyRules > saves a keyword rule 359ms
   ✓ PostAutoreplyRules > saves a catch-all rule 2122ms
   ✓ PostAutoreplyRules > re-reads the list after saving, so the rule replaces the empty state 322ms
 ✓ components/settings/email-templates/email-templates-view.test.tsx (15 tests) 4518ms
   ✓ Plantillas de correo > una plantilla nueva nace con el diseño por defecto, no en blanco 2096ms
 ✓ components/agent/agent-chat.test.tsx (13 tests) 4417ms
   ✓ Agente — lista de chats y navegación sin recarga > muestra los chats, la etiqueta 'Por confirmar', no recarga la lista al cambiar de chat y permite borrar con confirmación 2757ms
   ✓ Agente — enviar un mensaje, burbuja optimista, 'Pensando…' y composer > muestra la burbuja optimista y 'Pensando…' al enviar y luego los reemplaza por el Chat devuelto 350ms
 ✓ components/publications/calendar-view.test.tsx (6 tests) 6345ms
   ✓ CalendarView — grilla, paginación y estados > ubica cada publicación en su día y hora local, pide todas las páginas del rango y pinta el estado 2916ms
   ✓ CalendarView — conexión de canales y avisos de query > 'Agregar canal' con una red authorize pide authorize_url sin cuerpo y navega a ella 572ms
   ✓ CalendarView — conexión de canales y avisos de query > 'Agregar canal' con una red form abre el diálogo, envía { fields } y muestra el 422 sin cerrarlo 447ms
   ✓ CalendarView — abrir publicación desde ?publication= > pide la publicación con usePublication si no está en el rango cargado, abre el detalle y limpia la URL al cerrarlo 2087ms
 ✓ components/conversations/inbox-three-column.test.tsx (4 tests) 3443ms
   ✓ Bandeja en tres columnas y pestañas > muestra lista y estado vacío juntos, y cambia entre conversaciones sin recargar la lista 1126ms
   ✓ Bandeja en tres columnas y pestañas > muestra el resumen de reportes de la bandeja y la lista de canales conectados 1035ms
   ✓ Bandeja en tres columnas y pestañas > a un agente le muestra los canales sin Conectar ni Desconectar 1195ms
 ✓ components/publications/publication-editor-dialog.test.tsx (5 tests) 6922ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > arma el cuerpo de publicación programada con fecha ISO, media_id reordenados, post_type y content_override 3521ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > arma borrador (draft: true) y respeta post_type: 'reels' en Instagram 474ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > muestra errores de la tabla de reglas antes de enviar y muestra el 422 del backend con message y errors[] 367ms
   ✓ PublicationEditorDialog — firmas y sets > 'Usar set' carga texto, medios y canales activos (ignorando channel: null) sin cambiar la fecha, y 'Guardar como set' envía el cuerpo esperado 2414ms
 ✓ components/settings/inboxes/email-branding-panel.test.tsx (7 tests) 501ms
 ✓ middleware.test.ts (7 tests) 38ms
 ✓ components/settings/assignment-policies/assignment-policies-view.test.tsx (3 tests) 645ms
   ✓ AssignmentPoliciesView > creates a policy, wrapping the body in assignment_policy 316ms
 ✓ components/conversations/email-message.test.tsx (9 tests) 339ms
 ✓ lib/inboxes/email-template-design.test.ts (12 tests) 18ms
 ✓ components/instagram/connect-capabilities-dialog.test.tsx (6 tests) 346ms
 ✓ components/conversations/email-composer.test.tsx (8 tests) 523ms
 ✓ lib/api/notifications.test.tsx (3 tests) 321ms
 ✓ components/conversations/conversation-filters.test.tsx (3 tests) 890ms
   ✓ ConversationFilters > builds an equal_to condition from the default row 308ms
   ✓ ConversationFilters > saves the current filter as a named view 325ms
 ✓ components/settings/integrations/integration-app-view.test.tsx (2 tests) 2607ms
   ✓ IntegrationAppView connect > renders an OAuth link for external-action apps 2453ms
stderr | components/reports/reports-view.test.tsx > ReportsView > offers CSV + Excel export links for the current scope
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5) undefined

 ✓ components/reports/reports-view.test.tsx (2 tests) 2946ms
   ✓ ReportsView > renders live counters and summary metrics 2671ms
stderr | VirtualConsole.<anonymous> (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\virtual-console.js:29:45)
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-agent-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5) undefined

 ✓ components/settings/installation/installation-view.test.tsx (6 tests) 2817ms
   ✓ Configuración de la instalación > distingue lo configurado de lo que falta 2445ms
 ✓ components/reports/metric-chart.test.tsx (6 tests) 134ms
 ✓ components/settings/inboxes/channel-form.test.tsx (4 tests) 2899ms
   ✓ ChannelForm, creating an email inbox > draws a checkbox for a boolean field, not a text box 2508ms
 ✓ components/settings/automation/automation-rules-view.test.tsx (3 tests) 204ms
 ✓ components/conversations/conversation-participants.test.tsx (3 tests) 377ms
 ✓ components/settings/profile/profile-view.test.tsx (1 test) 243ms
 ✓ components/settings/mcp-tokens/mcp-tokens-view.test.tsx (2 tests) 464ms
 ✓ components/instagram/autoreply-view.test.tsx (4 tests) 368ms
 ✓ components/help-center/portal-detail-view.test.tsx (3 tests) 480ms
 ✓ components/shell/nav.test.tsx (4 tests) 256ms
 ✓ components/conversations/ai-handoff.test.tsx (4 tests) 392ms
 ✓ components/settings/macros/macros-view.test.tsx (4 tests) 193ms
 ✓ lib/api/reports-gaps.test.ts (6 tests) 8ms
 ✓ lib/api/fetcher.test.ts (5 tests) 11ms
 ✓ components/ui/tabs.test.tsx (3 tests) 210ms
 ✓ components/campaigns/campaigns-view.test.tsx (1 test) 206ms
 ✓ components/conversations/message-composer-canned.test.tsx (2 tests) 227ms
 ✓ lib/realtime/cable.test.ts (3 tests) 8ms
 ✓ components/settings/csat/csat-view.test.tsx (1 test) 2752ms
   ✓ CsatView > renders metrics cards and responses 2746ms
 ✓ components/settings/custom-attributes/custom-attributes-view.test.tsx (1 test) 187ms
 ✓ components/instagram/comments-panel.test.tsx (2 tests) 290ms
 ✓ lib/api/errors.test.ts (8 tests) 7ms
 ✓ components/reports/traffic-heatmap.test.tsx (3 tests) 301ms
 ✓ components/settings/agents/agents-view.test.tsx (1 test) 389ms
   ✓ AgentsView > lists agents with role + pending badge + email 380ms
 ✓ components/campaigns/campaign-analytics-panel.test.tsx (1 test) 212ms
 ✓ components/shell/page-header.test.tsx (2 tests) 201ms
 ✓ components/settings/canned-responses/canned-responses-view.test.tsx (2 tests) 749ms
   ✓ CannedResponsesView > lists responses with their short codes and content 328ms
   ✓ CannedResponsesView > sends the debounced search term to the backend 415ms
 ✓ components/conversations/conversation-actions.test.tsx (1 test) 326ms
   ✓ ConversationActions macros > runs the picked macro on the current conversation 318ms
 ✓ components/help-center/articles-panel.test.tsx (2 tests) 1857ms
   ✓ ArticlesPanel search > sends the debounced query to the articles endpoint 549ms
   ✓ ArticlesPanel search > clears the search with the reset button 1267ms
 ✓ components/settings/integrations/integrations-view.test.tsx (1 test) 2648ms
   ✓ IntegrationsView > lists apps with connection status 2634ms
 ✓ components/help-center/portals-view.test.tsx (1 test) 825ms
   ✓ PortalsView > lists portals with archived badge and custom domain 725ms
 ✓ components/settings/agent-bots/agent-bots-view.test.tsx (1 test) 179ms
 ✓ lib/api/uploads.test.ts (3 tests) 59ms
 ✓ components/settings/webhooks/webhooks-view.test.tsx (1 test) 194ms
 ✓ components/products/products-view.test.tsx (1 test) 176ms
 ✓ components/settings/labels/labels-view.test.tsx (1 test) 1981ms
   ✓ LabelsView > lists labels with description and shows the new-label button 1949ms
 ✓ components/conversations/channel-badge.test.tsx (5 tests) 2498ms
   ✓ ChannelBadge > names the channel for anyone not reading colour 2466ms
 ✓ components/settings/teams/teams-view.test.tsx (1 test) 2547ms
   ✓ TeamsView > lists teams, marks membership, and flags auto-assign off 2542ms
 ✓ components/conversations/message-composer.test.tsx (1 test) 150ms
 ✓ app/privacidad/page.test.tsx (3 tests) 249ms
 ✓ components/ui/button.test.tsx (3 tests) 183ms
 ✓ lib/api/instagram.test.tsx (1 test) 127ms
 ✓ components/help-center/portal-form.test.tsx (1 test) 239ms
 ✓ components/settings/notifications/push-toggle.test.tsx (1 test) 160ms
 ✓ lib/time.test.ts (4 tests) 6ms
 ✓ lib/auth/schemas.test.ts (3 tests) 6ms
 ✓ components/crm/crm-tabs.test.tsx (1 test) 113ms
 ✓ components/reports/bot-metrics-cards.test.tsx (1 test) 77ms
 ✓ app/terminos/page.test.tsx (2 tests) 151ms
 ✓ app/eliminacion-de-datos/page.test.tsx (2 tests) 125ms

 Test Files  84 passed (84)
      Tests  344 passed (344)
   Start at  13:48:42
   Duration  39.31s (transform 9.19s, setup 130.86s, collect 124.38s, tests 112.49s, environment 403.34s, prepare 30.58s)
```

### Revisión de Claude (2026-10-30)

- Corrí de nuevo los tres comandos sobre `5b1a02d`: typecheck y lint sin errores, 84 archivos y 344 tests en verde. Se cumplieron las notas de las revisiones anteriores (sin `color/NN`, `can_write` oculta lo que el backend niega, errores junto a lo que los provocó).
- Probé backend y pantalla juntos en el navegador, con un OpenAI simulado en local: chat nuevo, "Consultó tus canales", una propuesta inválida (Instagram sin imagen) que vuelve al modelo sin llegar al usuario, la propuesta corregida en la tarjeta ("Sale el sáb 31 oct, 10:00": la hora sin zona del modelo se lee en la del navegador), confirmar, "Ver en el calendario" abriendo el detalle con `?publication=`, la etiqueta "Por confirmar" en la lista, la vista angosta con el botón "Chats", y un usuario agente (nota de solo lectura, sin la sugerencia de armar, sin ver los chats de otros).
- Corregido en `9f3d7ea`: si el primer mensaje de un chat nuevo daba 502, la pantalla volvía al estado vacío aunque el chat había quedado guardado; el backend ahora devuelve `thread_id` y la pantalla lo muestra (con test). El botón de borrar un chat solo aparecía con el mouse: en pantallas angostas queda siempre visible.
- Sin tocar: `vitest.setup.ts` sube la espera de Testing Library a 4 s para todos los tests (`876cd29`); ayuda con la CPU cargada y solo demora los fallos.
