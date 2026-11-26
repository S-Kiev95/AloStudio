# Auditoría de rendimiento del panel de AloStudio — 2026-11-26

Fecha de medición: `2026-11-26`  
Rama auditada: `audit/rendimiento` (base `origin/develop`, commit `ceb5a59`)  
Entorno medido (solo lectura): VPS de pruebas `vmi3426238` (`https://vmi3426238.tail34088e.ts.net`, 6 vCPU, 11,7 GiB RAM) y pruebas locales aisladas en este worktree.

---

## 1. Resumen corto para el dueño

La sensación de que el panel «de a rato está lento» (y que acciones como tocar **«Resolver»** tarden en reflejarse) no viene de que al servidor le falte memoria ni de que los otros proyectos en Docker lo estén ahogando: la máquina tiene **6,7 GiB de RAM libres** y **~85–90 % de CPU libre** casi todo el tiempo. El tiempo se va en **cinco lugares concretos**:

1. **Cada clic esperaba viajes largos de red de ida y vuelta antes de cambiar la pantalla:** el servidor de pruebas está en Europa (`79.143.191.181`) y desde acá cada viaje por Tailscale tarda **~243 ms** de piso (**317–368 ms** por pedido API con conexión abierta, **~1,1 s** en frío). Botones como «Resolver» no cambiaban el estado en el momento: esperaban a ir al servidor y después volver a pedir la conversación y la bandeja entera (**2 viajes en serie = 0,7 a 1,2 s de piso** aun con servidor instantáneo).
2. **Abrir, marcar como vista o resolver una conversación con historia cargaba datos de más en la base:** una conversación real del servidor con 726 mensajes disparaba **50 consultas SQL y 666 ms** solo para leerse, y al tocar «Resolver» se volvía a recargar entera una segunda vez (**>1,3 s** solo leyendo relaciones de usuarios, cuentas y mensajes viejos que la respuesta ni siquiera usa). Además, la bandeja de entrada carga en memoria **todos los mensajes históricos** de las 25 conversaciones visibles (**1.139 a 2.259 mensajes, 241–472 ms**) solo para mostrar el último renglón y contar no leídos.
3. **`alostudio-embeddings` llevaba 11 días trabado en un bucle infinito de timeouts cada 3 minutos:** no es que el backend lo llame en cada pedido, sino que la tarea `embed_messages_task` del worker le mandaba de a **16 mensajes juntos** (algunos de hasta 5.900 caracteres) con un tope de espera de **15 segundos**. Como en CPU ese lote tarda ~30–35 s, a los 15 s el worker cortaba sin guardar nada (**6.305 corridas fallidas seguidas, 0 mensajes guardados**), mientras el servicio de embeddings seguía calculando en vano durante otros ~20 s usando 2 núcleos (**de ahí el 30,5 % de CPU promedio constante y 80,7 horas de CPU acumuladas**) y dejando bloqueado su candado interno para las búsquedas por significado que cayeran justo ahí.
4. **El panel descarga los 7 idiomas juntos (~1,1 MB de JS crudo / 347,5 kB comprimidos) y frena el cambio de pantalla con una transición de 240 ms:** todas las páginas cargan español, inglés, portugués, francés, alemán, japonés y coreano en el mismo paquete inicial (**511–545 kB gzip** en vez de ~195 kB). Encima, al hacer clic entre conversaciones o secciones, `template.tsx` congela la captura de pantalla hasta **240 ms** esperando al servidor (que está a 243 ms) y `AccountLayout` vuelve a pedir `/api/v1/profile` sin caché en cada navegación.
5. **Hay un solo proceso de backend (`uvicorn`) con `LOG_LEVEL=DEBUG` y envíos salientes en el mismo pedido:** cuando entran webhooks de WhatsApp/Instagram bajando y subiendo fotos a MinIO o un agente envía un mensaje (que espera en línea la respuesta de Meta o del servidor SMTP), todo comparte un único proceso Python y escribe trazas `DEBUG` en disco, encolando momentáneamente los pedidos del panel que coincidan en ese segundo.

### Qué conviene arreglar primero (y qué ya quedó listo en esta rama)

En esta rama (`audit/rendimiento`) ya dejamos aplicados y probados **3 arreglos chicos, seguros y sin tocar esquemas de base** en commits separados:
- **`6937ef9` — Embeddings:** bajamos el lote de vectorización de mensajes de `16` a `4` (y el de backfill de `32` a `8`) para que cada pasada entre holgada debajo de los 15 s y corte el bucle infinito de CPU.
- **`77859fb` — Backend conversaciones/perfil/notificaciones:** acotamos las relaciones cargadas en `GET /conversations/{id}`, `POST /update_last_seen`, `POST /toggle_status`, `GET /api/v1/profile` y `GET /notifications`, eliminamos el `refresh` completo del grafo al cambiar estado/prioridad/etiquetas, y confirmamos (`commit`) antes de devolver la respuesta HTTP.
- **`432fda3` — Panel tiempo real y «Resolver»:** actualización optimista inmediata en `useToggleStatus` («Resolver» / «Reabrir» cambia al instante), freno de refetches innecesarios en `useMarkSeen` cuando la conversación ya estaba leída, e invalidación acotada por conversación en `useCable` (ignorando eventos `typing_on/off`).

Para el próximo paso de fondo, el orden recomendado es: **1.º** dejar de cargar todos los mensajes en `conversation_finder` (`H2`), **2.º** separar los idiomas del bundle cliente (`H5`), **3.º** pasar `LOG_LEVEL=INFO` y `--workers 2` en el servidor (`H7`), y **4.º** agregar los índices propuestos en PostgreSQL (`H8`).

---

## 2. Hallazgos ordenados por impacto

