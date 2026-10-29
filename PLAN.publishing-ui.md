# PLAN — Frontend de publicaciones (calendario, editor, medios y estadísticas)

Paso 2 de la salida de Postiz (Fase 7 del fork). El backend ya está en `main` y en producción:

| Pieza | Backend | Este plan |
|---|---|---|
| Publicaciones programadas en Instagram y páginas de Facebook | `app/domains/publishing/` | Calendario + editor |
| Biblioteca de medios de la cuenta | `app/domains/media_library/` | Pestaña Medios |
| Estadísticas de posts y canales | `app/domains/publishing/analytics.py` | Pestaña Estadísticas |

Rama `feat/publishing-ui`, worktree `C:\Users\Zeek\Desktop\AloStudio-publishing-ui`. **Solo frontend.** El trabajo lo hace un agente y lo revisa Claude contra este documento.

## Insumos (todo está en este worktree)

- `docs/design-neon/DESIGN.md` y `frontend/DESIGN-SYSTEM.md`: el sistema de diseño neón ya aplicado en toda la app. Respetalo; no inventes estilos nuevos.
- `docs/design-neon/screens/calendar.png` y `docs/design-neon/screens/analytics.png`: **referencia de layout**, no de textos. El calendario tiene la barra de rango con flechas y "Hoy", el selector Día/Semana/Mes, el alternador calendario/lista y el panel de canales a la derecha. Analytics tiene el estado vacío centrado con las redes soportadas. Los textos van en español y las redes son solo las que soporta AloStudio.
- `docs/design-neon/after/agenda-*.png`: cómo quedó la agenda, que es el patrón visual más cercano.
- `docs/design-neon/postiz/`: capturas a 1440 px de la versión anterior del producto, **la referencia que el dueño quiere seguir**. Para este plan: `02-calendario-semana.jpg` (barra de rango, Día/Semana/Mes, alternador calendario/lista, botón "Crear publicación" y panel de canales con "Agregar canal"), `05-medios-vacio.jpg`, `04-estadisticas-vacio.jpg`, `01-inicio.jpg` y la columna izquierda de cualquiera (el menú). Copiá la disposición, el espaciado y la jerarquía; los textos van en español y con lo que hace AloStudio. Las demás capturas (bandeja, ajustes) son para un plan siguiente: no las implementes ahora.

## Reglas para el agente

1. Trabajá **solo** dentro de `C:\Users\Zeek\Desktop\AloStudio-publishing-ui`. No abras ni leas `C:\Users\Zeek\Desktop\Postiz` (otra licencia: todo lo de Postiz que sirve como referencia ya está descrito acá o en las capturas) ni `C:\Users\Zeek\Desktop\AloStudio` (salvo usar su `.venv` si hiciera falta).
2. **No toques el backend** (`app/`, `alembic/`, `tests/` de Python). Si la API no alcanza para algo, anotalo en **Estado** y resolvelo sin ese dato o dejalo afuera.
3. Copiá los patrones de: `frontend/components/agenda/` (semana, diálogo con `<dialog>`, `week-utils.ts`, conversión `datetime-local`), `frontend/components/instagram/` (pestañas con `NavTabs`, composer con subida de archivos, `state-badge.tsx`), `frontend/components/reports/` (tarjetas de resumen, `MetricChart` sin librerías), `frontend/lib/api/appointments.ts` (hooks de `@tanstack/react-query` sobre `apiFetch`). **Nada de librerías nuevas** de npm: ni calendarios, ni gráficos, ni fechas, ni drag and drop.
4. Prohibido: `git push`, `ssh`, tocar archivos `.env*`, `docker compose down`, borrar volúmenes o contenedores, levantar o migrar bases de datos, cambiar código fuera del alcance de este plan.
5. Commits chicos en la rama `feat/publishing-ui`, mensajes en español con el estilo del repo (`feat(publicaciones): ...`, `test(publicaciones): ...`). Terminá cada commit con la línea `Co-Authored-By: Antigravity <noreply@google.com>`.
6. Al terminar, completá la sección **Estado** al final de este archivo: qué se hizo, qué quedó sin hacer, la salida **completa** de los tres comandos de verificación y qué revisaste a mano. No declares verificado algo que no corriste.

## Entorno

- `cd frontend && npm ci` una vez; después `npm run typecheck`, `npm run lint` y `npm test`.
- No levantes el backend ni el frontend contra datos reales: los tests usan `fetch` simulado, como `components/products/products-view.test.tsx`. La prueba en el navegador con datos reales la hace Claude.

## API (contrato)

Todo existe en el backend salvo la identidad de canal por `channel_id` (abajo), que se está implementando en paralelo con este mismo contrato. Programá contra el contrato con `fetch` simulado; no esperes al backend.

Base `/api/v1/accounts/{accountId}`. Errores 422 con `{"message": string, "errors"?: string[]}`: mostrá el `message` y la lista `errors` tal cual (vienen en español). Las escrituras de publicaciones son **solo para administradores**: un agente recibe 401 de denegación (el fetcher ya distingue denegación de sesión vencida).

**Canales donde se puede publicar** — `GET /publications/channels` → `Channel[]`

Un canal es una cuenta de una red donde la cuenta de AloStudio publica. Todo se refiere a él por `id` (`channel_id`). Instagram y páginas de Facebook nacen de una bandeja de entrada (`inbox_id`); las demás redes (hoy Threads, `network: "threads"`) se conectan desde esta pantalla y tienen `inbox_id: null`. No asumas que la lista de redes es fija: para una red desconocida mostrá un ícono genérico y su `network` como nombre.

