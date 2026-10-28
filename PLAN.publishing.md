# PLAN — Publicación multi-red (backend)

Paso 2 de la salida de Postiz (Fase 7): que AloStudio programe y publique contenido en redes sociales, como hoy lo hace Postiz. Esta tanda es **solo backend** (modelo, adaptadores, cola, API y MCP). El calendario y el compositor del frontend van en una tanda aparte.

Rama `feat/publishing`, worktree `C:\Users\Zeek\Desktop\AloStudio-publishing`. Lo implementa un agente y lo revisa Claude contra este documento.

## Decisiones del dueño

- **Módulo genérico:** una publicación se escribe y programa una vez y sale a una o más redes. Cada red es un **adaptador** detrás de una interfaz común.
- **Redes de esta tanda:** **Instagram** (la principal; AloStudio ya publica en Instagram) y **páginas de Facebook**.
- El calendario va a mostrar publicaciones de todas las redes juntas.

## Regla de licencia (la más importante)

Esto reemplaza una función de Postiz (AGPL). El código tiene que ser **escrito desde cero**: no abras, no leas y no copies nada de `C:\Users\Zeek\Desktop\Postiz` ni de ningún repo de Postiz o fork. Las fuentes permitidas son la documentación oficial de Meta (Graph API para Pages y la de Instagram que ya usa este repo), este plan y el código de este worktree. En el mensaje del commit de cada adaptador anotá de qué fuentes salió.

## Reglas para el agente

1. Trabajá **solo** dentro de `C:\Users\Zeek\Desktop\AloStudio-publishing`. No leas `C:\Users\Zeek\Desktop\Postiz` ni `C:\Users\Zeek\Desktop\AloStudio` (salvo usar su `.venv`).
2. Solo backend: `app/`, `alembic/`, `tests/`. No toques `frontend/`.
3. **Código genérico sin nombres de red:** en el dominio `publishing` (modelos, servicio, router, cola, tools MCP) no puede aparecer `instagram`, `facebook` ni ningún `if network == ...`. Todo lo específico de una red vive en su adaptador. Si el código genérico necesita algo de una red, se agrega un método a la interfaz del adaptador y cada adaptador lo implementa.
4. Sin dependencias nuevas. Para HTTP usá `httpx` como el resto del repo; en tests, `respx` (ya está).
5. No cambies el comportamiento de lo que ya existe en `app/domains/instagram/` (posts de Instagram, comentarios, autorespuestas): el adaptador de Instagram **usa** ese servicio, no lo reescribe.
6. Prohibido: `git push`, `ssh`, tocar `.env*`, `docker compose down`, borrar contenedores o volúmenes, editar migraciones existentes.
7. Commits chicos en `feat/publishing`, en español con el estilo del repo (`feat(publishing): ...`, `test(publishing): ...`), terminados con `Co-Authored-By: Antigravity <noreply@google.com>`.
8. Al terminar, completá **Estado** al final: qué se hizo, qué quedó, y la salida real de cada verificación diciendo sobre qué archivos o tests corrió.

## Entorno

- Python: `..\AloStudio\.venv\Scripts\python.exe` (con el cwd en este worktree, `import app` resuelve acá).
- Tests: Postgres y Redis de Docker ya corriendo. `..\AloStudio\.venv\Scripts\python.exe -m pytest <archivos> -q -p no:cacheprovider`.
- Lint: `..\AloStudio\.venv\Scripts\python.exe -m ruff check app tests` (en `scripts/` hay 2 errores viejos que no son tuyos).
- Migración: head actual `c6d7e8f9a0b1`.

## Lo que ya existe y hay que reutilizar