### H1 · Explosión de consultas ORM (`lazy="selectin"`), doble recarga en «Resolver» y carrera de `commit`
- **Impacto:** Muy alto (afecta abrir cualquier chat, marcarlo como visto, resolverlo, cambiar prioridad/etiquetas y pedir `/api/v1/profile`).
- **Qué pasa:**
  1. En el código casi todas las relaciones SQLModel están declaradas con `lazy="selectin"`. Mientras que `GET /conversations` (`finder.py`) y `GET /conversations/{id}/messages` ya usaban `lazyload("*")` para cortar la cascada, el resto de endpoints de conversación llamaban a `_load_conversation_by_display_id()` sin `options`, trayendo en cadena `Account` → todos sus `AccountUser` → todos sus `User` → todos sus `AccessToken`, `Inbox` → `InboxMember`, `Contact` → `Note` y **todos los `Message` + `Attachment` de la historia de la conversación**.
  2. En `toggle_status()` (y también en `toggle_priority` y `update_labels`), después del `flush()` se ejecutaba `await session.refresh(conversation)` sin lista de atributos, lo que **expiraba y volvía a consultar por segunda vez todo ese grafo de relaciones** cuando solo había cambiado `updated_at`.
  3. `GET /api/v1/profile` (`_render_user`) cargaba `AccountUser` sin `lazyload("*")`, disparando la carga de todos los usuarios colegas de cada cuenta y sus `access_tokens`. Lo mismo pasaba en `GET /notifications` al hidratar las conversaciones asociadas.
  4. `get_session()` recién hacía `await session.commit()` al salir del generador de dependencias, **después** de que `ActionCableListener` ya había publicado los eventos por Redis (`/cable`) y al borde de la entrega de la respuesta HTTP. Si el refetch del navegador llegaba antes del `commit`, leía el estado viejo (`open`) hasta el próximo sondeo de 15 s.
- **Medición que lo prueba:**
  - Medido en lectura sobre la base real de `vmi3426238` (`display_id=456`, conversación con **726 mensajes**):
    - `select(Conversation)` sin `options` + `present_conversation_show`: **50 consultas SQL en 666,0 ms** (`8× accounts`, `8× account_users`, `8× users`, `8× access_tokens`, `4× inboxes`, `4× inbox_members`, `2× contacts`, `2× notes`, `2× attachments`, `1× messages`, `1× contact_inboxes`, `1× conversations`).
    - `select(Conversation).options(lazyload("*"))` (lo único que necesita `update_last_seen` o `list_labels`): **1 consulta SQL en 11,0 ms** (**60× más rápido**).
    - En `POST /toggle_status` sobre esa misma conversación, la carga inicial (666 ms) + el `refresh(conversation)` completo (+666 ms) + el `refresh(msg)` del mensaje de actividad insumían **>1,5 s y >120 consultas SQL** en un único proceso Python.
  - En `pg_stat_user_tables` de staging (con apenas 13 usuarios y 9 tokens en la base), esa cascada explica las **311.248 lecturas secuenciales (`seq_scan`) en `users`**, **141.861 en `account_users`** y **170.653 en `access_tokens`**.
  - Verificado después del arreglo en test de integración HTTP completo (`tests/integration/test_conversation_list_queries.py`, incluyendo autenticación y chequeo de membresía): `GET /conversations/{id}` = **9 consultas**, `POST /update_last_seen` = **6 consultas**, `POST /toggle_status` = **33 consultas** (incluyendo mensaje de actividad y 3 eventos de ciclo de vida), `GET /api/v1/profile` = **5 consultas**.