```ts
type Network = "instagram" | "facebook_page" | string;
type Channel = {
  id: number;
  network: Network;
  name: string | null;
  username: string | null;
  avatar_url: string | null;
  inbox_id: number | null;
  status: "active" | "reconnect"; // "reconnect": hay que volver a conectarlo; no se puede elegir para publicar
  status_message: string | null;
};
```

**Publicaciones**

- `GET /publications?from&to&state&channel_id&page` → `Publication[]`. Ordena por `scheduled_for` (o `created_at` si es un borrador sin fecha), `from` inclusivo y `to` exclusivo (ISO 8601). **50 por página fijo**: para cubrir un rango pedí páginas hasta que una venga con menos de 50.
- `POST /publications` → `Publication`. Sin `scheduled_for` (o con fecha pasada) y sin `draft`, sale **ya**.
- `GET /publications/{id}`, `PATCH /publications/{id}` (mismo cuerpo que POST, todo opcional), `DELETE /publications/{id}` → `{}`.
- `POST /publications/{id}/retry` → `Publication` (solo `failed` o `partially_published`; reintenta los destinos que fallaron).
- `POST /publications/{id}/refresh_metrics` → `Publication` (relee cifras ya; si se tocó hace menos de 5 minutos devuelve las mismas).

```ts
type MediaIn = { media_id: number } | { type: "image" | "video"; url: string };
type TargetIn = {
  channel_id: number;
  settings?: { post_type?: "feed" | "reels" | "story" }; // solo Instagram; por defecto "feed"
  content_override?: string | null; // texto propio de ese canal
};
type PublicationIn = {
  content?: string | null;
  media?: MediaIn[];
  scheduled_for?: string | null; // ISO con zona
  draft?: boolean;               // true = se guarda y no sale hasta guardarla con false
  targets: TargetIn[];           // al menos uno
};

type PublicationState = "draft" | "scheduled" | "publishing" | "published" | "partially_published" | "failed";
type TargetState = "pending" | "publishing" | "published" | "failed";
type Metrics = Partial<Record<"views" | "reach" | "likes" | "comments" | "shares" | "saves" | "interactions", number>>;

type Publication = {
  id: number;
  account_id: number;
  content: string | null;
  media: { type: "image" | "video"; url: string; media_id?: number }[]; // url pública, sirve de miniatura
  scheduled_for: string | null;
  state: PublicationState;
  created_by_id: number | null;
  published_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  targets: {
    id: number;
    channel: Channel;
    settings: { post_type?: string };
    content_override: string | null;
    state: TargetState;
    external_id: string | null;
    permalink: string | null;
    error_code: string | null;
    error_message: string | null;
    attempts: number;
    published_at: string | null;
    metrics: Metrics;
    metrics_updated_at: string | null;
    metrics_error: string | null;
  }[];
};
```

**Conectar redes que no son bandejas**

Hay dos formas, y `/networks` dice cuál usa cada red:

```ts
type ConnectionField = { name: string; label: string; help: string; secret: boolean };
type NetworkOption = {
  network: string;
  label: string;
  configured: boolean;
  kind: "authorize" | "form";
  fields: ConnectionField[]; // vacío para "authorize"
};
```

- `GET /publications/networks` → `NetworkOption[]` (hoy: Threads por autorización; Telegram y Discord por formulario).
- `kind: "authorize"`: `POST /publications/channels/connect/{network}` sin cuerpo (solo administrador) → `{ authorize_url: string }`: mandá el navegador ahí (`window.location.href`). 422 con `message` si la instalación no está configurada para esa red.
- `kind: "form"`: un diálogo con un campo por `fields` (los `secret` como contraseña, con su `help` debajo, todos obligatorios) y `POST /publications/channels/connect/{network}` con `{ fields: { [name]: valor } }` → `{ channel: Channel }`, ya conectado: refrescá la lista de canales. Si la red rechaza los datos vuelve 422 con `message` en español: mostralo en el diálogo sin cerrarlo.
- Al volver, la red deja al usuario en `/accounts/{accountId}/publications` con `?connected=<network>&channel=<id>` si salió bien o `?connect_error=<mensaje>` si no: mostrá un aviso con eso y limpiá la query.
- `DELETE /publications/channels/{id}` (solo administrador) → `{}`; 422 para los canales de una bandeja (se quitan desde la bandeja).

Reglas de estado: se edita solo en `draft` o `scheduled`; se borra en `draft`, `scheduled` o `failed`; se reintenta en `failed` o `partially_published`.

Reglas de cada red (el backend las valida igual; mostralas antes de enviar para no esperar al 422):

| Red | Texto | Medios |
|---|---|---|
| Instagram `feed` | hasta 2200 caracteres | 1 a 10 imágenes o videos (más de 1 = carrusel) |
| Instagram `reels` | hasta 2200 | exactamente 1 video |
| Instagram `story` | hasta 2200 (no se muestra) | exactamente 1 imagen o video |
| Página de Facebook | hasta 63206; texto **o** medios obligatorio | hasta 10 imágenes, o 1 video solo |
| Threads | hasta 500 (cada emoji cuenta como varios); texto **o** medios obligatorio | hasta 20 imágenes o videos (más de 1 = carrusel) |
| Telegram | hasta 4096 sin medios, 1024 con medios; texto **o** medios obligatorio | hasta 10 imágenes o videos (más de 1 = álbum) |
| Discord | hasta 2000, contando un link por cada video; texto **o** medios obligatorio | hasta 10 imágenes (los videos van como link) |

**Biblioteca de medios**

