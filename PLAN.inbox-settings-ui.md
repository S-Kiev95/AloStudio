# PLAN — Bandeja en tres columnas y ajustes de publicación

Segundo plan de frontend de la salida de Postiz (Fase 7), **después** de `PLAN.publishing-ui.md` (calendario, editor, medios, estadísticas y menú lateral). Se arranca desde `main` con ese plan ya integrado. El backend de todo lo de abajo ya existe.

Rama `feat/inbox-settings-ui`, worktree `C:\Users\Zeek\Desktop\AloStudio-inbox-ui`. **Solo frontend.** Lo hace un agente y lo revisa Claude contra este documento.

## Insumos

- `docs/design-neon/postiz/`: capturas de la versión anterior del producto, la referencia que quiere el dueño. Para este plan: `06-bandeja-lista.jpg`, `07-bandeja-conversacion.jpg`, `09-bandeja-reportes.jpg`, `10-bandeja-canales.jpg`, `12-ajustes-generales.png`, `13-ajustes-agentes.jpg`, `16-ajustes-autopost.jpg`, `17-ajustes-sets.jpg`, `18-ajustes-firmas.jpg`, `20-ajustes-plugs.jpg`. Copiá disposición, espaciado y jerarquía; textos en español y con lo que hace AloStudio.
- `docs/design-neon/DESIGN.md`, `frontend/DESIGN-SYSTEM.md` y los componentes de `frontend/components/ui/`.

## Reglas para el agente

Las mismas de `PLAN.publishing-ui.md` (worktree propio, no leer Postiz ni el repo principal, sin backend, sin push ni ssh, sin `.env`, sin bases, sin librerías nuevas, commits chicos con `Co-Authored-By: Antigravity <noreply@google.com>`, sección **Estado** con la salida real de `npm run typecheck`, `npm run lint` y `npm test`).

## Notas de la revisión del plan anterior (cumplilas)

- **Sin modificadores de opacidad sobre colores del tema** (`bg-danger/10`, `border-warning/30`, `bg-backdrop/75`, `bg-primary/60`…). Los colores son `var(--…)` con un hex adentro y Tailwind 3 no genera ninguna regla para esas clases: quedan transparentes. Al gráfico de estadísticas del plan anterior le pasó eso. Usá tokens sólidos (`bg-surface-2`, `bg-focused`, `bg-field`, `border-glass`, `text-danger`…) o `opacity-*`.
- **Largo de texto como el backend**, nunca `.length`. `components/publications/network-rules.ts` exporta `textLength(network, text)`: puntos de código, y en Threads cada emoji por sus bytes UTF-8. Usala para el mensaje de un plug, con la red del canal: es como lo va a contar la red al publicarlo. Para la firma (1–2000), `Array.from(texto).length`.
- **Fechas**: si mandás un instante, que sea ISO con zona (`toISOString()` de una fecha local). Nunca `YYYY-MM-DD` suelto.
- **Reutilizá antes de copiar**: `MetricChart` (`components/reports/metric-chart.tsx`), `PublicationEditorDialog` (en modo set, para "Agregar set" y editar), `PublicationErrorAlert`, `parsePublicationError`, `useIsAccountAdmin` y `NavTabs`.
- En un diálogo largo, si el error del backend queda lejos del botón que lo provocó, llevalo a la vista (como hace hoy el editor de publicaciones).
- Cada commit tiene que contener todo el cambio que describe su mensaje.

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

### Qué se hizo

- **1. Bandeja en tres columnas**:
  - `frontend/components/conversations/inbox-shell.tsx` y grupo de rutas `frontend/app/accounts/[accountId]/conversations/(inbox)/{layout.tsx,page.tsx,[id]/page.tsx}`: unificación de `/conversations` y `/conversations/[id]` bajo un único layout persistente que mantiene `ConversationList` montada (~320 px a la izquierda) sin recargar la lista al cambiar de conversación, muestra `"Elegí una conversación para empezar"` centrado cuando no hay conversación abierta y alterna de a una columna con `"Volver"` en pantallas chicas.
  - `frontend/components/conversations/conversation-list.tsx` y `frontend/lib/api/conversations.ts`: versión compacta de filas con avatar de iniciales (`Avatar` ampliado a dos iniciales y tamaño `xl`), nombre, ícono de canal, última línea de mensaje, fecha corta y burbuja de no leídos; pestañas superiores **Todas / Míos / Sin asignar** con contadores, buscador, pastillas **Abiertas / Resueltas / Pendientes / Todas**, selector de bandeja de entrada (`inbox_id`) y resaltado `aria-current="page"` de la conversación abierta.
  - `frontend/components/conversations/{conversation-view,conversation-actions,message-bubble,message-composer,contact-panel,conversation-participants,ai-handoff,email-message}.tsx`: encabezado con avatar, nombre, `#id`, estado y botón **Resolver**, segunda fila con Asignado, Equipo (`useAssignTeam`) y **+ Etiqueta**, burbujas diferenciadas (contacto en superficie neutra a la izquierda, equipo en color primario a la derecha, notas privadas con superficie propia, autor y hora debajo), editor inferior con **Nota privada**, **Respuestas rápidas**, adjuntar y **Enviar**, y `ContactPanel` (~280 px a la derecha) con avatar grande, nombre, estado, email, teléfono y atributos personalizados compartiendo la caché de conversaciones abiertas (`refetchOnMount: false`) para no disparar recargas al cambiar de chat.
