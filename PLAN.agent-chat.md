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
| 502 | OpenAI falló o tardó demasiado | Mostrar `message` cerca del composer. El mensaje del usuario **quedó guardado**: volvé a pedir el chat en vez de reponer el texto en el composer. |
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

(Lo completa el agente del frontend al terminar.)
