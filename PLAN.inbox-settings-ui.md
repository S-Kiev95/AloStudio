# PLAN — Bandeja en tres columnas y ajustes de publicación

Segundo plan de frontend de la salida de Postiz (Fase 7), **después** de `PLAN.publishing-ui.md` (calendario, editor, medios, estadísticas y menú lateral). Se arranca desde `main` con ese plan ya integrado. El backend de todo lo de abajo ya existe.

Rama `feat/inbox-settings-ui`, worktree `C:\Users\Zeek\Desktop\AloStudio-inbox-ui`. **Solo frontend.** Lo hace un agente y lo revisa Claude contra este documento.

## Insumos

- `docs/design-neon/postiz/`: capturas de la versión anterior del producto, la referencia que quiere el dueño. Para este plan: `06-bandeja-lista.jpg`, `07-bandeja-conversacion.jpg`, `09-bandeja-reportes.jpg`, `10-bandeja-canales.jpg`, `12-ajustes-generales.png`, `13-ajustes-agentes.jpg`, `16-ajustes-autopost.jpg`, `17-ajustes-sets.jpg`, `18-ajustes-firmas.jpg`, `20-ajustes-plugs.jpg`. Copiá disposición, espaciado y jerarquía; textos en español y con lo que hace AloStudio.
- `docs/design-neon/DESIGN.md`, `frontend/DESIGN-SYSTEM.md` y los componentes de `frontend/components/ui/`.

## Reglas para el agente

Las mismas de `PLAN.publishing-ui.md` (worktree propio, no leer Postiz ni el repo principal, sin backend, sin push ni ssh, sin `.env`, sin bases, sin librerías nuevas, commits chicos con `Co-Authored-By: Antigravity <noreply@google.com>`, sección **Estado** con la salida real de `npm run typecheck`, `npm run lint` y `npm test`).

## 1. Bandeja en tres columnas

Hoy `/conversations` es una lista a todo el ancho y `/conversations/[id]` una pantalla aparte (conversación + `ContactPanel` a la derecha en pantallas grandes). Pasa a ser una sola vista, como `07-bandeja-conversacion.jpg`:

- **Izquierda (~320 px):** la lista (`components/conversations/conversation-list.tsx`) en versión compacta: avatar con iniciales, nombre, ícono del canal, última línea del mensaje, fecha corta y burbuja de no leídos. Arriba: pestañas Todas / Míos / Sin asignar con su cantidad, buscador, pastillas Abiertas / Resueltas / Pendientes / Todas y selector de bandeja de entrada. La conversación abierta queda marcada.
- **Centro:** la conversación (`conversation-view.tsx`). Encabezado con avatar, nombre, `#id`, estado y botón **Resolver**; debajo, una fila con Asignado, Equipo y "+ Etiqueta". Mensajes en burbujas: los del contacto a la izquierda en superficie neutra, los del equipo a la derecha con el color primario, con autor y hora debajo; notas privadas con su estilo propio. Abajo, el editor con "Nota privada", "Respuestas rápidas" (las `/` de hoy), adjuntar y **Enviar**.
- **Derecha (~280 px):** el panel del contacto (`contact-panel.tsx`): avatar grande, nombre, estado, email, teléfono, atributos personalizados.
- Sin conversación elegida: "Elegí una conversación para empezar" en el centro.
- Rutas: `/conversations` y `/conversations/[id]` usan el mismo layout de tres columnas (un `layout.tsx` con la lista que no se recarga al cambiar de conversación). En pantallas chicas, una columna por vez con "volver" como hoy.
- No cambies cómo se cargan ni se mandan los mensajes: es una reorganización visual de los componentes que ya existen.

## 2. Pestañas de la bandeja

Arriba de la bandeja, `NavTabs` como en `06-bandeja-lista.jpg`: **Conversaciones** | **Reportes** | **Canales**.

- Reportes: un resumen como `09-bandeja-reportes.jpg` (abiertas, resueltas, pendientes, mensajes de hoy, contactos, agentes conectados, mensajes de los últimos 7 días) con los datos que ya usa `components/reports/` y `components/overview/`. Un link a la pantalla completa de Reportes.
- Canales: la lista de bandejas de entrada conectadas como `10-bandeja-canales.jpg`, con "Conectar canal", "Detalles de conexión" y "Desconectar" usando lo que ya hace `components/settings/inboxes/`.
- Los contactos viven en CRM (plan anterior): no los dupliques acá.

## 3. Ajustes de publicación