- **2. Pestañas de la bandeja**:
  - `frontend/components/conversations/inbox-tabs.tsx` y `frontend/app/accounts/[accountId]/conversations/layout.tsx`: `NavTabs` encima de la bandeja con **Conversaciones** | **Reportes** | **Canales** (sin duplicar Contactos, que viven en CRM).
  - `frontend/components/conversations/inbox-reports-view.tsx` y `frontend/app/accounts/[accountId]/conversations/reports/page.tsx`: resumen con abiertas, resueltas, pendientes, mensajes de hoy, contactos, agentes conectados, gráfico de mensajes de los últimos 7 días reutilizando `MetricChart` y enlace a `/accounts/{accountId}/reports`.
  - `frontend/components/conversations/inbox-channels-view.tsx` y `frontend/app/accounts/[accountId]/conversations/channels/page.tsx`: lista de bandejas conectadas con **Conectar canal**, **Detalles de conexión** y **Desconectar** reutilizando los hooks y rutas de `inboxes`.
- **3. Ajustes de publicación**:
  - `frontend/lib/api/publications.ts`: un hook de React Query por consulta o mutación para firmas (`usePublicationSignatures`, `useCreatePublicationSignature`, `useUpdatePublicationSignature`, `useDeletePublicationSignature`), sets (`usePublicationSets`, `useCreatePublicationSet`, `useUpdatePublicationSet`, `useDeletePublicationSet`), auto post (`usePublicationAutoposts`, `useCreatePublicationAutopost`, `useUpdatePublicationAutopost`, `useDeletePublicationAutopost`, `usePreviewPublicationAutopost`) y plugs (`usePublicationPlugsCatalog`, `usePublicationPlugs`, `useCreatePublicationPlug`, `useUpdatePublicationPlug`, `useDeletePublicationPlug`).
  - `frontend/components/settings/settings-sidebar.tsx`: nuevo grupo **Publicación** (**Firmas**, **Sets**, **Auto post**, **Plugs**) y renombrado de `mcp_tokens` a **API y MCP**.
  - **Firmas** (`frontend/components/settings/signatures/signatures-view.tsx`, `settings/signatures/page.tsx`): listado con marca `Automática`, acciones de administrador (`useIsAccountAdmin`, agentes solo lectura), diálogo con contador de puntos de código `Array.from(texto).length / 2000` y casilla `"¿Agregar sola a cada publicación nueva?"`.
  - **Sets** (`frontend/components/settings/sets/sets-view.tsx`, `settings/sets/page.tsx`, `publication-editor-dialog.tsx`): listado `Sets (N)` con nombre, avatares de canales y fecha; **Agregar set** y **Editar** reutilizan `PublicationEditorDialog` en `mode="set"` (sin selector de fecha y con botón **Guardar set**).
  - **Auto post** (`frontend/components/settings/autoposts/autoposts-view.tsx`, `settings/autoposts/page.tsx`): listado con nombre, URL, estado activo/pausado, `"Revisado hace…"` y `last_error` si existe; diálogo con botón **Probar** (muestra hasta las 5 entradas más nuevas o el 422 del backend), modo (`Publicar enseguida` / `Guardar como borrador`), canales (todos o algunos), `"Publicar también la última entrada que ya está en el feed"` y `"Activo"`.
  - **Plugs** (`frontend/components/settings/plugs/plugs-view.tsx`, `settings/plugs/page.tsx`): cruce de canales con `/publications/plugs/catalog`; estado vacío `"Conectá Threads para usar acciones automáticas"` con link al calendario cuando no hay canales compatibles; listado por canal con umbral, mensaje, estado y últimas corridas (`Bien` / `Falló` con motivo); diálogo que muestra el campo de mensaje **únicamente** cuando `message_max !== null` y cuenta caracteres con `textLength(network, text)`.
  - **API y MCP** (`frontend/components/settings/mcp-tokens/mcp-tokens-view.tsx`, `secret-reveal.tsx`): título actualizado a **API y MCP** y texto explicativo para conectar el agente de IA, n8n, CLI u otras herramientas externas sin alterar la funcionalidad existente.
  - Cumplimiento estricto de las **Notas de la revisión del plan anterior**: cero modificadores de opacidad `/NN` sobre colores del tema en todos los archivos tocados, scroll automático de errores (`scrollIntoView`) en diálogos, conteo exacto de texto (`textLength` / `Array.from`), fechas ISO con zona y preservación textual de `message` en respuestas 422.