- **Dónde está en el código:**
  - [`app/domains/conversations/router.py:153-201`](../app/domains/conversations/router.py#L153-L201), [`app/domains/conversations/router.py:624-734`](../app/domains/conversations/router.py#L624-L734), [`app/domains/conversations/router.py:1045-1114`](../app/domains/conversations/router.py#L1045-L1114)
  - [`app/domains/conversations/service.py:307-347`](../app/domains/conversations/service.py#L307-L347), [`app/domains/conversations/service.py:374-379`](../app/domains/conversations/service.py#L374-L379), [`app/domains/conversations/service.py:745-750`](../app/domains/conversations/service.py#L745-L750)
  - [`app/domains/users/router.py:157-200`](../app/domains/users/router.py#L157-L200)
  - [`app/domains/notifications/router.py:80-100`](../app/domains/notifications/router.py#L80-L100)
  - [`app/core/db.py:43-53`](../app/core/db.py#L43-L53) y [`app/domains/conversations/listeners.py:111-172`](../app/domains/conversations/listeners.py#L111-L172)
- **Propuesta de arreglo y riesgo:**
  - **Ya aplicado en commit `77859fb` (riesgo bajo):** pasamos `options=_list_loaders()` en `show_conversation`, `update_conversation`, `toggle_status_endpoint`, `toggle_priority_endpoint` y `set_labels`; pasamos `options=(lazyload("*"),)` en `update_last_seen_endpoint`, `list_labels` y `index_notifications`; acotamos `_render_user` en `/api/v1/profile`; cambiamos `session.refresh(conversation)` a `session.refresh(conversation, ["updated_at"])`; y agregamos `await session.commit()` explícito antes de responder en las mutaciones de conversación (igual que ya hacía `create_message_endpoint`).
  - **Propuesta adicional (riesgo bajo-medio):** hacer que `ActionCableListener` publique en Redis desde un gancho `after_commit` de SQLAlchemy (idéntico a lo que ya hace [`app/domains/webhooks/listener.py:175-185`](../app/domains/webhooks/listener.py#L175-L185)), así ningún evento de WebSocket sale antes de que Postgres confirme la transacción; y pasar `options=(lazyload("*"),)` también en [`app/domains/calls/service.py:96`](../app/domains/calls/service.py#L96) (`present_call`).

---

### H2 · La bandeja de conversaciones carga todos los mensajes históricos de las 25 filas en cada refresco
- **Impacto:** Alto hoy y crítico al escalar volumen (es el endpoint más llamado del sistema).
- **Qué pasa:**
  - `_list_loaders()` en `finder.py` incluye `selectinload(Conversation.messages).selectinload(Message.attachments)` sin límite por conversación.
  - Eso trae a Python **absolutamente todos los mensajes históricos** (con sus 4 columnas JSON/JSONB y adjuntos) de las 25 conversaciones de la página, únicamente para que `present_conversation()` tome el último mensaje (`conv.messages[-1]`), el último mensaje que no sea de actividad y cuente hasta 10 entrantes posteriores a `agent_last_seen_at` (`_unread_incoming_count`).
  - El mismo patrón se repite en `POST /conversations/filter` y `GET /conversations/search`.
- **Medición que lo prueba:**
  - En `~/logs/backend.log`, `GET /api/v1/accounts/{id}/conversations` es el **endpoint #1 en volumen** (`678` llamadas registradas).
  - En `alostudio-postgres` (`EXPLAIN ANALYZE`), buscar las 25 conversaciones abiertas tarda apenas **0,63 ms**, pero `conversation_finder` completo tarda:
    - **`240,7 ms`** en `status=open` (instanciando **1.139 objetos `Message`** en 14 consultas).
    - **`472,3 ms`** en `status=all` (instanciando **2.259 objetos `Message`** en 16 consultas, partiendo la carga de `attachments` en 5 consultas `IN (...)` de ~500 IDs cada una).
  - En `pg_stat_user_tables`, con solo `4.422` mensajes totales en la tabla `messages`, Postgres ya acumula **3.345.717 filas devueltas por índice (`idx_tup_fetch`)** y **983.335 por escaneo secuencial**. Cuando un cliente tenga 25 conversaciones activas de 500–1.000 mensajes cada una, cada refresco de bandeja leerá 15.000+ filas JSON y bloqueará el backend >2 segundos.
- **Dónde está en el código:**
  - [`app/domains/conversations/finder.py:292-301`](../app/domains/conversations/finder.py#L292-L301)
  - [`app/domains/conversations/filter.py:345-360`](../app/domains/conversations/filter.py#L345-L360)
  - [`app/domains/conversations/presenters.py:378-395`](../app/domains/conversations/presenters.py#L378-L395) y [`app/domains/conversations/presenters.py:454-525`](../app/domains/conversations/presenters.py#L454-L525)
- **Propuesta de arreglo y riesgo:**
  - **Propuesta:** quitar `selectinload(Conversation.messages)` de `_list_loaders()` y resolver en una sola consulta SQL acotada (con `LATERAL` o `ROW_NUMBER() OVER (PARTITION BY conversation_id ORDER BY id DESC)`) únicamente los IDs del último mensaje, del último mensaje no-actividad y el conteo `LEAST(COUNT(*), 10)` de no leídos para los 25 `conversation_id` de la página; cargar solo esos ≤50 `Message` con sus `attachments` e inyectarlos al presentador. Baja el costo a constante `O(25)` (~20–30 ms) sin importar cuántos miles de mensajes tenga cada hilo.
  - **Riesgo:** Medio (requiere cuidar que el contrato JSON de `present_conversation` —`messages` con 1 elemento, `last_non_activity_message` y `unread_count`— quede idéntico byte por byte; está bien cubierto por `tests/integration/test_conversation_list_queries.py`).

---

### H3 · Latencia de red Tailscale (~243 ms RTT) multiplicada por falta de UI optimista y exceso de invalidaciones en `/cable`
- **Impacto:** Alto en la percepción directa del usuario al hacer clic o recibir eventos.
- **Qué pasa:**
  1. El VPS `vmi3426238` está físicamente en Europa (`79.143.191.181`), por lo que cada ida y vuelta desde Sudamérica suma **~243 ms** incompresibles de velocidad de la luz + ruteo.
  2. Las mutaciones frecuentes del chat (`useToggleStatus`, `useAssignAgent`, `useAssignTeam`, `useTogglePriority`, `useSetLabels`) no actualizaban la caché de React Query en `onMutate`: mostraban spinner durante el `POST` (~320–500 ms) y recién en `onSuccess` llamaban a `invalidateQueries`, disparando un **segundo viaje de red completo** (`GET /conversations/{id}` + `GET /conversations`, otros ~350–700 ms) antes de cambiar el estado visual.
  3. `useMarkSeen` se dispara al abrir cualquier conversación y, en `onSuccess`, invalidaba siempre `["conversations", accountId]` aunque la conversación ya tuviera `unread_count === 0`, forzando otro `GET /conversations` completo en cada clic de la lista.
  4. `useCable` invalidaba de forma global `["conversations", accountId]`, `["messages", accountId]` y `["conversation", accountId]` ante cualquier evento entrante, **incluidos `conversation.typing_on` y `conversation.typing_off`**, y además al resolver una conversación el backend emite **3 eventos seguidos** (`conversation.status_changed`, `conversation.updated` y `message.created` por la nota de actividad), provocando ráfagas de refetches sobre conversaciones que ni siquiera eran la abierta.
- **Medición que lo prueba:**
  - `tailscale ping vmi3426238`: conexión directa WireGuard UDP en **243 ms**.
  - `curl` externo a `https://vmi3426238.tail34088e.ts.net/login` (6 corridas en frío): DNS `4–15 ms`, TCP `251–262 ms`, TLS `512–645 ms`, TTFB `797–952 ms`, total **`1,05 s – 1,21 s`**.
  - `curl` externo con `keep-alive` reutilizando TLS hacia `/api/backend/health`: 1.º pedido `1,06 s`, 2.º y 3.º pedido **`317 ms – 368 ms`** (contra **`42–47 ms`** medidos en `127.0.0.1:3000/api/backend/health` dentro del VPS: **~275–320 ms son puramente el tramo de red externo**).
  - Handshake WebSocket a `wss://vmi3426238.tail34088e.ts.net/cable`: conexión lista en **`818,5 ms`** y frame `{"type":"welcome"}` en **`829,8 ms`**.
- **Dónde está en el código:**
  - [`frontend/lib/api/conversations.ts:401-442`](../frontend/lib/api/conversations.ts#L401-L442) y [`frontend/lib/api/conversations.ts:523-649`](../frontend/lib/api/conversations.ts#L523-L649)
  - [`frontend/lib/realtime/use-cable.ts:28-119`](../frontend/lib/realtime/use-cable.ts#L28-L119)
- **Propuesta de arreglo y riesgo:**
  - **Ya aplicado en commit `432fda3` (riesgo bajo):** agregamos actualización optimista con rollback en `useToggleStatus` (el botón «Resolver» / «Reabrir» y el chip cambian en <16 ms sin esperar la red), evitamos invalidar `["conversations", accountId]` en `useMarkSeen` cuando la conversación ya tenía `unread_count === 0`, e hicimos que `useCable` ignore `conversation.typing_on/off` y acote la invalidación de `messages` y `conversation` al `display_id` afectado.
  - **Propuesta adicional (riesgo bajo):** extender el mismo patrón `onMutate` optimista a `useAssignAgent`, `useAssignTeam`, `useTogglePriority` y `useSetLabels`; y para producción con clientes en Argentina/Uruguay, alojar el VPS en São Paulo (`~35–45 ms` RTT) o Santiago/Buenos Aires en lugar de Europa (`243 ms` RTT), lo que recorta ~200 ms por cada viaje de red.

---

### H4 · `alostudio-embeddings` trabado hace 11 días en un bucle infinito de timeouts cada 3 minutos
- **Impacto:** Alto en consumo sostenido de CPU del servidor y bloqueos intermitentes de búsqueda semántica.
- **Qué pasa:**
  - Cada 3 minutos (`minutos 2, 5, 8, ...`), el cron `embed_messages_task` del worker busca los últimos `BATCH = 16` mensajes sin vector (`length(trim(content)) >= 12`, recortados a `1.000` caracteres) y llama a `POST http://127.0.0.1:8100/embed` con `timeout = 15,0 s` (`settings.embeddings_service_timeout`).
  - Los 16 mensajes pendientes que quedaron al tope de la cola incluyen transcripciones de llamadas y textos largos (7 mensajes de 509 a 5.906 caracteres). Codificar esos 16 textos en `EmbeddingGemma 2` (`float32`, 2 hilos CPU, `batch_size=4` interno) demora **~30–35 segundos**.
  - Exactamente a los **15,0 s**, `httpx` en el worker aborta por `ReadTimeout`, registra `messages.embed.unavailable` y **no inserta ninguna fila en `message_embeddings`**.
  - Sin embargo, en `app/embeddings_service/main.py`, `await asyncio.to_thread(_encode, texts)` **no puede cancelar un hilo nativo de PyTorch** cuando el cliente corta el socket: el servicio sigue quemando sus 2 hilos al 100 % durante otros ~20 s sosteniendo `lock = threading.Lock()`, descarta el resultado al terminar, y al minuto siguiente el cron vuelve a pedir **exactamente los mismos 16 mensajes** en un bucle sin fin.
  - Mientras ese `threading.Lock()` está tomado (~30–35 s cada 180 s), cualquier búsqueda interactiva por significado (F8 `search_messages`, Centro de Ayuda o autorespuesta de Instagram con `EMBEDDING_SHADOW=true`) queda esperando en la fila del candado y puede vencer también su timeout de 15 s.
- **Medición que lo prueba:**
  - `ps` / `top` en `vmi3426238`: PID `3475977` lleva `11-00:10:51` encendido con **`80 h 41 min` de tiempo de CPU acumulado** (`80,68 h / 264,18 h = 30,5 %` que reporta `ps`), repartido exactamente en los dos hilos de cómputo `TID 3476056` (`39 h 25 min`, `14,9 %`) y `TID 3487586` (`39 h 23 min`, `14,9 %`). Fuera de esa ventana (medido con `top -b -d 1` a las `21:10:21`), el proceso duerme en `futex_wait_queue` con **`0,0–1,0 %` de CPU** y **`1,74 GiB` de RAM RSS**.
  - `~/logs/worker.log`: `cron:embed_messages_task` ejecutó **6.305 corridas** sumando **86.678,8 s** de espera, con **`p50 = 15,15 s`**, **`p95 = 15,35 s`** y **`0` lotes exitosos** (`embed_messages batches with work: 0`).
  - Consulta en `alostudio-postgres`: hay `2.640` mensajes vectorizados y **`1.146` mensajes elegibles estancados**; los 16 primeros (`ids 6055..6036` y `2113`) tienen largos de `526`, `509`, `509`, `509`, `1.506`, `1.321` y `5.906` caracteres. Además, repetir esa consulta 6.305 veces generó **2.041.882 `idx_scan`** sobre `message_embeddings`.
- **Dónde está en el código:**
  - [`app/domains/conversations/message_embeddings.py:40-97`](../app/domains/conversations/message_embeddings.py#L40-L97)
  - [`app/core/config.py:113-115`](../app/core/config.py#L113-L115) y [`app/core/embeddings.py:107-117`](../app/core/embeddings.py#L107-L117)
  - [`app/embeddings_service/main.py:89-132`](../app/embeddings_service/main.py#L89-L132)
  - [`app/workers/embeddings_backfill.py:39-40`](../app/workers/embeddings_backfill.py#L39-L40)
- **Propuesta de arreglo y riesgo:**
  - **Ya aplicado en commit `6937ef9` (riesgo muy bajo):** bajamos `BATCH` de `16` a `4` en `message_embeddings.py` (alineado con el `batch_size=4` interno del servicio: no pierde throughput, tarda ~1,5–6 s por lote, confirma en la base cada 4 mensajes y suelta el `threading.Lock()` cada pocos segundos) y `BATCH_SIZE` de `32` a `8` en `embeddings_backfill.py`. Con esto, al desplegar, los `1.146` mensajes pendientes se completan en ~2–3 corridas del cron y el servicio vuelve a **~0 % de CPU**.
  - **Propuesta adicional (riesgo bajo):** usar un timeout corto (ej. `4–5 s`) para búsquedas interactivas del usuario (`TASK_QUERY`, que tiene fallback limpio a texto completo) y `30–60 s` para tareas de worker en segundo plano.

---

### H5 · Todas las pantallas del panel cargan los 7 idiomas completos (`347,5 kB` gzip / `1,09 MB` JS crudo)
- **Impacto:** Medio-alto (penaliza la primera carga, compilación/parseo JS en celulares y máquinas livianas).
- **Qué pasa:**
  - `frontend/lib/i18n/translate.ts` importa de manera estática los 7 diccionarios completos (`es`, `en`, `pt`, `fr`, `de`, `ja`, `ko` — 52 archivos por idioma = 364 módulos) en el objeto `MESSAGES`.
  - Como `I18nProvider` y utilidades cliente (`time.ts`, `client-t.ts`, `week-utils.ts`, `agent-time.ts`) importan `createTranslate` desde `translate.ts`, Webpack mete los 7 idiomas juntos en un único chunk compartido por prácticamente todas las rutas del panel.
- **Medición que lo prueba:**
  - Tamaño fuente de `frontend/lib/i18n/messages/`: **`1.308,9 KB`** (`es` 174,4 KB, `en` 171,2 KB, `pt` 182,0 KB, `fr` 192,0 KB, `de` 188,5 KB, `ja` 208,2 KB, `ko` 192,4 KB).
  - En la compilación de producción (`~/logs/build-ytc.log` y `.next/static/chunks/`):
    - El chunk `6413-21fb6fec436f3b8e.js` pesa **`1.092,5 KB` sin comprimir (`347,5 KB` gzip)** y contiene las cadenas de los 7 idiomas.
    - Por culpa de ese chunk, `First Load JS` salta de **`102–134 kB`** (en `/`, `/accounts`, `/hc/[slug]`) a **`511–545 kB` gzip** en todas las pantallas del panel (`/accounts/[accountId]/conversations/[id]` = **545 kB**, `/publications` = **537 kB**, `/contacts/[contactId]` = **534 kB**, `/login` = **524 kB**).
    - Nota: `Three.js` (`b536a0f1.*.js`, `673,3 KB` crudo / `167,2 KB` gzip + `1,48 MB` de modelos `.glb` en `public/brand/3d/`) está bien separado en un chunk dinámico solo para el login/portada, no contamina la bandeja.
- **Dónde está en el código:**
  - [`frontend/lib/i18n/translate.ts:1-11`](../frontend/lib/i18n/translate.ts#L1-L11)
  - [`frontend/lib/i18n/provider.tsx:12-33`](../frontend/lib/i18n/provider.tsx#L12-L33)
  - [`frontend/app/layout.tsx:39-60`](../frontend/app/layout.tsx#L39-L60)
  - Importadores cliente directos: [`frontend/lib/i18n/client-t.ts:2`](../frontend/lib/i18n/client-t.ts#L2), [`frontend/lib/time.ts:2`](../frontend/lib/time.ts#L2), [`frontend/components/agenda/week-utils.ts:3`](../frontend/components/agenda/week-utils.ts#L3), [`frontend/components/agent/agent-time.ts:3`](../frontend/components/agent/agent-time.ts#L3)
- **Propuesta de arreglo y riesgo:**
  - **Propuesta:** mover el mapa completo `MESSAGES` a un módulo `server-only`, resolver el diccionario fusionado (`{ ...es, ...MESSAGES[locale] }`) en `RootLayout` (Server Component) y pasarlo por props a `<Providers locale={locale} messages={messages}>`. En utilidades cliente (`time.ts`, `week-utils.ts`), recibir `t` por parámetro desde `useT()` (o usar `Intl.RelativeTimeFormat` nativo para fechas relativas). Reduce `First Load JS` de **~545 kB a ~240 kB gzip** (-300 kB gzip / -920 kB JS crudo).
  - **Riesgo:** Bajo-medio (toca ~8 archivos cliente y tests unitarios que hoy llaman a `useT()` sin montar `<I18nProvider>`; dejando `es` como fallback liviano en tests o en un setup de Vitest no se rompe ningún test).

---

### H6 · `ViewTransition` global de 240 ms chocando con el RTT de red, `getProfile()` sin caché por navegación y costo gráfico en modo oscuro
- **Impacto:** Medio (explica tirones visuales al cambiar de conversación o sección).
- **Qué pasa:**
  1. `AccountTemplate` registra un listener global `click` en fase de captura sobre cualquier `<a href="/accounts/...">` (incluyendo cada fila de `ConversationList`). Al hacer clic, llama a `document.startViewTransition()` pasando una promesa que retiene el frame congelado hasta **240 ms** esperando a que cambie `pathname`.
  2. Como el RTT al VPS es de **243 ms**, cuando Next.js tiene que buscar el payload RSC en el servidor, el timer de 240 ms expira **justo antes** de que llegue la respuesta, destraba la primera transición en vacío y milisegundos después `useIsomorphicLayoutEffect` dispara una **segunda `startViewTransition`** al cambiar `pathname`.
  3. En cada render RSC que pasa por `AccountLayout`, `getProfile()` hace `fetch` a `/api/v1/profile` con `cache: "no-store"` (`465` llamadas en `backend.log`, #6 en volumen), sumando ~50 ms extra de backend antes de entregar el RSC.
  4. Esas capturas de `ViewTransition` se componen encima de `.glass-panel` (`backdrop-filter: blur(18px) saturate(135%)`), `.glass-card` (`blur(14px)`), `body { background-attachment: fixed }` y, con barra lateral desplegada en modo oscuro, `NeonWordmark` corre un bucle continuo de `setTimeout` (`sequential` actualiza estado React 10 veces cada 200 ms; `random-beat` cada 400 ms) recalculando múltiples capas de `text-shadow`.
- **Medición que lo prueba:**
  - `GET /api/v1/profile` medido en servidor: **5 consultas y 51,5 ms**, llamado **465 veces** en `backend.log`.
  - Timer fijo en código (`240 ms`) vs. RTT medido (`243 ms` ping / `317–368 ms` HTTP keep-alive).
- **Dónde está en el código:**
  - [`frontend/app/accounts/[accountId]/template.tsx:63-149`](../frontend/app/accounts/%5BaccountId%5D/template.tsx#L63-L149)
  - [`frontend/app/accounts/[accountId]/layout.tsx:18-26`](../frontend/app/accounts/%5BaccountId%5D/layout.tsx#L18-L26) y [`frontend/lib/auth/profile.ts:28-40`](../frontend/lib/auth/profile.ts#L28-L40)
  - [`frontend/components/brand/neon-wordmark.tsx:82-275`](../frontend/components/brand/neon-wordmark.tsx#L82-L275) y [`frontend/app/globals.css:251-256`](../frontend/app/globals.css#L251-L256), [`frontend/app/globals.css:522-550`](../frontend/app/globals.css#L522-L550)
- **Propuesta de arreglo y riesgo:**
  - **Propuesta:**
    1. Excluir de `handleDocumentClick` en `template.tsx` los cambios internos dentro de `/conversations/*` (donde `InboxShell` ya mantiene montada la columna izquierda: no hace falta congelar toda la página con `startViewTransition` para cambiar el hilo central).
    2. Quitar `background-attachment: fixed` en `body` (en Chrome/Windows obliga a repintar en scroll junto con `backdrop-filter`).
    3. En `NeonWordmark`, correr la animación inicial (`ignite`) una vez y espaciar o llevar a CSS puro las escenas en reposo para no disparar renders de React cada 200–400 ms.
  - **Riesgo:** Bajo (cambio puramente visual; conviene validarlo con el ojo del dueño para respetar la estética Neon).

---

### H7 · Un solo proceso `uvicorn`, `LOG_LEVEL=DEBUG` en staging y llamadas externas en línea al enviar mensajes
- **Impacto:** Medio-alto en picos («de a rato se frena cuando entran cosas juntas»).
- **Qué pasa:**
  1. `alostudio-backend.service` corre `uvicorn app.main:app --host 127.0.0.1 --port 8000` con **un solo proceso** (`1 worker`).
  2. En `~/AloStudio/.env` del servidor está definido `APP_ENV=local` y `LOG_LEVEL=DEBUG`. Además, en `app/main.py` `configure_logging()` se ejecuta **antes** de `apply_overlay(session)`, así que aunque en `installation_configs` `app_env` sea `staging`, el nivel de log de Python y structlog queda configurado con lo que decía `.env` al arrancar (`DEBUG` + `ConsoleRenderer`). Resultado: `httpcore` y `httpx` escriben ~15 líneas `DEBUG` por cada request a MinIO o Meta, pasando cada una por `SecretRedactingFilter`.
  3. Al enviar un mensaje desde el compositor (`POST /conversations/{id}/messages`), `_apply_message_post_create` llama **en línea dentro del mismo request** a la API de Meta (WhatsApp Cloud, incluyendo `take_over_before_reply`, Instagram, Messenger), Telegram, Twilio o al servidor SMTP antes de devolver el `200 OK`.
  4. `devise_token_auth.py` cachea `bcrypt.checkpw` en memoria (`_verified`), lo cual evita pagar 250 ms en cada request, pero como esa caché vive en memoria de cada proceso y `alostudio-backend` se reinició **10 veces en las últimas 28 horas** por despliegues (tardando además **~20 s** en levantar cada vez, ej. `20:10:45Z` → `20:11:05Z`), el primer lote de pedidos tras cada reinicio bloquea el event loop ~250 ms por sesión en `bcrypt.checkpw`.
- **Medición que lo prueba:**
  - `~/AloStudio/.env` (claves no secretas): `APP_ENV=local`, `LOG_LEVEL=DEBUG`.
  - `~/logs/backend.log`: `24.479` líneas (`2,3 MB`) plagadas de `connect_tcp.started`, `send_request_headers.started`, `receive_response_body.started` de `httpcore`; ventana de indisponibilidad en reinicio medida en logs: `20:10:45.431Z` (`shutdown`) a `20:11:05.510Z` (`startup`) = **`20,1 s`**.
- **Dónde está en el código:**
  - [`app/main.py:154-173`](../app/main.py#L154-L173) y [`app/core/logging.py:115-141`](../app/core/logging.py#L115-L141)
  - [`app/domains/conversations/service.py:1265-1291`](../app/domains/conversations/service.py#L1265-L1291)
  - [`app/core/auth/devise_token_auth.py:118-135`](../app/core/auth/devise_token_auth.py#L118-L135)
  - Unidades en servidor: `~/.config/systemd/user/alostudio-backend.service` y `~/.config/systemd/user/alostudio-frontend.service` (que además corre `next start` con `output: "standalone"` emitiendo advertencia en `frontend.log` en vez de `node .next/standalone/server.js`).
- **Propuesta de arreglo y riesgo:**
  - **Propuesta:**
    1. Pasar `LOG_LEVEL=INFO` y `APP_ENV=staging` en `~/AloStudio/.env`, y mover `configure_logging()` en `app/main.py` para que re-aplique el nivel después de `apply_overlay(session)`.
    2. Correr `uvicorn` con `--workers 2` (el realtime `/cable` ya coordina por Redis pub/sub, así que múltiples workers funcionan sin perder eventos; consume solo ~230 MB extra de los 6,7 GiB libres y evita que un request lento o un `bcrypt` frío frene al resto).
    3. Más adelante, mover los envíos salientes lentos (sobre todo SMTP de correo) a tareas ARQ como hace Chatwoot (`SendReplyJob`).
  - **Riesgo:** Bajo para `LOG_LEVEL=INFO` y `--workers 2` (verificar únicamente que ningún estado en memoria sin Redis —fuera del caché idempotente `_verified` de bcrypt y el overlay de `installation_configs` que ya refresca por intervalo— asuma proceso único).

---

### H8 · Índices faltantes en PostgreSQL para crecimiento de datos (solo propuesta — NO aplicada)
- **Impacto:** Bajo-medio hoy en staging (tablas chicas en RAM), **alto en producción** cuando crezcan conversaciones y mensajes.
- **Qué pasa y medición en `alostudio-postgres`:**
  1. **`access_tokens` sin índice en `(owner_type, owner_id)`:** en `pg_stat_user_tables` registra **170.653 `seq_scan` y `0` `idx_scan`** (`855.227` filas leídas). Solo tiene `access_tokens_pkey (id)` y `ix_access_tokens_token (token)`. Cada búsqueda del token de un usuario o bot escanea toda la tabla.
  2. **`conversations` sin índice de ordenamiento para la bandeja (`account_id, status, last_activity_at DESC`):** `EXPLAIN (ANALYZE, BUFFERS)` de `SELECT id FROM conversations WHERE account_id = 1 AND status = 0 ORDER BY last_activity_at DESC LIMIT 25` hoy hace `Seq Scan` + `Sort` (`0,63 ms` con 366 filas). Existen `index_conversations_on_status_and_account_id (status, account_id)` y `conv_acid_inbid_stat_asgnid_idx`, pero ninguno incluye `last_activity_at DESC`, obligando a leer y ordenar todas las conversaciones abiertas de la cuenta en cada página.
  3. **`message_embeddings` en el cron `embed_pending`:** `EXPLAIN (ANALYZE, BUFFERS)` mostró un `Nested Loop Anti Join` recorriendo `2.656` filas de `messages_pkey` (`7.774` buffers en memoria, `14,5 ms` para apenas 4.422 mensajes). Con 500.000 mensajes históricos ya vectorizados, buscar los 4 nuevos sin vector recorrerá toda la tabla si no se acota por una ventana o cursor de `id`.
- **Dónde está en el código:**
  - [`app/domains/users/models.py:284-302`](../app/domains/users/models.py#L284-L302)
  - [`app/domains/conversations/models.py:329-390`](../app/domains/conversations/models.py#L329-L390)
  - [`app/domains/conversations/message_embeddings.py:79-88`](../app/domains/conversations/message_embeddings.py#L79-L88)
- **Propuesta de arreglo y riesgo (migración Alembic):**
  ```sql
  CREATE INDEX CONCURRENTLY ix_access_tokens_owner
    ON access_tokens (owner_type, owner_id);

  CREATE INDEX CONCURRENTLY ix_conversations_account_status_activity
    ON conversations (account_id, status, last_activity_at DESC);
  ```
  Y en `embed_pending`, guardar o consultar primero si hay mensajes nuevos (`id > COALESCE((SELECT max(message_id) FROM message_embeddings), 0)`) antes de buscar huecos hacia atrás en el backfill histórico.
  - **Riesgo:** Muy bajo usando `CREATE INDEX CONCURRENTLY` en una migración con `autocommit_block`. (Respetando las reglas del pedido, **no se creó ni aplicó ninguna migración**.)

---

## 3. Qué NO es el problema (medido y descartado)

Para no perder tiempo volviendo a mirar pistas que están sanas:

1. **Memoria RAM, swap o disco del VPS:** `free -h` mostró **11,7 GiB totales, 5,0 GiB usados y 6,7 GiB disponibles**, `0 B` de swap y `0,0–1,7 %` de espera de I/O (`wa` en `vmstat`). Los OOM de `alostudio-embeddings` que quedaron viejos en `journalctl` son del `15/11` (antes de limitar `batch_size=4` y `MemoryMax=3072M`); lleva 11 días seguidos estable en `1,74 GiB`.
2. **Que el backend llame a `alostudio-embeddings` en cada pedido o que les robe CPU a los demás cuando está quieto:** verificado en código y en `top -b -d 1`. El backend solo lo consulta al buscar mensajes/artículos o en comentarios de Instagram; fuera del cron fallido cada 3 minutos, su consumo real es **0–1 % de CPU**, y además corre con `Nice=10` y `CPUWeight=20` (`ops/embeddings/alostudio-embeddings.service`), por lo que cede CPU al instante ante `alostudio-backend` o Postgres.
3. **Los otros proyectos en Docker (`sfoffice`, `supabase`, `citricola`):** medidos con `docker stats --no-stream` y `ps`. Entre todos sumaban ~20–25 % de **un** núcleo (`supabase-studio` 13,8 %, `sfoffice-redis` 5,1 %, el resto <2 %) en una máquina de 6 núcleos (**600 %** de capacidad total). El servidor tenía **85–90 % de CPU libre**.
4. **El sondeo (`polling`) de llamadas activas (`useActiveCalls`) y notificaciones (`NotificationBell`):** `useActiveCalls` sondea cada **15 s** (solo baja a 1 s mientras el propio agente está discando una llamada saliente, `frontend/lib/api/calls.ts:74,105`), `useUnreadCount` cada **60 s**, `refetchOnWindowFocus` está desactivado en `QueryClient` (`frontend/lib/query.ts:30`) y TanStack Query frena los intervalos cuando la pestaña pasa a segundo plano. En la base, `GET /calls/active` sin llamadas activas ejecuta **2 consultas** livianas y `GET /notifications/unread_count` ejecuta **1 `COUNT`** sobre el índice `ix_notifications_performance`.
5. **El proxy BFF de Next.js (`/api/backend/[...path]`) y el WebSocket `/cable`:** medidos desde dentro del VPS (`127.0.0.1:3000` vs. `127.0.0.1:8000`), el paso por el route handler BFF suma apenas **~20–25 ms**. Y Tailscale Serve enruta `/cable` directo a `127.0.0.1:8000/cable`, respondiendo `welcome` en ~11 ms una vez abierto el túnel TLS.
6. **Los listeners en línea al resolver (webhooks, WhatsApp Business Agent, CSAT):** `fan_out_to_whatsapp` (`release_to_ai_task`), `fan_out_to_webhooks` y `fan_out_to_agent_bots` (`deliver_webhook_task`) **ya delegan la llamada HTTP externa a ARQ**; no bloquean `toggle_status` esperando a Meta ni a servidores externos.

---

## 4. Qué no se pudo medir sin sesión y comandos para repetir

### Qué queda para medir con sesión iniciada (si el dueño quiere)
Por regla del pedido no iniciamos sesión en el panel. Si después de desplegar estos arreglos querés medir la fluidez visual real en tu navegador:
1. Abrí DevTools → pestaña **Performance**, grabá 5 segundos mientras hacés clic entre 3 conversaciones largas y tocás **«Resolver»**, y mirá `INP` (Interaction to Next Paint) y si hay frames largos de `Recalculate Style / Paint` por el `backdrop-filter`.
2. En la pestaña **Network** (filtrando `Fetch/XHR`), verificá que al tocar «Resolver» el botón cambie en el acto y el `POST .../toggle_status` baje de >1,5 s a ~350–450 ms (los ~250 ms de red a Europa + ~80–100 ms de servidor).

### Comandos usados para repetir las mediciones

#### A. Latencia de red Tailscale, HTTPS (frío vs. keep-alive) y WebSocket `/cable` (desde Windows)
```powershell
tailscale ping -c 5 vmi3426238

# 6 pedidos en frío (nueva conexión TCP+TLS cada vez)
1..6 | ForEach-Object {
  curl.exe -s -o NUL -w "run $_`: dns=%{time_namelookup}s tcp=%{time_connect}s tls=%{time_appconnect}s ttfb=%{time_starttransfer}s total=%{time_total}s code=%{http_code}`n" https://vmi3426238.tail34088e.ts.net/login
}

# Reutilizando conexión keep-alive hacia el BFF
curl.exe -s -o NUL `
  -w "req1: tcp=%{time_connect}s tls=%{time_appconnect}s ttfb=%{time_starttransfer}s total=%{time_total}s`n" https://vmi3426238.tail34088e.ts.net/api/backend/health `
  -w "req2: tcp=%{time_connect}s tls=%{time_appconnect}s ttfb=%{time_starttransfer}s total=%{time_total}s`n" https://vmi3426238.tail34088e.ts.net/api/backend/health
```

#### B. Estado de CPU en vivo, memoria, Docker y tiempos en `worker.log` (solo lectura en el VPS)
```bash
ssh -o BatchMode=yes zeek@vmi3426238 '
  uptime && free -h && vmstat 1 3
  docker stats --no-stream
  # CPU instantáneo real (no el promedio histórico de ps) de backend, worker y embeddings:
  top -b -n 3 -d 1 -p $(pgrep -d, -f "app\.(main|workers|embeddings_service)")
'
```

```bash
# Estadística de duración por tarea en ~/logs/worker.log
ssh -o BatchMode=yes zeek@vmi3426238 'python3 -c "
import re, collections
from pathlib import Path
durations = collections.defaultdict(list)
for line in Path(\"/home/zeek/logs/worker.log\").read_text(errors=\"replace\").splitlines():
    m = re.search(r\"(\d+\.\d+)s ← (?:[0-9a-f]{32}:)?([a-zA-Z0-9_:]+)\", line)
    if m: durations[m.group(2)].append(float(m.group(1)))
for task, vals in sorted(durations.items(), key=lambda kv: -sum(kv[1]))[:10]:
    s = sorted(vals)
    print(f\"{task:36s} count={len(vals):6d} total={sum(vals):8.1f}s p50={s[len(s)//2]:6.2f}s p95={s[int(len(s)*0.95)]:6.2f}s\")
"'
```

#### C. Escaneos secuenciales, mensajes sin vector y `EXPLAIN ANALYZE` en PostgreSQL (solo lectura)
```bash
ssh -o BatchMode=yes zeek@vmi3426238 '
  docker exec alostudio-postgres psql -U alostudio -d alostudio -P pager=off -c "
    SELECT relname, n_live_tup, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch
    FROM pg_stat_user_tables
    ORDER BY seq_tup_read DESC NULLS LAST LIMIT 15;

    SELECT count(*) AS elegibles_pendientes, max(length(m.content)) AS max_chars
    FROM messages m
    LEFT JOIN message_embeddings me ON me.message_id = m.id
    WHERE me.message_id IS NULL AND m.message_type IN (0, 1) AND length(trim(m.content)) >= 12;

    EXPLAIN (ANALYZE, BUFFERS)
    SELECT id FROM conversations WHERE account_id = 1 AND status = 0 ORDER BY last_activity_at DESC LIMIT 25;
  "
'
```

#### D. Conteo de consultas SQL por operación y verificación de tests (en este worktree)
```powershell
uv run pytest tests/integration/test_conversation_list_queries.py -s
cd frontend
npx vitest run lib/realtime/cable.test.ts components/conversations/conversation-view.test.tsx
```