En `components/settings/settings-sidebar.tsx`, un grupo "Publicación" con estas páginas nuevas en `app/accounts/[accountId]/settings/`:

**Firmas** (`signatures/`), como `18-ajustes-firmas.jpg`: lista de firmas y "Agregar firma" en un diálogo con el texto y "¿Agregar sola a cada publicación nueva?". `GET/POST /publications/signatures`, `PATCH/DELETE /publications/signatures/{id}`.

```ts
type Signature = { id: number; content: string; auto_add: boolean; created_at: string | null; updated_at: string | null };
// POST { content: string (1–2000), auto_add?: boolean } · PATCH { content?, auto_add? }
// Marcar una con auto_add saca la marca de la anterior (lo hace el backend; refrescá la lista).
```

**Sets** (`sets/`), como `17-ajustes-sets.jpg`: lista con nombre, canales (avatares) y fecha; "Agregar set" abre el editor de publicaciones del plan anterior en modo set (sin fecha, con "Guardar set" en vez de publicar). Editar y borrar. `GET/POST /publications/sets`, `PATCH/DELETE /publications/sets/{id}` (tipos en `PLAN.publishing-ui.md`).

**Auto post** (`autoposts/`), como `16-ajustes-autopost.jpg`: lista con nombre, URL, activo, "revisado hace…" y el último error si hay. Diálogo con nombre, URL del feed con botón **Probar** (muestra las 5 entradas más nuevas), "¿Qué hacer con cada entrada nueva?" (Publicar enseguida / Guardar como borrador), canales (todos o algunos), "Publicar también la última entrada que ya está en el feed" y activo.

```ts
type Autopost = {
  id: number; name: string; feed_url: string; mode: "publish" | "draft"; active: boolean;
  start_with_latest: boolean; channel_ids: number[]; // vacío = todos los canales
  last_checked_at: string | null; last_error: string | null; created_at: string | null; updated_at: string | null;
};
// GET/POST /publications/autoposts · PATCH/DELETE /publications/autoposts/{id}
// POST /publications/autoposts/preview { feed_url } → { items: { title, link, image_url, published_at }[] }
// Una URL que no es un feed (o apunta a una red privada) → 422 con message.
```

**Plugs** (`plugs/`), como `20-ajustes-plugs.jpg`: por cada canal que tenga acciones en el catálogo, sus plugs con umbral, mensaje, activo y las últimas corridas (bien / falló con el motivo). Diálogo: canal, acción (del catálogo de su red), "cuando llegue a N me gusta" y el mensaje si la acción lo pide (con contador contra `message_max`). Sin canales compatibles: "Conectá Threads para usar acciones automáticas" con link al calendario.

```ts
type PlugKind = { kind: string; label: string; description: string; message_max: number | null };
// GET /publications/plugs/catalog → { network: string; kinds: PlugKind[] }[]
type Plug = {
  id: number; channel_id: number; kind: string; likes_threshold: number; message: string | null; active: boolean;
  runs: { target_id: number; ok: boolean; error_message: string | null; ran_at: string | null }[];
  created_at: string | null; updated_at: string | null;
};
// GET/POST /publications/plugs { channel_id, kind, likes_threshold (≥1), message?, active? }
// PATCH /publications/plugs/{id} { likes_threshold?, message?, active? } · DELETE /publications/plugs/{id}
```

**API y MCP**: la página actual "Tokens MCP" pasa a llamarse "API y MCP", con un texto como el de `13-ajustes-agentes.jpg` que explica para qué sirve un token (conectar el agente de IA, n8n u otras herramientas a AloStudio). La funcionalidad no cambia.

Todas: escritura solo administrador (agentes ven), 422 con `message` mostrados tal cual, un hook de react-query por consulta o mutación en `lib/api/`.

## 4. Tests

Con Vitest y `fetch` simulado: la bandeja muestra lista y conversación juntas y cambia de conversación sin recargar la lista; cada pantalla de ajustes lista, crea (cuerpo correcto), edita y borra; "Probar" del auto post muestra las entradas o el error; el plug pide mensaje solo cuando la acción tiene `message_max`.

## Fuera de alcance

Cambios de backend, la pantalla de chat del agente de IA, videos con IA, apps OAuth, cambios en cómo se envían o reciben mensajes. Anotá en **Estado** lo que parezca necesario.

## Terminado cuando

`npm run typecheck`, `npm run lint` y `npm test` pasan, cada sección está hecha o explicada en **Estado**, y **Estado** está completo.

## Estado

_(lo completa el agente al terminar)_