- **4. Tests**:
  - `frontend/components/conversations/inbox-three-column.test.tsx`: verifica que lista, conversación y panel de contacto se muestran juntos, que el estado vacío aparece sin selección, que cambiar de conversación actualiza la vista central y el contacto sin volver a pedir `GET /conversations`, y cubre `InboxTabs`, `InboxReportsView` e `InboxChannelsView`.
  - `frontend/components/settings/signatures/signatures-view.test.tsx`, `sets/sets-view.test.tsx`, `autoposts/autoposts-view.test.tsx`, `plugs/plugs-view.test.tsx` y `mcp-tokens/mcp-tokens-view.test.tsx`: cubren listado, creación (verificando el cuerpo enviado), edición, borrado, modo solo lectura para agentes, errores 422, **Probar** del auto post (entradas y error 422) y aparición condicional del mensaje en plugs solo cuando la acción define `message_max` con conteo UTF-8 en Threads.

### Qué quedó pendiente / fuera de alcance

- Ningún punto de las secciones 1 a 4 quedó pendiente.
- Se respetó estrictamente **Fuera de alcance**: sin cambios de backend, sin pantalla de chat del agente de IA, sin generación de videos con IA, sin apps OAuth y sin cambios en la lógica de carga/envío de mensajes.
- No se levantaron bases de datos ni servidores contra entorno real; la verificación visual interactiva en navegador con sesión real queda para la revisión posterior.

### Qué se revisó a mano

- Contraste visual contra las capturas `06-bandeja-lista.jpg`, `07-bandeja-conversacion.jpg`, `09-bandeja-reportes.jpg`, `10-bandeja-canales.jpg`, `12-ajustes-generales.png`, `13-ajustes-agentes.jpg`, `16-ajustes-autopost.jpg`, `17-ajustes-sets.jpg`, `18-ajustes-firmas.jpg` y `20-ajustes-plugs.jpg`, así como `docs/design-neon/DESIGN.md` y `frontend/DESIGN-SYSTEM.md`.
- Escaneo completo sobre todos los archivos creados o modificados en la rama para confirmar la ausencia total de clases Tailwind con modificador de opacidad sobre variables del tema (`bg-*/NN`, `border-*/NN`, `text-*/NN`, etc.).
- Revisión de `git diff --name-status` respecto de `main` para confirmar que solo se tocaron archivos bajo `frontend/` y `PLAN.inbox-settings-ui.md`, sin tocar `package.json`, `package-lock.json`, `.env*` ni el backend.

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


 RUN  v2.1.9 C:/Users/Zeek/Desktop/AloStudio-inbox-ui/frontend

 ✓ lib/inboxes/email-blocks.test.ts (15 tests) 11ms
 ✓ components/publications/network-rules.test.ts (3 tests) 8ms
 ✓ components/reports/summary-table.test.tsx (3 tests) 273ms
 ✓ components/settings/inboxes/email-branding-panel.test.tsx (7 tests) 436ms
 ✓ components/publications/media-library-view.test.tsx (3 tests) 661ms
   ✓ MediaLibraryView > rechaza una imagen mayor a 30 MB y un video mayor a 200 MB antes de subir 355ms
 ✓ components/instagram/post-reply-picker.test.tsx (11 tests) 780ms
 ✓ components/publications/analytics-view.test.tsx (3 tests) 610ms
 ✓ components/instagram/instagram-connection.test.tsx (8 tests) 563ms
 ✓ components/publications/publication-detail-dialog.test.tsx (2 tests) 820ms
   ✓ PublicationDetailDialog > muestra cifras, 'actualizado hace…', error del destino y link, y oculta acciones a un agente 355ms
   ✓ PublicationDetailDialog > habilita Reintentar y Actualizar estadísticas para un administrador en partially_published y Borrar en failed 459ms
 ✓ components/agenda/week-view.test.tsx (3 tests) 798ms
   ✓ AgendaView > loads the current week in weekly view, navigates weeks, and filters by status 416ms
 ✓ components/contacts/contacts-view.test.tsx (4 tests) 936ms
   ✓ ContactsView > filters the list when a company chip is clicked 307ms
 ✓ components/conversations/conversation-list.test.tsx (4 tests) 895ms
   ✓ ConversationList > renders conversations returned by the API 312ms