- `GET /media?kind=image|video&page` → `MediaAsset[]` (50 por página).
- `POST /media` multipart con el campo `file` → `MediaAsset`. Límites: imagen 30 MB, video 200 MB (validalos antes de subir).
- `DELETE /media/{id}` → `{}`, solo administradores; 422 si una publicación pendiente lo usa.

```ts
type MediaAsset = {
  id: number; kind: "image" | "video"; filename: string | null; content_type: string | null;
  size_bytes: number; url: string; uploaded_by_id: number | null; created_at: string | null;
};
```

`url` es un link de vista previa que **vence a la hora**: `staleTime` menor a una hora y volvé a pedir la lista al reenfocar.

**Estadísticas** — `GET /publications/analytics?from&to&channel_id` (por defecto los últimos 30 días; período inválido o mayor a 366 días → 422)

```ts
type Analytics = {
  from: string; to: string;
  totals: { posts: number } & Metrics;
  channels: {
    channel: Channel;
    posts: number;
    metrics: Metrics;
    followers: number | null;
    followers_change: number | null;
    series: ({ date: string; followers?: number } & Pick<Metrics, "views" | "reach" | "interactions">)[]; // un punto por día
  }[];
  top_posts: {
    publication_id: number; target_id: number; channel: Channel | null;
    content: string; permalink: string | null; published_at: string | null; metrics: Metrics;
  }[];
};
```

Las cifras de los posts se actualizan cada hora y las de los canales una vez por día (03:47 UTC): decilo en la pantalla.

**Firmas y sets** (para el editor; las pantallas para administrarlos van en un plan siguiente)

```ts
type Signature = { id: number; content: string; auto_add: boolean; created_at: string | null; updated_at: string | null };
type PublicationSet = {
  id: number;
  name: string;
  content: string | null;
  media: ({ media_id: number; type: "image" | "video"; url: string } | { type: "image" | "video"; url: string })[];
  targets: { channel_id: number; channel: Channel | null; settings: { post_type?: string }; content_override: string | null }[];
  created_at: string | null;
  updated_at: string | null;
};
```

- `GET /publications/signatures` → `Signature[]`. A lo sumo una tiene `auto_add: true`.
- `GET /publications/sets` → `PublicationSet[]` (ordenados por nombre). `channel: null` = el canal ya no existe: ignoralo al cargar el set.
- `POST /publications/sets` (solo administrador) con `{ name, content, media: [{ media_id } | { type, url }], targets: [{ channel_id, settings, content_override }] }` → `PublicationSet`. 422 con `message` si un canal o archivo no es de la cuenta.

**Rol del usuario**: `useProfile()` de `lib/api/profile.ts` trae `accounts[]`; la cuenta actual es la de `id === Number(accountId)`. Es administrador si `role === ROLE_ADMINISTRATOR` (`1`, de `lib/api/account.ts`). Ojo: el backend manda `role` como número aunque el tipo de `profile.ts` diga `string`; corregí ese tipo a `number`. Para un agente, ocultá crear, editar, borrar, reintentar y actualizar estadísticas (puede ver todo y subir medios).

## 1. Navegación y rutas

El dueño quiere el menú lateral como el de su versión anterior (referencia: `docs/design-neon/screens/calendar.png`, columna izquierda): cada sección principal es un ítem propio, sin pestañas que agrupen publicación.

- Rutas en `frontend/app/accounts/[accountId]/publications/`: `page.tsx` (Calendario), `media/page.tsx` (Medios), `analytics/page.tsx` (Estadísticas). Sin `layout.tsx` de pestañas.
- `frontend/components/shell/nav.ts`, en este orden y con estos íconos de `lucide-react`:
  1. Inicio (`Home`, como está).
  2. **Calendario** (`CalendarDays`) → `publications`.
  3. **Estadísticas** (`ChartLine`) → `publications/analytics`.
  4. **Medios** (`Images`) → `publications/media`.
  5. **Bandeja** (`Inbox`) → `conversations` (el ítem "Conversaciones" actual, renombrado).
  6. **CRM** (`Users`) → `contacts`: agrupa Contactos, Productos y Agenda, que dejan de ser ítems sueltos. En esas tres pantallas, pestañas `NavTabs` (como `components/instagram/instagram-tabs.tsx`) Contactos | Productos | Agenda, con un `layout.tsx` compartido o el mismo componente de pestañas en cada página. Las rutas no cambian.
  7. Instagram, Help Center, Campañas y Reportes siguen como están, después de CRM.
  8. Ajustes, abajo, como está.
  Ajustá `NAV_GROUPS` para que refleje este orden (los grupos con título pueden desaparecer si quedan raros; que se vea como la referencia). Un ítem queda activo también en sus subrutas (`publications/media` no debe marcar Calendario).
- Componentes en `frontend/components/publications/`; hooks y tipos en `frontend/lib/api/publications.ts` y `frontend/lib/api/media.ts` (un hook por consulta o mutación, como `appointments.ts`; las mutaciones invalidan las consultas afectadas).

## 2. Calendario