- **Instagram:** `app/domains/instagram/publishing_service.py` (`create_post`, `publish_post`, validaciones de `media_type` y `source`, límites de caption), modelo `InstagramPost` (`app/domains/instagram/models.py`), worker `app/workers/instagram.py` (patrón `enqueue_publish` con fallback inline cuando no hay pool de ARQ), `fire_due_instagram_posts` en el tick del scheduler (`app/workers/scheduler.py`). Leelo entero antes de diseñar el adaptador.
- **Páginas de Facebook:** canal `FacebookPage` en `app/domains/inboxes/models.py` (`page_id`, `page_access_token`), cliente de envío en `app/domains/facebook/sender.py` (cómo llama a Graph con el token de página).
- **Canales:** cada red conectada es un `Inbox` de la cuenta con su canal. Un destino de publicación se identifica por `inbox_id`.
- **Patrones de dominio:** `app/domains/appointments/` y `app/domains/products/` (models, schemas, service, presenters, router), permisos en `app/core/deps.py`, tools MCP en `app/mcp/tools/appointments.py`, tests en `tests/integration/test_appointments.py` y `test_mcp_appointment_tools.py`.

## 1. Modelo (`app/domains/publishing/models.py`) y migración

**`Publication`** (tabla `publications`, `TimestampMixin`):

| Campo | Regla |
|---|---|
| `id` BigInteger PK | |
| `account_id` FK `accounts` CASCADE | |
| `content` Text, null | el texto base de la publicación |
| `media` JSONB, not null, default `[]` | lista de `{"type": "image" \| "video", "url": str}` en orden; URLs públicas que Meta pueda descargar |
| `scheduled_for` timestamptz, null | null = publicar ahora |
| `state` String not null | `draft`, `scheduled`, `publishing`, `published`, `partially_published`, `failed` |
| `created_by_id` FK `users` SET NULL, null | |
| `published_at` timestamptz, null | cuando terminó el último destino |

**`PublicationTarget`** (tabla `publication_targets`):

| Campo | Regla |
|---|---|
| `id` BigInteger PK | |
| `publication_id` FK `publications` CASCADE | |
| `account_id` FK `accounts` CASCADE | |
| `inbox_id` FK `inboxes` CASCADE | el canal destino |
| `network` String not null | clave del adaptador (la escribe el adaptador, el código genérico solo la guarda) |
| `settings` JSONB not null default `{}` | opciones propias de la red (ej. tipo de post de Instagram); las valida el adaptador |
| `content_override` Text, null | texto distinto para este destino, opcional |
| `state` String not null | `pending`, `publishing`, `published`, `failed` |
| `external_id`, `permalink` String null | lo que devuelve la red |
| `error_code`, `error_message` | último error, en texto que entienda un humano |
| `attempts` Integer default 0 | |
| `published_at` timestamptz null | |
| `extra` JSONB default `{}` | referencias del adaptador (ej. id del `InstagramPost` creado) |

Índices: `publications(account_id, scheduled_for)`, `publications(state, scheduled_for)`, `publication_targets(publication_id)`, `publication_targets(account_id, inbox_id)`; único `(publication_id, inbox_id)`. Migración nueva con `down_revision = "c6d7e8f9a0b1"`, `upgrade` y `downgrade`.

Estado de la publicación = agregado de sus destinos: todos `published` → `published`; alguno `published` y alguno `failed` → `partially_published`; todos `failed` → `failed`.

## 2. Adaptadores (`app/domains/publishing/adapters/`)

`base.py` con la interfaz (Protocol o clase abstracta) y un registro:

- `network: str` (clave estable).
- `supports(inbox, channel) -> bool`: si ese canal puede publicar con este adaptador.
- `channel_label(inbox, channel) -> dict`: datos para mostrar el destino (nombre, usuario o página, avatar si hay).
- `validate(publication, target) -> list[str]`: errores legibles en español (ej. "Instagram necesita al menos una imagen o video", límites de largo, cantidad de medios, tipos permitidos, `settings` inválidos). El servicio genérico rechaza con 422 si hay errores.
- `async publish(session, publication, target) -> PublishResult`: publica **un** destino. Devuelve `external_id`, `permalink`, `extra`, o un error (`code`, `message`, `retryable: bool`). No lanza excepciones por errores de la red: los devuelve.

