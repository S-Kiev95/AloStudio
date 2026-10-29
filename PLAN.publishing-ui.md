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
- "Agregar canal" con una red `authorize` pide la URL de conexión y navega a ella; con una red `form` abre el diálogo, manda `{ fields }` y muestra el 422 en el diálogo. El aviso de `?connected` / `?connect_error` se muestra y la query se limpia.
- Estadísticas muestra totales, "—" para cifras ausentes y el estado vacío sin canales.

## Fuera de alcance

Cambios de backend, pantallas propias de cada red (más allá del menú "Agregar canal" y la tabla de reglas), quitar o cambiar la pantalla de Instagram existente, arrastrar publicaciones para reprogramarlas, generar textos con IA, comentarios de los posts, vistas previas fieles a cada red. Si algo de esto parece necesario, anotalo en **Estado** y no lo hagas.

## Terminado cuando

`npm run typecheck`, `npm run lint` y `npm test` pasan sin errores, cada sección de arriba está hecha o explicada en **Estado**, y la sección **Estado** está completa.

## Estado

_(lo completa el agente al terminar)_