- Vistas **Semana** (lunes a domingo, por hora, con la línea de "ahora" como en la referencia), **Mes** (grilla de 6 semanas) y **Lista** (por día, con filtro de estado). Barra con anterior / rango / siguiente y "Hoy". Fechas en la zona horaria del navegador. Reutilizá `components/agenda/week-utils.ts` donde aplique.
- Cada publicación es una tarjeta en su día y hora: miniatura del primer medio, ícono de cada red de sus destinos, las primeras palabras del texto y el estado con color (`draft` Borrador, `scheduled` Programada, `publishing` Publicando, `published` Publicada, `partially_published` Publicada en parte, `failed` Falló). En Mes, si no entran, "+N más".
- Panel de canales a la derecha (colapsable; abajo en móvil): los canales de `/publications/channels` con avatar (o ícono de red), nombre y usuario, los de `status: "reconnect"` marcados con su `status_message`, y un filtro por canal (`channel_id`). Botón **"Agregar canal"** (administrador): un menú con las redes de `/publications/networks` (las de `configured: false` deshabilitadas, con "Falta configurar en Ajustes → Instalación") más "Instagram o página de Facebook", que lleva a `Ajustes > Bandejas de entrada` (`/accounts/{accountId}/settings/inboxes`). En un canal con `status: "reconnect"`, "Volver a conectar" repite la conexión de su red; en uno sin bandeja, "Quitar" (con confirmación). Sin canales: estado vacío con el mismo botón.
- Botón **"Nueva publicación"**. Un administrador también crea haciendo clic en un hueco vacío de Semana o en un día de Mes (fecha precargada).
- Clic en una tarjeta: si es editable abre el editor; si no, el detalle (sección 4).

## 3. Editor (diálogo)

- **Canales**: elegir uno o más de `/publications/channels` (solo los de `status: "active"`).
- **Texto** compartido, con contador contra el límite más chico de los canales elegidos.
- **Medios**: elegir de la biblioteca (grilla con miniaturas, filtro imagen/video) o subir uno nuevo, que queda en la biblioteca. Mostrar los elegidos en orden, con quitar y mover. Se envían como `{ media_id }`.
- **Por canal** (una fila por canal elegido): en Instagram, el tipo `feed` / `reels` / `story` con el `SegmentedControl` existente; en todos, "Personalizar texto para este canal", que manda `content_override`.
- **Cuándo**: "Publicar ahora" o fecha y hora (`datetime-local`, enviada como ISO con zona).
- **Vista previa** simple por canal: nombre del canal, el texto que le toca y el primer medio. No imites la interfaz de cada red.
- Acciones: **Guardar borrador** (`draft: true`), **Programar** o **Publicar ahora** (`draft: false`). Mostrá los problemas de la tabla de reglas antes de enviar y los 422 del backend tal cual.
- Editar una publicación existente usa `PATCH` con el mismo formulario precargado.
- **Firmas**: un botón "Firma" junto al texto abre la lista de `/publications/signatures` y agrega la elegida al final del texto (en una línea nueva). Al abrir el editor para una publicación **nueva**, si hay una firma con `auto_add`, el texto arranca con esa firma (dos saltos de línea antes, para escribir arriba).
- **Sets**: arriba del editor, "Usar set" (si hay sets) carga uno: reemplaza texto, medios y canales con los del set (con su `settings` y `content_override`), sin tocar la fecha. "Guardar como set" (administrador) pide un nombre y manda el editor actual a `POST /publications/sets` (los medios de la biblioteca como `{ media_id }`).

## 4. Detalle

- Para publicaciones no editables (o desde "Ver" en una editable): texto, medios, fecha y, por destino, su estado, el error si falló (`error_message`), el link a la publicación (`permalink`) y sus cifras (`views`, `reach`, `likes`, `comments`, `shares`, `saves`, `interactions`) con "actualizado hace…" (`metrics_updated_at`) o el motivo si no se pudieron leer (`metrics_error`).
- Acciones (solo administrador y según las reglas de estado): **Reintentar**, **Actualizar estadísticas**, **Borrar** (con confirmación).

## 5. Medios

- Grilla de la biblioteca con filtro Todo / Imágenes / Videos, paginada de a 50 ("Cargar más").
- Subir con botón y arrastrando archivos a la pantalla (eventos nativos de drag de archivos; nada de librerías). Validá tamaño y tipo antes de subir y mostrá el progreso como "Subiendo…".
- Borrar (solo administrador) con confirmación; si el backend dice que está en uso, mostralo.

## 6. Estadísticas

- Selector de período: 7, 30 o 90 días, o personalizado con desde y hasta (máximo un año); filtro por canal.
- Tarjetas de totales: publicaciones, vistas, alcance, interacciones, me gusta, comentarios, compartidos, guardados (las que vengan; una cifra que no viene se muestra como "—", no como 0).
- Por canal: seguidores y su variación en el período, publicaciones y totales, y un gráfico diario (`series`) de alcance o vistas con selector, hecho como `components/reports/metric-chart.tsx`.
- Mejores publicaciones: las de `top_posts`, con canal, texto, fecha, cifras y link.
- Sin canales: el estado vacío de la referencia (con Instagram y Facebook como redes soportadas) y un botón al calendario.

## 7. Tests

Con Vitest y `fetch` simulado, como los tests existentes:

- El calendario ubica cada publicación en su día y hora, pide todas las páginas del rango y pinta el estado.
- El editor arma el cuerpo correcto: borrador, programada con fecha ISO, `media_id` en orden, `post_type` y `content_override` por canal; muestra los errores de reglas y los de un 422.
- El detalle muestra cifras, error y link, y oculta las acciones a un agente.
- Medios rechaza un archivo demasiado grande antes de subir.
- El editor nuevo arranca con la firma automática; "Usar set" carga texto, medios y canales; "Guardar como set" manda el cuerpo esperado.
- "Agregar canal" con una red `authorize` pide la URL de conexión y navega a ella; con una red `form` abre el diálogo, manda `{ fields }` y muestra el 422 en el diálogo. El aviso de `?connected` / `?connect_error` se muestra y la query se limpia.
- Estadísticas muestra totales, "—" para cifras ausentes y el estado vacío sin canales.

## Fuera de alcance