stderr | components/settings/inboxes/email-template-panel.test.tsx > EmailTemplatePanel > surfaces a rejected save
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined

 ✓ components/settings/signatures/signatures-view.test.tsx (2 tests) 1062ms
   ✓ SignaturesView > lista firmas, crea (cuerpo correcto y conteo de puntos de código), edita y borra 791ms
 ✓ components/settings/inboxes/email-transport-panel.test.tsx (13 tests) 1195ms
 ✓ components/settings/sets/sets-view.test.tsx (2 tests) 1121ms
   ✓ SetsView > lista sets con canales y fecha, crea en modo set con el editor, edita y borra 1057ms
stderr | components/settings/inboxes/email-template-panel.test.tsx > EmailTemplatePanel, the visual designer > saves the generated HTML together with its settings
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined

stderr | components/settings/inboxes/email-template-panel.test.tsx > EmailTemplatePanel, the visual designer > sends no design when the HTML was edited by hand
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined

 ✓ components/settings/autoposts/autoposts-view.test.tsx (2 tests) 1415ms
   ✓ AutopostsView > lista feeds con revisado hace y último error, prueba el feed (entradas y error 422), crea, edita y borra 1364ms
stderr | components/settings/inboxes/email-template-panel.test.tsx > EmailTemplatePanel, the visual designer > sends no design when the HTML was edited by hand
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined

 ✓ components/settings/inboxes/email-template-panel.test.tsx (15 tests) 1480ms
   ✓ EmailTemplatePanel > saves the authored HTML 386ms
stderr | components/settings/inboxes/email-template-panel.test.tsx
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined

stderr | VirtualConsole.<anonymous> (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\virtual-console.js:29:45)
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\email-templates.ts:27:19) undefined

 ✓ components/settings/plugs/plugs-view.test.tsx (3 tests) 1559ms
   ✓ PlugsView > pide mensaje solo cuando la acción tiene message_max, cuenta UTF-8 de Threads y permite listar, crear, editar y borrar 992ms
 ✓ components/publications/calendar-view.test.tsx (5 tests) 1815ms
   ✓ CalendarView — grilla, paginación y estados > ubica cada publicación en su día y hora local, pide todas las páginas del rango y pinta el estado 755ms
   ✓ CalendarView — conexión de canales y avisos de query > 'Agregar canal' con una red authorize pide authorize_url sin cuerpo y navega a ella 409ms
   ✓ CalendarView — conexión de canales y avisos de query > 'Agregar canal' con una red form abre el diálogo, envía { fields } y muestra el 422 sin cerrarlo 314ms
 ✓ components/settings/email-templates/email-templates-view.test.tsx (15 tests) 1946ms
 ✓ components/instagram/post-autoreply-rules.test.tsx (17 tests) 2470ms
   ✓ PostAutoreplyRules > saves a keyword rule 334ms
 ✓ components/conversations/inbox-three-column.test.tsx (3 tests) 1608ms
   ✓ Bandeja en tres columnas y pestañas > muestra lista y estado vacío juntos, y cambia entre conversaciones sin recargar la lista 1157ms
   ✓ Bandeja en tres columnas y pestañas > muestra el resumen de reportes de la bandeja y la lista de canales conectados 406ms
 ✓ components/publications/publication-editor-dialog.test.tsx (5 tests) 2819ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > arma el cuerpo de publicación programada con fecha ISO, media_id reordenados, post_type y content_override 1362ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > arma borrador (draft: true) y respeta post_type: 'reels' en Instagram 527ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > muestra errores de la tabla de reglas antes de enviar y muestra el 422 del backend con message y errors[] 417ms
   ✓ PublicationEditorDialog — firmas y sets > 'Usar set' carga texto, medios y canales activos (ignorando channel: null) sin cambiar la fecha, y 'Guardar como set' envía el cuerpo esperado 366ms
 ✓ components/settings/installation/installation-view.test.tsx (6 tests) 2282ms
   ✓ Configuración de la instalación > no deja guardar un campo vacío 1917ms
 ✓ components/settings/assignment-policies/assignment-policies-view.test.tsx (3 tests) 2338ms
   ✓ AssignmentPoliciesView > creates a policy, wrapping the body in assignment_policy 2068ms
 ✓ middleware.test.ts (7 tests) 30ms
 ✓ lib/inboxes/email-template-design.test.ts (12 tests) 8ms
 ✓ components/conversations/email-message.test.tsx (9 tests) 347ms
 ✓ components/instagram/connect-capabilities-dialog.test.tsx (6 tests) 316ms
 ✓ components/conversations/email-composer.test.tsx (8 tests) 492ms
 ✓ lib/api/notifications.test.tsx (3 tests) 284ms
 ✓ components/conversations/conversation-filters.test.tsx (3 tests) 532ms
 ✓ components/instagram/autoreply-view.test.tsx (4 tests) 1979ms
   ✓ AutoreplyView (prepared answers) > says an empty library answers nothing 526ms
   ✓ when the server has no embedding provider > says so instead of blaming the answer 1115ms