El registro resuelve el adaptador por `network` y, para un canal, el primero cuyo `supports` dé true.

**`instagram.py`:** usa `app/domains/instagram/publishing_service.py`. En `publish`, crea el `InstagramPost` con `create_post` (sin `scheduled_for`, porque la programación la maneja el módulo genérico) y lo publica con `publish_post`; mapea el estado final del `InstagramPost` al resultado y guarda su id en `extra`. `settings.post_type`: `feed` (imagen, video o carrusel según `media`), `reels` o `story`; derivá el `media_type` y el `source` que espera el servicio de Instagram a partir de `media` y `settings`. Así los posts siguen apareciendo en la pantalla de posts de Instagram y las autorespuestas de comentarios siguen funcionando.

**`facebook_page.py`:** Graph API (la misma versión que usa el repo, `settings.meta_graph_api_version`) con el `page_access_token` del canal:

- Solo texto (y link si el texto tiene uno): `POST /{page-id}/feed` con `message`.
- Una imagen: `POST /{page-id}/photos` con `url` y `message`.
- Varias imágenes: subí cada una con `POST /{page-id}/photos` y `published=false`, y después `POST /{page-id}/feed` con `message` y `attached_media`.
- Un video: `POST /{page-id}/videos` con `file_url` y `description`.
- Mezcla de imágenes y video: no soportado, error de `validate`.
- `permalink`: pedilo con `GET /{post-id}?fields=permalink_url` cuando la respuesta no lo traiga.
- Errores de Graph: mapealos a mensajes en español. Falta de permiso (códigos 10, 200 o similares) → "La página no dio permiso para publicar (pages_manage_posts). Volvé a conectarla o esperá la aprobación de Meta." `retryable` true para límites de tasa y errores 5xx; false para permisos, token vencido o datos inválidos.

## 3. Servicio y cola

`app/domains/publishing/service.py`:

- `create_publication(session, account_id, created_by_id, payload)`: valida que cada `inbox_id` sea de la cuenta (si no, 422) y que algún adaptador lo soporte; asigna `network`; corre `validate` de cada adaptador; estado `scheduled` si viene `scheduled_for` futuro, `draft` si `draft: true`, y si no, `scheduled` con `scheduled_for = now` y encola ya.
- `update_publication`: solo en `draft` o `scheduled`; permite cambiar texto, medios, fecha y destinos.
- `delete_publication`: solo en `draft`, `scheduled` o `failed`.
- `retry_publication`: vuelve a `pending` los destinos `failed` y encola.
- `list_publications`: filtros `from`/`to` (sobre `scheduled_for`, y para las ya publicadas sobre `published_at` si no tienen fecha), `state`, `inbox_id`, `page`. Para el calendario.
- `list_channels`: los inboxes de la cuenta que algún adaptador soporta, con `network` y `channel_label`.

**Cola** (`app/workers/publishing.py`), siguiendo el patrón de `app/workers/instagram.py`:

- `fire_due_publications(session)`: llamado desde el tick del scheduler junto a `fire_due_instagram_posts`. Toma las `scheduled` con `scheduled_for <= now`, las pasa a `publishing` **con una actualización condicional** (solo si siguen en `scheduled`), para que dos ticks o dos workers nunca publiquen dos veces, y encola `publish_publication_task(publication_id)`.
- `publish_publication_task`: publica cada destino en `pending` por separado (uno que falla no frena a los demás), cuenta `attempts`, guarda resultados y recalcula el estado de la publicación. Un destino ya `published` nunca se vuelve a publicar. Errores `retryable`: reintento con espera, como el throttle de Instagram (máximo 3).
- Registrá la tarea en el worker como las demás.
- Publicar ahora: `enqueue` con fallback inline igual que Instagram.

## 4. API

Router `/api/v1/accounts/{account_id}/publications` (registrarlo en `app/main.py`):