Cambios de backend, pantallas propias de cada red (más allá del menú "Agregar canal" y la tabla de reglas), quitar o cambiar la pantalla de Instagram existente, arrastrar publicaciones para reprogramarlas, generar textos con IA, comentarios de los posts, vistas previas fieles a cada red. Si algo de esto parece necesario, anotalo en **Estado** y no lo hagas.

## Terminado cuando

`npm run typecheck`, `npm run lint` y `npm test` pasan sin errores, cada sección de arriba está hecha o explicada en **Estado**, y la sección **Estado** está completa.

## Estado

### Qué se hizo

- **Clientes de API, tipos, errores 422 y rol de cuenta**:
  - `frontend/lib/api/profile.ts`: corregido `accounts[].role` de `string` a `number` y agregado `useIsAccountAdmin(accountId)` comparando contra `ROLE_ADMINISTRATOR` (`1`).
  - `frontend/lib/api/media.ts`: tipos y hooks `useMediaAssets`, `useInfiniteMediaAssets` (paginación de a 50, `staleTime` de 30 min `< 1h` y `refetchOnWindowFocus: true` por vencimiento de URLs firmadas), `useUploadMedia` (`POST /media` multipart con `file`) y `useDeleteMedia`, más `validateMediaFile` (30 MB imagen / 200 MB video y validación de tipo antes de subir).
  - `frontend/lib/api/publications.ts`: todos los tipos del contrato (`Channel`, `Publication`, `PublicationIn`, `NetworkOption`, `Analytics`, `Signature`, `PublicationSet`), `parsePublicationError` (preserva `message` y `errors[]` de los 422), predicados de estado (`canEditPublication`, `canDeletePublication`, `canRetryPublication`, `canRefreshMetrics`), `fetchAllPublications` / `usePublicationsRange` (itera páginas de 50 hasta recibir `< 50`) y hooks de React Query con invalidación para canales, redes, conexión (`authorize` y `form`), borrado de canal, CRUD de publicaciones, `retry`, `refresh_metrics`, `analytics`, `signatures` y `sets`.
  - `frontend/components/publications/network-rules.ts`: validación previa al envío de todas las reglas por red (Instagram `feed`/`reels`/`story`, página de Facebook sin mezclar imagen y video, Threads 500, Telegram 4096/1024, Discord 2000 descontando links de video) y `minSharedCharLimit`.
- **1. Navegación y rutas**:
  - `frontend/components/shell/nav.ts`, `sidebar-nav.tsx`, `dashboard-shell.tsx`: menú lateral reordenado (`Inicio`, `Calendario` → `publications`, `Estadísticas` → `publications/analytics`, `Medios` → `publications/media`, `Bandeja` → `conversations`, `CRM` → `contacts`, `Instagram`, `Help Center`, `Campañas`, `Reportes`, y `Ajustes` fijo abajo). `activeNavItemKey` resuelve por prefijo más específico para que `publications/media` y `publications/analytics` no marquen `Calendario`, mientras `contacts`, `products` y `agenda` marcan `CRM`.
  - `frontend/components/crm/crm-tabs.tsx` y `frontend/app/accounts/[accountId]/(crm)/layout.tsx`: agrupación de Contactos, Productos y Agenda con `NavTabs` compartidas sin cambiar ninguna URL.
  - Rutas nuevas sin layout de pestañas: `publications/page.tsx`, `publications/media/page.tsx` y `publications/analytics/page.tsx`.
- **2. Calendario y panel de canales**:
  - `frontend/components/publications/calendar-utils.ts` y `calendar-view.tsx`: vistas Día, Semana (lunes a domingo por hora con línea neón de "ahora") y Mes (grilla de 6 semanas con `+N más` expandible), alternador Calendario / Lista (agrupada por día con filtro de estado), barra anterior / rango / siguiente y "Hoy" en zona horaria local, creación desde botón "Nueva publicación" o clic en hueco/día para administradores, apertura de editor en estados editables o de detalle en no editables, y carteles de retorno `?connected=<network>&channel=<id>` / `?connect_error=<mensaje>` limpiando la query con `router.replace`.
  - `frontend/components/publications/channels-panel.tsx`: panel derecho colapsable (abajo en móvil) con avatar/ícono de red (incluyendo fallback genérico para redes desconocidas), filtro por `channel_id`, estado vacío con "Agregar canal", menú de `/publications/networks` (deshabilitando `configured: false` con aviso de `Ajustes → Instalación` más link "Instagram o página de Facebook" a `/accounts/{accountId}/settings/inboxes`), flujo `authorize` (`window.location.href = authorize_url`), diálogo `form` (campos obligatorios, `secret` como password, `help` y 422 en el diálogo sin cerrarlo), "Volver a conectar" en canales `reconnect` y "Quitar" con confirmación en canales con `inbox_id: null`.
- **3. Editor (diálogo)**:
  - `frontend/components/publications/publication-editor-dialog.tsx`: selección de canales activos, texto compartido con contador contra `minSharedCharLimit`, selector de biblioteca con filtro Todo/Imágenes/Videos y subida directa de archivos nuevos, lista ordenada de medios con mover arriba/abajo y quitar (enviados como `{ media_id }`), ajustes por canal (`SegmentedControl` `feed`/`reels`/`story` en Instagram y `content_override` en todos), selector "Publicar ahora" / "Programar" (`datetime-local` → ISO con zona), vista previa simple por canal, validación previa de reglas y visualización textual de 422 (`message` + `errors[]`), edición con `PATCH`, botón "Firma" + precarga `\n\n<firma>` cuando hay una firma `auto_add` en publicaciones nuevas, "Usar set" (ignorando `channel: null` y preservando la fecha) y "Guardar como set" (administrador).