stderr | components/reports/reports-view.test.tsx > ReportsView > offers CSV + Excel export links for the current scope
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-inbox-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5) undefined

 ✓ components/reports/reports-view.test.tsx (2 tests) 2738ms
   ✓ ReportsView > renders live counters and summary metrics 445ms
   ✓ ReportsView > offers CSV + Excel export links for the current scope 2287ms
 ✓ components/settings/integrations/integration-app-view.test.tsx (2 tests) 2434ms
   ✓ IntegrationAppView connect > renders an OAuth link for external-action apps 425ms
   ✓ IntegrationAppView connect > creates a hook from the inline settings form 2002ms
 ✓ components/settings/inboxes/channel-form.test.tsx (4 tests) 2640ms
   ✓ ChannelForm, creating an email inbox > omits a box left unticked rather than sending false as text 1411ms
   ✓ ChannelForm, creating an email inbox > still sends the text fields 788ms
 ✓ components/reports/metric-chart.test.tsx (6 tests) 1108ms
   ✓ MetricChart > gives the tallest bar the full height 1053ms
 ✓ lib/api/reports-gaps.test.ts (6 tests) 7ms
 ✓ components/settings/mcp-tokens/mcp-tokens-view.test.tsx (2 tests) 2488ms
   ✓ MCPTokensView y menú lateral de Ajustes > muestra el título 'API y MCP', la explicación de uso y lista tokens con alcances 2283ms
 ✓ components/settings/automation/automation-rules-view.test.tsx (3 tests) 183ms
 ✓ components/help-center/portal-detail-view.test.tsx (3 tests) 2459ms
   ✓ PortalDetailView locale picker > filters articles by the picked portal locale 2238ms
 ✓ components/conversations/ai-handoff.test.tsx (4 tests) 1975ms
   ✓ AiHandoff > renders nothing on conversations Meta's AI never touched 813ms
   ✓ AiHandoff > lets the team take a conversation the AI is answering 892ms
 ✓ components/settings/macros/macros-view.test.tsx (4 tests) 229ms
 ✓ components/conversations/conversation-participants.test.tsx (3 tests) 397ms
 ✓ components/settings/profile/profile-view.test.tsx (1 test) 269ms
 ✓ components/ui/tabs.test.tsx (3 tests) 202ms
 ✓ lib/api/fetcher.test.ts (5 tests) 9ms
 ✓ components/settings/csat/csat-view.test.tsx (1 test) 257ms
 ✓ components/campaigns/campaigns-view.test.tsx (1 test) 248ms
 ✓ components/settings/custom-attributes/custom-attributes-view.test.tsx (1 test) 1397ms
   ✓ CustomAttributesView > lists attributes with model badge and type 1360ms
 ✓ lib/realtime/cable.test.ts (3 tests) 7ms
 ✓ components/shell/nav.test.tsx (3 tests) 263ms
 ✓ lib/api/errors.test.ts (8 tests) 6ms
 ✓ components/instagram/comments-panel.test.tsx (2 tests) 287ms
 ✓ components/conversations/message-composer-canned.test.tsx (2 tests) 252ms
 ✓ components/reports/traffic-heatmap.test.tsx (3 tests) 223ms
 ✓ components/campaigns/campaign-analytics-panel.test.tsx (1 test) 179ms
 ✓ components/settings/integrations/integrations-view.test.tsx (1 test) 175ms
 ✓ lib/api/uploads.test.ts (3 tests) 70ms
 ✓ components/settings/agents/agents-view.test.tsx (1 test) 311ms
   ✓ AgentsView > lists agents with role + pending badge + email 301ms
 ✓ components/shell/page-header.test.tsx (2 tests) 224ms
 ✓ components/settings/webhooks/webhooks-view.test.tsx (1 test) 211ms
 ✓ components/products/products-view.test.tsx (1 test) 256ms
 ✓ components/help-center/portals-view.test.tsx (1 test) 486ms
   ✓ PortalsView > lists portals with archived badge and custom domain 450ms
 ✓ components/conversations/conversation-actions.test.tsx (1 test) 595ms
   ✓ ConversationActions macros > runs the picked macro on the current conversation 560ms
 ✓ components/settings/canned-responses/canned-responses-view.test.tsx (2 tests) 1267ms
   ✓ CannedResponsesView > lists responses with their short codes and content 358ms
   ✓ CannedResponsesView > sends the debounced search term to the backend 878ms
 ✓ components/help-center/articles-panel.test.tsx (2 tests) 2100ms
   ✓ ArticlesPanel search > sends the debounced query to the articles endpoint 827ms
   ✓ ArticlesPanel search > clears the search with the reset button 1238ms
 ✓ components/settings/agent-bots/agent-bots-view.test.tsx (1 test) 176ms
 ✓ components/settings/teams/teams-view.test.tsx (1 test) 173ms
 ✓ components/conversations/message-composer.test.tsx (1 test) 145ms
 ✓ components/settings/labels/labels-view.test.tsx (1 test) 253ms
 ✓ lib/api/instagram.test.tsx (1 test) 122ms
 ✓ components/ui/button.test.tsx (3 tests) 142ms
 ✓ app/privacidad/page.test.tsx (3 tests) 166ms
 ✓ components/conversations/channel-badge.test.tsx (5 tests) 107ms
 ✓ components/settings/notifications/push-toggle.test.tsx (1 test) 104ms
 ✓ lib/time.test.ts (4 tests) 4ms
 ✓ components/crm/crm-tabs.test.tsx (1 test) 82ms
 ✓ lib/auth/schemas.test.ts (3 tests) 4ms
 ✓ components/help-center/portal-form.test.tsx (1 test) 185ms
 ✓ app/terminos/page.test.tsx (2 tests) 116ms
 ✓ components/reports/bot-metrics-cards.test.tsx (1 test) 60ms
 ✓ app/eliminacion-de-datos/page.test.tsx (2 tests) 87ms

 Test Files  83 passed (83)
      Tests  328 passed (328)
   Start at  19:06:45
   Duration  23.68s (transform 8.55s, setup 29.86s, collect 90.02s, tests 61.77s, environment 250.18s, prepare 34.29s)