- `GET /channels`, `GET ""`, `POST ""`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`, `POST /{id}/retry`.
- Permisos: leer y escribir, admin o agente (como la agenda).
- Presenter: la publicación con sus destinos (estado, error, permalink, red y etiqueta del canal), fechas ISO 8601.

## 5. MCP

`app/mcp/tools/publishing.py`, registrado como los demás: `list_publication_channels`, `list_publications(from, to, state)`, `create_publication(content, media, inbox_ids, scheduled_for=None, settings=None)`, `cancel_publication(publication_id)` (borra si está en `draft`/`scheduled`). Escritura con `requires("write")`. Llaman al servicio, sin lógica duplicada.

## 6. Tests

- `tests/integration/test_publishing.py`: CRUD, inbox de otra cuenta → 422, canal sin adaptador → 422, errores de `validate` → 422, editar o borrar una publicada → 422, agente puede crear, filtros del listado.
- `tests/integration/test_publishing_worker.py`: `fire_due_publications` toma solo las vencidas; dos llamadas seguidas no encolan dos veces; un destino falla y el otro publica → `partially_published`; retry solo reintenta los fallidos; un destino publicado no se republica.
- `tests/integration/test_publishing_facebook.py` con `respx`: texto, una imagen, varias imágenes (`attached_media`), video, error de permiso → mensaje en español y no reintentable, límite de tasa → reintentable.
- `tests/integration/test_publishing_instagram.py`: el adaptador crea el `InstagramPost` y lo publica (mockeá `publish_post`/Graph como hacen los tests de Instagram existentes); mapeo de `post_type` y `media` a `media_type`/`source`; errores.
- `tests/integration/test_mcp_publishing_tools.py`.
- Corré también los tests de Instagram existentes para confirmar que nada cambió (`tests/integration/test_instagram*.py`).

## Fuera de alcance

Frontend (calendario y compositor: tanda siguiente), biblioteca de medios y subida de archivos, analytics, otras redes, cambiar los permisos que pide la conexión de páginas de Facebook (hoy no pide `pages_manage_posts`; se agrega cuando Meta lo apruebe), importar posts de Postiz, programación nativa de Meta (`scheduled_publish_time`). Si algo parece necesario, anotalo en **Estado**.

## Terminado cuando

Todos los tests nuevos y los de Instagram pasan, `ruff check app tests` sin errores, `alembic heads` con un solo head, ninguna mención de red en el código genérico de `app/domains/publishing/` fuera de `adapters/`, y **Estado** completo.

## Estado

Lo implementó Claude (Antigravity se quedó sin cuota al arrancar), con las mismas reglas: escrito desde cero, sin leer Postiz. Fuentes: la referencia de la Graph API de Meta para páginas (feed, photos, videos, errores) y el código de este repo.

**Hecho**

- Modelo `Publication` / `PublicationTarget` y migración `d7e8f9a0b1c2` (sube y baja limpia sobre la base de tests).
- Adaptadores en `app/domains/publishing/adapters/`: interfaz (`supports`, `channel_label`, `validate`, `publish`) y registro; `instagram` reutiliza `create_post` / `publish_post` / `reset_for_retry` del servicio de Instagram; `facebook_page` publica texto (con link), una imagen, varias imágenes (`attached_media`) y video (host de video), con errores en español.
- Servicio, cola (`app/workers/publishing.py`), tick del scheduler y tarea registrada en el worker (timeout de 30 min), API `/publications` y tools MCP `list_publication_channels`, `list_publications`, `create_publication`, `cancel_publication`.
- Fuera de `adapters/`, ningún archivo del dominio nombra una red.

**Cambios por la revisión de patrones (agente revisor)**

- Commit por destino en `publish_pending_targets`: una publicación aceptada por la red sobrevive a un crash o timeout del trabajo, así no se republica.
- `recover_stale_publications` en cada tick: una publicación trabada en `publishing` más de 60 min se re-encola; un destino agarrado a mitad de publicar queda `failed` con "no se sabe si salió", no se reenvía.
- Si encolar falla, el reclamo se libera y el próximo tick lo reintenta.
- El reclamo vuelve a chequear la fecha; las mutaciones bloquean la fila (`for_update`); editar solo el texto no exige fecha futura; cero destinos = `failed`.
- Facebook: timeout al publicar = no reintentable (puede haber salido); falla del permalink no anula la publicación; token en el cuerpo del POST, no en la URL.
- **Decisión a confirmar con el dueño:** escritura solo para administradores (como la publicación de Instagram existente); los agentes leen. El plan decía admin o agente.

**Verificaciones (corridas por Claude)**

- `ruff check app tests` → All checks passed.
- `alembic heads` → `d7e8f9a0b1c2 (head)`, uno solo.
- Tests nuevos: `test_publishing.py` (13), `test_publishing_worker.py` (10), `test_publishing_facebook.py` (12), `test_publishing_instagram.py` (9), `test_mcp_publishing_tools.py` (3).
- Suite amplia: nuevos + `test_scheduler.py` + `test_instagram_*.py` + `test_mcp_*.py` + `test_facebook_*.py` → **349 passed**.

**Pendiente**

- Frontend: calendario y compositor (tanda siguiente).
- Facebook en producción necesita `pages_manage_posts` en la conexión de páginas y aprobado por Meta.
- La base de tests local quedó migrada a `d7e8f9a0b1c2`.

## Canales de publicación (2026-10-28)

Para sumar redes que no son bandejas (Threads, TikTok, YouTube, LinkedIn, X, Google Business Profile, Telegram, Discord, Slack, Twitch), el destino de una publicación dejó de ser una bandeja y pasó a ser un **canal de publicación** (`PublishingChannel`, tabla `publishing_channels`, migración `0a1b2c3d4e5f`).

- **Instagram y páginas de Facebook** siguen publicando con las credenciales de su bandeja: cada bandeja que un adaptador `supports` tiene un canal con `inbox_id`, creado y renombrado por `sync_inbox_channels` (al listar canales y antes de la foto diaria de estadísticas). Borrar la bandeja borra su canal.
- **Las redes nuevas** guardan sus credenciales en el canal (`credentials`, `token_expires_at`, `external_id` de la cuenta en la red) y no tocan las bandejas. `status = "reconnect"` (con `status_message`) marca un canal cuyo token dejó de servir: no se puede elegir para publicar ni se le toman estadísticas.
- `PublicationTarget` y `ChannelMetricSnapshot` apuntan a `channel_id`. La migración crea un canal por cada bandeja que ya usaban y traslada las filas; el downgrade las devuelve (y descarta las de canales sin bandeja).
- API, MCP y webhooks hablan de `channel_id`: `GET /publications/channels` devuelve `{id, network, name, username, avatar_url, inbox_id, status, status_message}` (nunca `credentials`); los destinos se crean con `{"channel_id"}`; los filtros de listado y estadísticas son `channel_id`; la tool MCP `create_publication` recibe `channel_ids`; el webhook `publication_completed` manda `channel_id` y, si hay bandeja, `inbox_id`.
- Adaptadores: `supports(inbox)` ahora es opcional (por defecto `False`), `fetch_channel_metrics` recibe el canal y `channel_inbox(session, channel_id)` da la bandeja a los adaptadores que la usan. Se quitó `channel_label`.

**Siguiente paso:** conexión de cuentas para las redes nuevas: `POST /publications/channels/connect/{network}` → URL de autorización con `state` firmado, callback que crea o actualiza el canal (upsert por `account_id, network, external_id`), `DELETE /publications/channels/{id}` para los canales sin bandeja, y refresco de tokens antes de publicar. La primera red sería Threads, que usa la app de Meta existente y se puede probar con cuentas que tengan rol en la app antes de la revisión de Meta.