- **4. Detalle (diálogo)**:
  - `frontend/components/publications/publication-detail-dialog.tsx`: texto, medios, fecha, estado por destino, `error_message`, link `permalink`, cifras (`views`, `reach`, `interactions`, `likes`, `comments`, `shares`, `saves`, mostrando `"—"` cuando faltan) con "actualizado hace…" (`metrics_updated_at`) o `metrics_error`, y acciones de administrador según estado (`Editar`, `Actualizar estadísticas`, `Reintentar`, `Borrar` con confirmación), ocultas para agentes.
- **5. Medios**:
  - `frontend/components/publications/media-library-view.tsx`: grilla con filtro Todo / Imágenes / Videos, paginación de 50 con "Cargar más", subida por botón y eventos nativos de drag & drop sin librerías externas, validación previa de tipo y tamaño (30 MB / 200 MB), indicador "Subiendo…" y borrado con confirmación solo para administradores mostrando el 422 si está en uso.
- **6. Estadísticas**:
  - `frontend/components/publications/analytics-view.tsx`: selector 7 / 30 / 90 días o rango personalizado (validado hasta 1 año), filtro por canal, aviso de frecuencia de actualización (cada hora en posts y 03:47 UTC en canales), tarjetas de totales mostrando `"—"` para métricas ausentes (nunca `0` salvo que venga `0`), desglose por canal con seguidores y variación + gráfico diario de barras (`reach` / `views`) sin dependencias siguiendo `components/reports/metric-chart.tsx`, lista `top_posts` y estado vacío sin canales con Instagram y Facebook como redes soportadas y botón al calendario.
- **7. Tests**:
  - Agregados `nav.test.tsx`, `crm-tabs.test.tsx`, `network-rules.test.ts`, `media-library-view.test.tsx`, `analytics-view.test.tsx`, `publication-detail-dialog.test.tsx`, `publication-editor-dialog.test.tsx` y `calendar-view.test.tsx` cubriendo todos los escenarios pedidos con Vitest + MSW.

### Qué quedó pendiente / fuera de alcance

- Ningún punto de las secciones 1 a 7 quedó sin implementar.
- Se respetó estrictamente la sección **Fuera de alcance**: no se modificó el backend ni archivos `.env*`, no se agregaron dependencias de npm, no se tocó la pantalla existente de Instagram y no se implementaron drag & drop de reprogramación, generación con IA, comentarios de posts, vistas previas fieles a cada red ni pantallas de administración de firmas/sets (previstas para un plan siguiente).
- Tal como indica **Entorno**, no se levantaron servidores contra bases reales; la prueba interactiva en navegador con datos reales queda para la revisión de Claude.

### Qué se revisó a mano

- Revisión visual de las capturas de referencia en `docs/design-neon/screens/{calendar,analytics}.png`, `docs/design-neon/postiz/{01-inicio,02-calendario-semana,04-estadisticas-vacio,05-medios-vacio,11-crm-clientes}.jpg` y `docs/design-neon/after/agenda-*.png`, junto con los tokens y reglas de `docs/design-neon/DESIGN.md` y `frontend/DESIGN-SYSTEM.md` (sin colores hardcodeados fuera de los acentos de marca de red, sin librerías nuevas, tipografía numérica tabular y superficies glass).
- Revisión manual línea por línea de contratos de entrada/salida, paginación completa de `/publications`, expiración `< 1h` de URLs firmadas en `/media`, preservación de `message` + `errors[]` en respuestas 422, limpieza de `?connected` / `?connect_error` y ocultamiento de acciones de escritura cuando `role !== ROLE_ADMINISTRATOR`.
- Revisión de `git diff main --stat` para confirmar que únicamente se tocaron archivos de `frontend/` (y este archivo de plan), sin tocar backend, `.env*` ni `package.json`.

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


 RUN  v2.1.9 C:/Users/Zeek/Desktop/AloStudio-publishing-ui/frontend

 ✓ lib/inboxes/email-blocks.test.ts (15 tests) 11ms
 ✓ middleware.test.ts (7 tests) 30ms
 ✓ components/conversations/email-message.test.tsx (9 tests) 259ms
 ✓ components/reports/summary-table.test.tsx (3 tests) 336ms
 ✓ components/publications/media-library-view.test.tsx (3 tests) 577ms
 ✓ components/settings/assignment-policies/assignment-policies-view.test.tsx (3 tests) 557ms
   ✓ AssignmentPoliciesView > creates a policy, wrapping the body in assignment_policy 315ms
 ✓ components/conversations/email-composer.test.tsx (8 tests) 480ms
 ✓ components/instagram/post-reply-picker.test.tsx (11 tests) 673ms
 ✓ components/publications/analytics-view.test.tsx (2 tests) 430ms
 ✓ components/conversations/conversation-filters.test.tsx (3 tests) 547ms
   ✓ ConversationFilters > builds an equal_to condition from the default row 328ms
 ✓ components/settings/inboxes/email-branding-panel.test.tsx (7 tests) 523ms
 ✓ components/publications/publication-detail-dialog.test.tsx (2 tests) 680ms
   ✓ PublicationDetailDialog > muestra cifras, 'actualizado hace…', error del destino y link, y oculta acciones a un agente 312ms
   ✓ PublicationDetailDialog > habilita Reintentar y Actualizar estadísticas para un administrador en partially_published y Borrar en failed 362ms
 ✓ components/settings/installation/installation-view.test.tsx (6 tests) 584ms
 ✓ components/instagram/instagram-connection.test.tsx (8 tests) 567ms
 ✓ components/conversations/conversation-list.test.tsx (4 tests) 700ms
 ✓ components/agenda/week-view.test.tsx (3 tests) 707ms
   ✓ AgendaView > loads the current week in weekly view, navigates weeks, and filters by status 381ms
 ✓ components/settings/inboxes/email-transport-panel.test.tsx (13 tests) 1008ms
 ✓ components/contacts/contacts-view.test.tsx (4 tests) 862ms