```

### Revisión de Claude (2026-10-29)

- Corrí de nuevo los tres comandos sobre `9d0160c`: typecheck y lint sin errores, 83 archivos y 328 tests en verde. Lo de arriba es cierto, y se cumplieron las notas de la revisión anterior (sin `color/NN`, `textLength` en plugs, `Array.from` en firmas, errores a la vista).
- Probé en el navegador contra un backend de `main` con datos sembrados (144 conversaciones en 3 bandejas, canales, firmas, sets): lista y conversación juntas sin recargar la lista (un solo pedido de `/conversations`), burbujas, asignado/equipo/etiqueta, panel del contacto; Reportes con cifras y gráfico; Canales; Firmas (marcar automática le saca la marca a la otra); Auto post con "Probar" contra un feed real (5 entradas) y contra una URL que no es feed (422 debajo del campo), guardado en borrador con un solo canal; Plugs (contador 31/500 con un emoji en Threads, el mensaje desaparece con "Repostear", alta); editor en modo set.
- Corregido en `7301496`: la pestaña Canales mostraba "Conectar canal" y "Desconectar" a los agentes (ahora solo administradores, con test), y el panel del contacto pedía `/contacts/-1` mientras cargaba la conversación (404; venía de antes).
- Menor, sin tocar: a un agente sin bandejas asignadas Canales le dice "No hay canales conectados todavía", aunque la cuenta tenga canales.