stderr | components/settings/inboxes/email-template-panel.test.tsx > EmailTemplatePanel > surfaces a rejected save
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined

stderr | components/settings/inboxes/email-template-panel.test.tsx > EmailTemplatePanel, the visual designer > saves the generated HTML together with its settings
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined

stderr | components/settings/inboxes/email-template-panel.test.tsx > EmailTemplatePanel, the visual designer > saves the generated HTML together with its settings
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined

stderr | components/settings/inboxes/email-template-panel.test.tsx > EmailTemplatePanel, the visual designer > sends no design when the HTML was edited by hand
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined

 ✓ components/settings/inboxes/email-template-panel.test.tsx (15 tests) 1279ms
   ✓ EmailTemplatePanel > saves the authored HTML 364ms
stderr | components/settings/inboxes/email-template-panel.test.tsx
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined

stderr | VirtualConsole.<anonymous> (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\virtual-console.js:29:45)
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\email-templates.ts:27:19) undefined

 ✓ components/publications/calendar-view.test.tsx (5 tests) 1676ms
   ✓ CalendarView — grilla, paginación y estados > ubica cada publicación en su día y hora local, pide todas las páginas del rango y pinta el estado 651ms
   ✓ CalendarView — conexión de canales y avisos de query > 'Agregar canal' con una red authorize pide authorize_url sin cuerpo y navega a ella 375ms
   ✓ CalendarView — conexión de canales y avisos de query > 'Agregar canal' con una red form abre el diálogo, envía { fields } y muestra el 422 sin cerrarlo 391ms
 ✓ components/settings/email-templates/email-templates-view.test.tsx (15 tests) 1811ms
 ✓ components/instagram/post-autoreply-rules.test.tsx (17 tests) 1936ms
   ✓ PostAutoreplyRules > saves a keyword rule 334ms
 ✓ lib/inboxes/email-template-design.test.ts (12 tests) 8ms
 ✓ components/publications/publication-editor-dialog.test.tsx (5 tests) 2455ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > arma el cuerpo de publicación programada con fecha ISO, media_id reordenados, post_type y content_override 1185ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > arma borrador (draft: true) y respeta post_type: 'reels' en Instagram 431ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > muestra errores de la tabla de reglas antes de enviar y muestra el 422 del backend con message y errors[] 374ms
   ✓ PublicationEditorDialog — firmas y sets > 'Usar set' carga texto, medios y canales activos (ignorando channel: null) sin cambiar la fecha, y 'Guardar como set' envía el cuerpo esperado 346ms
 ✓ components/settings/inboxes/channel-form.test.tsx (4 tests) 600ms
 ✓ components/publications/network-rules.test.ts (2 tests) 5ms
stderr | components/reports/reports-view.test.tsx > ReportsView > offers CSV + Excel export links for the current scope
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-publishing-ui\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5) undefined

 ✓ components/reports/reports-view.test.tsx (2 tests) 733ms
   ✓ ReportsView > renders live counters and summary metrics 444ms
 ✓ lib/api/reports-gaps.test.ts (6 tests) 8ms
 ✓ components/instagram/connect-capabilities-dialog.test.tsx (6 tests) 362ms
 ✓ components/reports/metric-chart.test.tsx (6 tests) 132ms
 ✓ lib/api/notifications.test.tsx (3 tests) 344ms
 ✓ components/conversations/conversation-participants.test.tsx (3 tests) 414ms
 ✓ lib/api/fetcher.test.ts (5 tests) 10ms
 ✓ components/settings/integrations/integration-app-view.test.tsx (2 tests) 458ms
 ✓ components/instagram/autoreply-view.test.tsx (4 tests) 430ms
 ✓ components/settings/macros/macros-view.test.tsx (4 tests) 209ms
 ✓ components/conversations/ai-handoff.test.tsx (4 tests) 529ms
 ✓ components/settings/automation/automation-rules-view.test.tsx (3 tests) 1346ms
   ✓ AutomationRulesView > lists rules with event, counts, and active state 1258ms
 ✓ components/ui/tabs.test.tsx (3 tests) 1629ms
   ✓ Tabs > marks the active tab with aria-selected and neon-tab-active 635ms
   ✓ Tabs > renders NavTabs links with aria-current on the active route 579ms
   ✓ SegmentedControl > switches active segment with Focused Glass and Lit Text (no halo) 401ms
 ✓ components/settings/profile/profile-view.test.tsx (1 test) 1964ms
   ✓ ProfileView avatar > uploads a picked image and PUTs the resulting URL 1959ms
 ✓ components/help-center/portal-detail-view.test.tsx (3 tests) 2276ms
   ✓ PortalDetailView reindex > posts a reindex and reports how many were enqueued 1918ms
 ✓ components/campaigns/campaigns-view.test.tsx (1 test) 368ms
 ✓ components/settings/csat/csat-view.test.tsx (1 test) 516ms
   ✓ CsatView > renders metrics cards and responses 358ms
 ✓ lib/realtime/cable.test.ts (3 tests) 7ms
 ✓ components/settings/custom-attributes/custom-attributes-view.test.tsx (1 test) 231ms
 ✓ components/instagram/comments-panel.test.tsx (2 tests) 329ms
   ✓ CommentsPanel > renders comments and marks hidden ones 314ms
 ✓ components/shell/nav.test.tsx (3 tests) 271ms
 ✓ components/conversations/message-composer-canned.test.tsx (2 tests) 263ms
 ✓ components/settings/agents/agents-view.test.tsx (1 test) 2133ms
   ✓ AgentsView > lists agents with role + pending badge + email 2107ms
 ✓ lib/api/errors.test.ts (8 tests) 5ms
 ✓ components/campaigns/campaign-analytics-panel.test.tsx (1 test) 233ms
 ✓ components/reports/traffic-heatmap.test.tsx (3 tests) 192ms
 ✓ components/settings/canned-responses/canned-responses-view.test.tsx (2 tests) 738ms
   ✓ CannedResponsesView > lists responses with their short codes and content 314ms
   ✓ CannedResponsesView > sends the debounced search term to the backend 419ms
 ✓ components/shell/page-header.test.tsx (2 tests) 194ms
 ✓ components/settings/integrations/integrations-view.test.tsx (1 test) 163ms
 ✓ components/help-center/articles-panel.test.tsx (2 tests) 894ms
   ✓ ArticlesPanel search > sends the debounced query to the articles endpoint 519ms
   ✓ ArticlesPanel search > clears the search with the reset button 369ms
 ✓ components/conversations/conversation-actions.test.tsx (1 test) 265ms
 ✓ components/products/products-view.test.tsx (1 test) 188ms
 ✓ components/settings/agent-bots/agent-bots-view.test.tsx (1 test) 165ms
 ✓ lib/api/uploads.test.ts (3 tests) 62ms
 ✓ components/settings/webhooks/webhooks-view.test.tsx (1 test) 207ms
 ✓ components/conversations/message-composer.test.tsx (1 test) 140ms
 ✓ lib/api/instagram.test.tsx (1 test) 139ms
 ✓ components/help-center/portals-view.test.tsx (1 test) 179ms
 ✓ components/settings/labels/labels-view.test.tsx (1 test) 261ms
 ✓ components/ui/button.test.tsx (3 tests) 169ms
 ✓ components/settings/mcp-tokens/mcp-tokens-view.test.tsx (1 test) 208ms
 ✓ app/privacidad/page.test.tsx (3 tests) 206ms
 ✓ components/conversations/channel-badge.test.tsx (5 tests) 126ms
 ✓ components/settings/teams/teams-view.test.tsx (1 test) 162ms
 ✓ components/help-center/portal-form.test.tsx (1 test) 158ms
 ✓ components/crm/crm-tabs.test.tsx (1 test) 82ms
 ✓ components/settings/notifications/push-toggle.test.tsx (1 test) 114ms
 ✓ lib/time.test.ts (4 tests) 5ms
 ✓ components/reports/bot-metrics-cards.test.tsx (1 test) 64ms
 ✓ lib/auth/schemas.test.ts (3 tests) 4ms
 ✓ app/terminos/page.test.tsx (2 tests) 124ms
 ✓ app/eliminacion-de-datos/page.test.tsx (2 tests) 87ms

 Test Files  78 passed (78)
      Tests  313 passed (313)
   Start at  17:23:05
   Duration  20.26s (transform 8.58s, setup 27.49s, collect 80.68s, tests 39.80s, environment 201.11s, prepare 22.87s)
```

### Revisión de Claude (2026-10-29)

- Corrí de nuevo los tres comandos sobre `4cd924d`: typecheck y lint sin errores, 78 archivos y 313 tests en verde. Lo de arriba es cierto.
- Probé en el navegador con un backend de `feat/signatures-sets` y una base aparte con datos sembrados (5 canales, uno a reconectar; 74 publicaciones en todos los estados; cifras, firmas, sets y un agente): menú, Semana/Mes/Lista, paginación (pide la página 2), "+N más", filtro de estado, detalle con reintento real, editor con firma automática y "Usar set", y qué ve un agente (sin crear, editar, borrar, conectar ni acciones del detalle; puede subir medios).
- Corregido en `8a11e34`:
  - Reglas y contadores contaban `text.length` (unidades UTF-16): un emoji valía 2 en todas las redes. Ahora cuentan como el backend (puntos de código; en Threads, cada emoji por sus bytes UTF-8). Antes 198 emoji marcaban 396/500 y el backend los rechazaba con 422.
  - El 422 del backend quedaba arriba del diálogo, fuera de la vista de quien tocó Guardar abajo: ahora se desplaza hasta el aviso.
  - Estadísticas mandaba `from`/`to` como fechas sueltas: el backend las lee como medianoche UTC con `to` exclusivo y dejaba afuera lo de hoy (y el día "Hasta"). Ahora manda medianoches locales, hoy incluido.
  - El gráfico diario reusa `MetricChart`. Sus barras eran invisibles: `bg-primary/60` no genera CSS porque `primary` es `var(--primary)` con un hex. Ahora usa `opacity-60`.
- Pendiente fuera de este plan: el mismo problema de opacidad está en ~95 clases de 39 archivos de `main` (`bg-danger/10`, `bg-success/10`, `bg-backdrop/75`…): ninguna genera CSS. Se arregla una vez en `tailwind.config.ts` (colores con `<alpha-value>`), revisando a ojo toda la app porque cambia el aspecto de avisos y fondos de diálogos.
- Menores, sin tocar: `useUploadMedia` repite la lógica de 401 de `apiFetch`; al editar, un destino cuyo canal pasó a "reconnect" se quita del PATCH sin avisar.
