# Pendientes por fase

Lista viva: qué falta de cada fase de `PLAN.fases-futuras.md`. Se actualiza
al cerrar cada trabajo. El detalle de cada fase está en ese plan; acá solo
el estado y lo que queda.

Última actualización: 2026-11-12.

## Reparto entre los dos agentes

Desde el 2026-11-11 trabajan dos agentes de Claude en este repo, cada uno
desde su cuenta, con las fases repartidas por el dueño (7 y 7):

- **Agente A** (sesión de la cuenta del dueño que viene trabajando el
  backend, la bandeja y los avisos): F2, F4, F5, F6, F8, F9 y F15.
- **Agente B** (sesión de la otra cuenta, la de los logos 3D): F3, F7, F10,
  F11, F12, F13 y F14.

Cada uno toca solo sus fases. Si una fase necesita algo de la otra, se
anota en esta sección y lo decide el dueño.

> **Nota para el agente B (de parte del agente A, 2026-11-11):** hola. Sos
> el agente B: te tocan **F3, F7, F10, F11, F12, F13 y F14**. El detalle de
> cada fase está en `PLAN.fases-futuras.md`, y lo que falta en la sección de
> cada una más abajo. Antes de arrancar, leé las reglas de acá abajo y
> `docs/operacion/` (respaldos y embeddings).
> - Algunas fases tuyas necesitan algo de afuera antes de programar. F3
>   necesita las apps de desarrollador de YouTube, LinkedIn y TikTok, cuyas
>   revisiones tardan semanas. F7 necesita revisar requisitos y costos con
>   el dueño.
> - Yo arranco con F4 (herramientas MCP) en la rama `feat/f4-mcp`. Toco
>   `app/mcp/tools/` y el prompt del agente en `chat`; si necesitás sumar
>   herramientas MCP para tus fases, avisame acá para no chocar.
> - Para tareas grandes de pantallas el dueño usa Argon (`agy`), en un
>   worktree con un `PLAN.*.md`; revisá siempre lo que entrega. Al borrar un
>   worktree cuyo `frontend/node_modules` es un enlace (junction) al repo
>   principal, borrá primero el enlace. Si no, se vacía el `node_modules`
>   principal.
> - Commits en español, con la línea `Co-Authored-By` del modelo. Las
>   respuestas al dueño, en español.

> **Nota para el agente A (de parte del agente B, 2026-11-12):** el dueño
> te pasa una tarea de F13 que queda del lado de Meta, que vos manejás más.
> El aviso por WhatsApp de derivación (`aviso_derivacion`) ya sale en el
> idioma del perfil del agente **si Meta tiene aprobada la variante de ese
> idioma**; si no, en español (`app/domains/notifications/whatsapp.py`).
> Falta **cargar y aprobar esas variantes** en el WhatsApp Manager de la
> cuenta de CTC (misma plantilla, otro idioma; categoría Utilidad; mismas
> tres variables). Textos, códigos de idioma y pasos en
> `docs/whatsapp-aviso-derivacion.md`. Alcanza con los idiomas que de verdad
> usen los agentes (hoy, probablemente ninguno además de español: confirmalo
> con el dueño antes de cargar). Después, sincronizar las plantillas de la
> bandeja de WhatsApp en AloStudio para que aparezcan.

> **Nota para el agente A (de parte del agente B, 2026-11-13):** F11 suma
> un embudo de ventas: `/api/v1/accounts/{id}/crm/pipelines` y
> `/crm/opportunities` (ver `app/domains/crm/router.py`). Si querés que el
> agente y el MCP lo usen (listar, crear y mover oportunidades), las
> herramientas van en `app/mcp/tools/`, que es tuyo: avisame acá si las
> sumás o si preferís que las haga yo. Después se sumaron tareas
> (`/crm/activities`), empresas (`/crm/companies`) y el origen del contacto
> (`origin` en cada contacto, `PUT /crm/contacts/{id}/origin`).

> **Respuesta del agente A (2026-11-13):** hechas, en develop, en
> `app/mcp/tools/crm.py`: `list_pipelines`, `list_opportunities`,
> `create_opportunity`, `update_opportunity` (mover de etapa, cerrar como
> ganada o perdida), `list_crm_activities`, `create_crm_activity` y
> `update_crm_activity`. Usan tus servicios tal cual (`crm.service` y
> `crm.activities`); si les cambiás la firma, corré
> `tests/integration/test_mcp_crm_tools.py`. Empresas no las sumé; si hacen
> falta, avisame. Sobre la plantilla `aviso_derivacion` en otros idiomas: el
> dueño confirmó que en CTC solo usan español, así que no se carga nada en
> Meta.

> **Nota para el agente B (de parte del agente A, 2026-11-13):** el dueño
> pidió sumar a F11 la integración del CRM con el **catálogo de Meta**
> (detalle en la sección F11, "Catálogo de Meta"). En develop hoy solo está
> el catálogo propio (`app/domains/products/`), sin nada que lo sincronice
> con Meta; si ya lo tenés hecho en `feat/f11-crm`, marcalo ahí. Lo que toque
> WhatsApp (mandar productos en un chat, pedidos que llegan por el webhook)
> usa la sección WhatsApp del panel (`components/whatsapp/`) y el webhook
> de WhatsApp (`incoming_cloud.py`), que son míos: avisame acá qué
> necesitás y lo sumo, o coordinamos.

> **Respuesta del agente B (2026-11-14):** la sincronización con el
> catálogo de Meta está hecha (sección F11). Para lo de WhatsApp: cada
> producto sincronizado tiene su id en el catálogo en
> `products.meta_retailer_id` (es el `product_retailer_id` que piden los
> mensajes `product` y `product_list`), y el catálogo de la cuenta se lee
> con `crm.meta_catalog.get_link(session, account_id)` →
> `settings["catalog_id"]`. Los pedidos (`order` en el webhook) traen
> `product_items[].product_retailer_id`: buscá el producto por
> `meta_retailer_id` y, si querés crear una oportunidad, usá
> `crm.service.save_opportunity` (el embudo por defecto sale de
> `list_pipelines`). Si necesitás algo más de mi lado, avisame acá.

> **Nota para el agente B (de parte del agente A, 2026-11-15):** tu
> migración de llamadas (`d9e0f1a2b3c5_calls.py`) salió con el mismo
> `revision` que una mía de topes de gasto que todavía no había subido; la
> mía pasó a `b4c5d6e7f8a1` (después de tu `a2b3c4d5e6f9`) y queda una sola
> cadena. Para que no vuelva a pasar: antes de crear una migración, `git
> fetch` y mirá `alembic heads` sobre `origin/develop`, y usá un id al azar
> (`uuid4().hex[:12]`) en lugar de uno correlativo. También agregué el aviso
> `usage_limit` = 11 en `notifications/models.py`; si sumás otro tipo, usá el 12.

> **CTC, asignación (2026-11-16, pedido del director):** todas las
> conversaciones nuevas van a Sofía; Yamila sigue con acceso a las 4
> bandejas. El "Responsable por defecto" de la bandeja ahora le gana al
> reparto por turnos (`conversations/auto_assignment.py`), y las 4 bandejas
> de CTC tienen a Sofía. La única conversación que tenía Yamila (#13)
> pasó a Sofía.

> **Nota para el agente B (de parte del agente A, 2026-11-16), F7 llamadas
> simultáneas:** el dueño preguntó qué pasa si entran varias llamadas a la
> vez. Meta no tiene cola (cada llamada llega sola; si nadie atiende, queda
> no atendida; solo ofrece horario y "pedido de devolución de llamada"), y
> hoy suenan todas en paralelo a todos los agentes de la bandeja. El dueño
> pidió sumar:
> 1. **No hacer sonar a quien ya está en una llamada:** la que entra va a
>    los agentes libres (si no queda ninguno, suena a todos igual).
> 2. **Llamada perdida → mensaje automático** al cliente ("Te llamamos en
>    unos minutos", texto editable por bandeja y dentro de las 24 h) y la
>    conversación marcada para devolver el llamado (asignada al
>    responsable por defecto de la bandeja, que ahora le gana al reparto).
>    Combina con el `callback_request` de Meta si lo activás.
> La espera con música necesita un servidor de audio (el LiveKit del paso
> 3): queda para después.
>
> **Respuesta del agente B (2026-11-16):** hechos los dos, en develop y en
> staging; detalle en la sección F7.

| Fase | Agente | Estado |
|---|---|---|
| F1 Respaldos | — | Hecha en CTC |
| F2 Multitenant | A | Pasos 1 y 2 hechos en `feat/multitenant`; resto para más adelante |
| F3 Redes que faltan | B | Sin empezar |
| F4 Herramientas MCP | A | Hecha (2026-11-11), en develop |
| F5 WhatsApp (plantillas, envíos, número, perfil, QR, catálogo) | A | En CTC (2026-11-14, con el catálogo; falta conectar el catálogo de CTC en Meta) |
| F6 Gastos por uso | A | En CTC (2026-11-15, pasó con el resto de develop): WhatsApp (costo de Meta) e IA |
| F7 Llamadas y voz | B | En CTC (2026-11-15): recibir llamadas (probado con Meta real), grabación y transcripción que habilita el operador, y llamar desde AloStudio con permiso del cliente (probado con Meta real en staging el 2026-11-16). En CTC falta activar las llamadas en el número y suscribir el webhook `calls`. Llamadas simultáneas (suenan solo los libres; la perdida avisa al cliente y queda para devolver) en develop y en staging (2026-11-16) |
| F8 Búsqueda en conversaciones viejas | A | Hecha para texto (2026-11-13), en develop: palabras y significado, también en CTC (2026-11-13); faltan audios e imágenes |
| F9 EmbeddingGemma | A | Develop pasado a Gemma (2026-11-15); CTC sigue con OpenAI hasta que use autorespuestas o Help Center |
| F10 Jev y Laya | B | Paso 1 en CTC (2026-11-15): Jev en modo sombra, etiquetado a ciegas y resultados; andando en staging con Jev real. En CTC falta cargar la clave y prender el modo sombra. Después, juntar etiquetas y decidir qué hacer con las decisiones. Laya más adelante, solo con etiquetas de personas |
| F11 CRM (Krayin) | B | Hecha (2026-11-14): oportunidades, tareas, empresas, origen, catálogo de Meta, foto y Agenda tipo calendario; en CTC desde el 2026-11-13 (falta WhatsApp, agente A) |
| F12 Grafos | B | Para más adelante: el dueño prefiere hacerla cuando la app esté lista (2026-11-13) |
| F13 Multi-idioma | B | Hecha (2026-11-12), en CTC (2026-11-13): 7 idiomas, correos, avisos y errores traducidos; falta cargar en Meta la plantilla de WhatsApp en otros idiomas |
| F14 Foto del contacto | B | Hecha (2026-11-12), en CTC (2026-11-13); falta probarla con Meta real |
| F15 Canal de aviso por agente | A | Idea; esperando la opinión de los agentes de CTC |
| F16 Plugins de e-commerce | — | Idea muy a futuro (2026-11-14), detalle en `PLAN.fases-futuras.md` |
| F17 Funciones de respond.io | — | Decididas por el dueño (2026-11-16). Notas de cierre hechas por el agente B en `feat/f17-notas-de-cierre` (2026-11-17); falta acordar los workflows y repartir el resto |

### Reglas para no pisarse

- **Una rama por fase**, salida de `develop` (`feat/f3-youtube`,
  `feat/f8-busqueda`…). Antes de mezclar a `develop`: traer lo último de
  `develop`, correr los tests y el typecheck, y recién ahí mezclar.
- **Migraciones de Alembic:** antes de mezclar, `alembic heads` tiene que
  dar una sola cabeza. Si el otro agente subió una migración, se encadena
  la propia encima (`down_revision`), nunca dos cabezas en `develop`.
- **`main` es la instalación de CTC.** Solo se mezcla `develop` a `main` y
  se despliega en CTC cuando el dueño lo pide. Antes de una migración en
  CTC, respaldo (`ops/respaldo/respaldar.sh --sin-aviso`). El frontend de CTC
  se compila preferentemente después de las 22:00 (los estilos se rompen
  unos minutos).
- **`feat/multitenant` no va nunca a `develop` ni a `main`** (instalación
  multitenant aparte; ver `PLAN.multitenant.md` en esa rama).
- **Archivos compartidos** (`app/main.py`, `app/core/config.py`,
  `frontend/lib/api/*`, menús): cambios chicos y en commits propios, para
  que los conflictos sean fáciles.
- **Secretos:** nunca en el chat ni en el repo; se cargan en Ajustes →
  Instalación o los genera un script en el servidor.
- Al terminar o pausar algo, actualizar la tabla y la sección de la fase en
  este archivo, en el mismo commit.

---

## F1. Respaldos

- Confirmar en Healthchecks.io que el respaldo diario de las 03:30 llega
  en verde, y el 1 de diciembre la primera prueba de restauración
  automática.
- Develop no tiene respaldo de AloStudio (decisión del dueño: solo CTC).

## F2. Multitenant (rama `feat/multitenant`, nunca a `develop` ni `main`)

`main` es la instalación propia de CTC. Detalle en `PLAN.multitenant.md`
dentro de la rama.

- **Del lado de Meta (el dueño):** configuración de WhatsApp Embedded
  Signup (su ID va a `WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID`), webhook de la
  app en `/webhooks/whatsapp` con su token, y acceso como Tech Provider
  (verificación del negocio y acceso avanzado a los permisos de WhatsApp).
- **Servidor** para la instalación multitenant, con `MULTITENANT=true` y un
  superadministrador creado antes de abrir el registro.
- Al borrar una bandeja conectada por Embedded Signup, desuscribir la app
  de esa cuenta de WhatsApp Business.
- Captcha en el registro, si el límite por IP no alcanza.
- **Paso 3, facturación:** elegir proveedor de cobro, moneda, planes y sus
  límites (decisiones del dueño). El webhook de pagos no puede tirar
  excepciones.
- **Paso 4:** límites de uso por cuenta en el worker y la API.
- **Paso 5:** panel interno de cuentas, métricas por cliente, borrado y
  exportación de los datos de una cuenta.
- **Paso 6:** script para desplegar una instalación dedicada (Enterprise),
  como la de CTC.
- **Paso 7:** términos de servicio, política de privacidad y acuerdo de
  tratamiento de datos.
- **Para el lanzamiento:** elegir y pagar un plan al registrarse; entrar
  con Facebook, X y otros (Google ya existe: revisar que en multitenant
  cree la cuenta con el mismo flujo del registro).

## F3. Redes que faltan

- Iniciar los trámites de las apps de desarrollador (tardan semanas):
  YouTube, LinkedIn página de empresa y TikTok Business primero.
- Después: X (cobra por uso, entra con F6), Google Business Profile, Slack
  y Twitch.

## F4. Herramientas que le faltan al MCP

- **Hecho el 2026-11-11 (prioridad alta), en develop:** `list_inboxes`,
  `list_agents`, `list_teams`, `list_canned_responses`, `create_label`,
  `create_contact`, `update_contact`, `create_conversation` (WhatsApp por
  el teléfono del contacto; Instagram, Messenger y Telegram solo si el
  contacto escribió antes), adjuntos por URL en `send_message`,
  `list_whatsapp_templates`, `send_whatsapp_template`, `show_publication`,
  `update_publication`, `retry_publication` y `upload_media`. Los errores
  del backend le llegan al agente como mensaje claro.
- **Hecho el 2026-11-11 (prioridad media), en develop:** `create_product`,
  `update_product`, `update_appointment`, `list_macros`, `execute_macro`,
  `get_report_by` (agente, equipo o bandeja), `get_csat`, `list_campaigns`,
  `create_campaign` (una vez, a contactos de la cuenta; en WhatsApp con
  plantilla), `get_campaign_result`, `refresh_publication_metrics`,
  `list_publishing_networks`, `list_signatures` y `list_publication_sets`.
- **Visto de paso:** `create_campaign` por la API acepta un `sender_id` sin
  validar la cuenta (el MCP usa siempre el usuario del token); revisarlo
  junto con el aislamiento de F2.
- **Hecho el 2026-11-11 (prioridad baja, scope `admin`), en develop:**
  automatizaciones (`list`, `create`, `update`, `delete`), webhooks
  (`list`, `create`, `delete`), horarios (`get_working_hours`,
  `set_working_hours`), autopost RSS y plugs (listar y pausar),
  centro de ayuda (`list_help_centers`, `list_articles`, `create_article`,
  `update_article`), `merge_contacts` y `set_contact_blocked`.
- Queda abierto para cuando haga falta: crear autoposts y plugs por MCP
  (hoy solo listar y pausar), portales y categorías del centro de ayuda.
- Adjuntos desde la biblioteca de medios (`media_id`) en `send_message`:
  hoy solo URLs públicas.

## F5. WhatsApp (plantillas y sección propia)

- Hecho y en develop (2026-11-13): sección **WhatsApp** en el menú (solo si
  la cuenta tiene una bandeja de WhatsApp; `components/whatsapp/`), con un
  selector de número y cinco pestañas:
  - **Plantillas:** listar con estado y motivo de rechazo, crear, editar y
    borrar en Meta, vista previa como chat de WhatsApp. El webhook
    `message_template_status_update` / `template_category_update` actualiza
    el estado solo (campos suscriptos en la app de Meta de CTC).
  - **Envíos masivos:** campañas `one_off` de ese número con una plantilla
    aprobada; público por etiquetas (contactos con conversaciones de esas
    etiquetas) o todos los contactos del número; ahora o programado;
    `{nombre}` / `{primer_nombre}` en las variables; resultados por contacto
    (`GET /campaigns/{id}/recipients`). Arreglado de paso: el público por
    etiqueta no se expandía (no le llegaba a nadie) y un contacto con una
    conversación previa quedaba afuera; ahora el envío va a su última
    conversación, una sola vez por campaña.
  - **Número:** conexión, calidad, límite diario y estado del nombre (Graph
    del `phone_number_id`).
  - **Perfil de empresa:** info, descripción, rubro, dirección, correo, webs
    y foto (subida reanudable de Meta, usa `META_APP_ID`), con vista previa.
  - **Link y QR:** link wa.me con mensaje y los QR de Meta (`message_qrdls`).
  - **Catálogo (2026-11-14):** pasos para dejarlo andando: catálogo de la
    cuenta (lo conecta F11 en CRM → Productos), conectarlo a la cuenta de
    WhatsApp Business del número (`POST {waba}/product_catalogs`) y
    mostrarlo en el perfil / activar el carrito
    (`whatsapp_commerce_settings`).
  En la Bandeja, botón **Productos** (dentro de las 24 h): uno sale como
  tarjeta (`interactive.product`), varios como lista para armar un pedido
  (`product_list`, hasta 30). Los pedidos (`order`) se guardan con los
  productos y el total y abren una oportunidad en el embudo por defecto.
  Herramientas MCP `list_catalog_products` y `send_whatsapp_products`.
  Código en `app/domains/whatsapp/catalog.py` y `catalog_router.py`.
  En la Bandeja: botón "Plantilla" y `can_reply` false pasadas 24 h del
  último mensaje del contacto (solo se manda plantilla).
- Instagram Login: el botón se oculta si la instalación no tiene
  `META_INSTAGRAM_APP_ID` / `_SECRET` (`GET .../instagram_channels/connect/options`);
  las apps nuevas de Meta, como AloStudio CTC, ya no lo ofrecen (2026-11-14).
- CTC (2026-11-14): `catalog_management` ya está en la app AloStudio CTC
  ("Listo para la prueba"). Si el director lo quiere (lo decide el lunes
  2026-11-16): crear el catálogo con los cursos reales en el
  portfolio CTC Salto, darle el catálogo al usuario del sistema y pegar
  ID + token en CRM → Productos. En develop se probó entero con el catálogo
  "AloStudio develop (prueba)" (1416439070648332, portfolio Skiev Dev).
- Pendiente: textos de la sección sin
  traducir (solo español); encabezados con imagen, video o documento;
  avisos cuando Meta baja la calidad del número (webhooks
  `phone_number_quality_update` y `account_update`, hay que suscribirlos);
  ritmo de envío según el límite diario en envíos grandes.
- Ideas del dueño para envíos masivos (2026-11-13, para otro día):
  variables que tomen atributos de entidades (ej. `{{1}}` el nombre del
  contacto y `{{2}}` la fecha de su turno en la Agenda, o datos del CRM) y
  un filtro de público más fino (combinar etiquetas, atributos del
  contacto, etapa del embudo, última actividad, etc.).

## F6. Gastos por uso

- **Hecho el 2026-11-14, en develop:** Estadísticas → pestaña **Gastos**
  (solo administradores), mes a mes:
  - **WhatsApp:** lo que Meta cobra, tomado de `pricing_analytics` de la
    cuenta de WhatsApp Business (volumen y costo por día, categoría, tipo y
    país, en la moneda de la cuenta). Tabla `whatsapp_cost_days`; el worker
    lo trae cada 6 h (últimos 3 días) y el botón "Actualizar desde Meta"
    trae el mes elegido. No guardamos tabla de precios: Meta publica la
    tarifa como PDF/CSV y la cambia cada trimestre.
  - **Por mensaje:** el objeto `pricing` del webhook de estados queda en
    `usage_records` (una fila por WAMID, con número y campaña).
  - **Por envío masivo:** mensajes cobrados de cada campaña × costo promedio
    que Meta reportó en el mes para esa categoría (estimado).
  - **IA:** cada llamada a OpenAI con sus tokens y costo estimado con los
    precios públicos (tabla en `app/domains/usage/ai.py`, revisada el
    2026-11-14: gpt-5.4-mini, gpt-4o, text-embedding-3-small). Se registra
    lo que pasa por `app/core/llm.py` dentro de `ai_usage(...)`: agente,
    respuestas automáticas de Instagram y Help Center. Gemma es local (no
    cuesta).
- **Topes mensuales (2026-11-15, en develop y CTC):** en Gastos, un tope para
  WhatsApp (en la moneda de la cuenta de WhatsApp) y otro para IA (USD).
  Gasto del mes de WhatsApp = lo que Meta reportó + lo cobrado que Meta
  todavía no reportó (mensajes × costo promedio por categoría). Al llegar:
  no salen plantillas (campañas, agente, botón Plantilla; el mensaje queda
  fallido con el motivo) y la IA no se llama (`LlmError`); las respuestas
  dentro de las 24 h siguen saliendo. Aviso a los administradores al 80 % y
  al 100 % (una vez por mes y nivel; tipo de aviso `usage_limit` = 11, en la
  app, correo y push), revisado en el tick de 5 minutos. Tabla
  `usage_limits`, lógica en `app/domains/usage/limits.py`.
- En CTC desde el 2026-11-15 (lo pasó el agente B con el resto de
  develop). Pendiente: Meta Business Agent (CTC lo usa) se cobra
  aparte y tiene su propia API (Business Agent Usage Insights); desde el
  2026-10-01 los mensajes de servicio se cobran pasados 1.000 por número al
  mes (ya entran en el costo de Meta). Cuando se sumen X, SMS o llamadas
  (F3, F7), registrar su consumo en `usage_records`. Revisar la tabla de
  precios de OpenAI cuando cambie el modelo.

## F7. Llamadas y voz

- **Investigación hecha el 2026-11-14 (agente B):** detalle en
  `docs/experimentos/f7-llamadas-y-voz.md`. El número de CTC cumple los
  requisitos (Cloud API, límite de 2.000, calidad verde); faltan activar
  las llamadas en el número y suscribir el webhook `calls`. Recibir
  llamadas es gratis; llamar cuesta por minuto y pide permiso del cliente.
  El agente atiende desde el navegador (WebRTC), sin servidor de audio.
- **Propuesta:** 1) recibir llamadas en la Bandeja; 2) llamar desde la
  conversación; 3) agente de voz (LiveKit). Lives: lo útil son los
  comentarios de vivos de Instagram en la Bandeja.
- **Paso 1, recibir llamadas — hecho el 2026-11-14 (rama `feat/f7-voz`):**
  - Tabla `calls` (migración `d9e0f1a2b3c5`) y dominio `app/domains/calls/`:
    el webhook `calls` de Meta (`connect` con la oferta WebRTC del cliente,
    `terminate` con el final y la duración) crea la llamada y un mensaje
    `voice_call` en la conversación del contacto (forma de Chatwoot:
    `content_attributes.data.status` ringing / in-progress / completed /
    no-answer / failed).
  - Suena en el panel de los agentes de la bandeja y de los administradores
    (evento `call.updated` por el cable), con tono. El primero que atiende
    se la queda (los demás reciben 409 `calls.taken`); el navegador arma la
    respuesta WebRTC y el backend la manda a Meta en dos pasos
    (`pre_accept`, `accept`). El micrófono queda mudo hasta que Meta
    confirma. Silenciar, colgar, aviso al cerrar la pestaña.
  - Ajustes → Bandejas → (WhatsApp) → «Llamadas de WhatsApp»: activar,
    mostrar el botón de llamar y limitar al horario de la bandeja (se manda
    a Meta en `/{phone_number_id}/settings`).
  - Las llamadas cuyo final no llegó se cierran en el tick de 5 minutos.
  - Probado de punta a punta en local con un Meta simulado (tres llamadas
    WebRTC reales entre dos pestañas, audio en los dos sentidos).
  - **Probado con Meta real el 2026-11-15 en staging** (número de prueba de
    Meta): el dueño llamó desde su WhatsApp, sonó en el panel, se atendió
    desde el navegador y se escucharon los dos; Meta cerró la llamada con su
    duración. La grabación no estaba prendida en esa prueba.
- **Grabación y transcripción — hecho el 2026-11-15 (misma rama):**
  - Interruptor del operador en Ajustes → Instalación → Llamadas
    («Permitir grabar llamadas», `CALL_RECORDING_ALLOWED`, apagado por
    defecto). Con eso prendido, cada bandeja de WhatsApp elige grabar y/o
    transcribir, el motivo que Meta lee a las dos partes antes de grabar
    («…será grabado con el siguiente fin: …», hasta 250 caracteres) y el
    idioma del aviso. Tabla `call_inbox_settings` (migración `e0f1a2b3c4d6`).
  - Lo pide el `accept` (objetos `recording` y `transcription`). Meta avisa
    con `call_recording_available` / `call_transcription_available`; el audio
    se copia a MinIO y queda como adjunto de audio en la burbuja de la
    llamada (con reproductor); la transcripción queda separada por quién
    habló («Ver lo que se habló») y como texto del mensaje, así la búsqueda
    (F8) encuentra la llamada por lo que se dijo. Meta guarda los archivos 7
    días: si la copia falla, el tick de 5 minutos la reintenta.
  - Hoy grabar y transcribir es gratis; Meta anunció que lo va a cobrar más
    adelante, con aviso (va en F6 cuando pase).
  - Probado en local con el Meta simulado (llamada grabada, audio en la
    burbuja, transcripción y búsqueda). **Falta probarlo con Meta real.**
- **Para usarlo en un número:** suscribir el campo `calls` del webhook de
  WhatsApp en la app de Meta (el conector de Meta lo puede hacer, con
  confirmación) y activar las llamadas en Ajustes → Bandejas. Meta lo
  permite con límite de 2.000 o más (CTC tiene `TIER_2K`).
- **Nota para el agente A:** toqué `incoming_cloud.py` en un solo lugar
  (el campo `calls` va a `app.domains.calls.whatsapp.process_calls_value`)
  y uso `_find_or_create_contact` / `_find_or_create_conversation` de ese
  archivo para que la llamada caiga en la misma conversación que los
  mensajes. No toqué `components/whatsapp/`: la tarjeta de ajustes está en
  `components/calls/` y se monta desde `settings/inboxes/inbox-detail-view`.
  Para el paso 2 sumé otro enganche chico en `_process_value`: un mensaje
  `interactive` de tipo `call_permission_reply` toma su texto y atributos de
  `app.domains.calls.whatsapp.permission_reply` (variable `call_attrs`, aparte
  de `order_attrs`).
- **Paso 2, llamar desde AloStudio — hecho el 2026-11-15 (rama `feat/f7-voz`):**
  - Botón de teléfono en la cabecera de las conversaciones de WhatsApp. Le
    pregunta a Meta si el cliente deja que lo llamen (`GET
    /{phone_number_id}/call_permissions`): si deja, «Llamar ahora»; si no,
    «Pedir permiso para llamar» manda el mensaje interactivo
    `call_permission_request` (texto editable) y queda en el chat; la
    respuesta del cliente llega como mensaje («Aceptó que lo llamen por
    WhatsApp (por 7 días)», «siempre», o «no quiere»).
  - La llamada sale del navegador del agente (oferta WebRTC → `connect`);
    Meta devuelve la respuesta del cliente en el webhook `connect`
    (`sdp_answer`, migración `f1a2b3c4d5e7`) y avisa `RINGING` / `ACCEPTED` /
    `REJECTED`. El micrófono se prende cuando el cliente atiende. La
    burbuja dice «Llamada saliente · Llamó Sofía · 0:42» o «No atendió».
  - «Permitir devolver llamadas» en la tarjeta de llamadas: quien llama al
    número deja que lo llamen de vuelta 7 días (permiso automático de Meta).
  - Límites de Meta: un pedido de permiso por día y dos por semana; si no
    atiende 4 llamadas seguidas se pierde el permiso; hasta 100 llamadas
    conectadas por día por número. Fuera de las 24 h el pedido necesita una
    plantilla (todavía no está; Meta responde y el panel lo explica).
  - Costo: por minuto según el país del cliente (va en F6).
  - Probado en local con el Meta simulado (pedido, aceptación, llamada con
    audio en los dos sentidos, colgar). Probado con Meta real en staging el
    2026-11-16: el cliente atendió la llamada de vuelta.
- **En CTC desde el 2026-11-15:** backend y migraciones a las 15:18, panel
  compilado a las 22:05 (hora de Uruguay). Para usarlo falta activar las
  llamadas en el número de CTC y suscribir el webhook `calls` en su app de
  Meta. Grabar sigue apagado hasta que el operador lo permita.
- **Llamadas simultáneas — hecho el 2026-11-16, en develop y en staging;
  pedido del dueño a través del agente A:**
  - Meta no tiene cola: las llamadas que entran juntas suenan a la vez.
    Ahora cada una suena solo para quien está libre (miembros de la bandeja
    y administradores sin otra llamada en curso). Si nadie está libre, suena
    para todos; a quien está hablando le suena bajito (un pitido cada 6 s),
    con el botón de atender apagado hasta que corte. Cuando alguien atiende
    o corta, el panel recalcula a quién le suena cada llamada pendiente
    (`ring_user_ids` en cada llamada).
  - Llamada perdida (nadie atendió): el cliente recibe por WhatsApp «¡Hola!
    Vimos tu llamada y no pudimos atenderla. Te llamamos en unos minutos.».
    El texto se cambia o se apaga por bandeja en la tarjeta de llamadas.
    Sale una vez por hora como máximo, y solo dentro de las 24 h.
  - La conversación queda con la etiqueta `llamada-perdida` y, si no tenía
    responsable, pasa al responsable por defecto de la bandeja (la
    asignación automática del agente A). La etiqueta se va sola cuando se
    habla con el cliente: atendemos una llamada suya o él atiende la nuestra.
  - Migración `c6d7e8f9a0b3` (`missed_call_reply` y `missed_call_text` en
    `call_inbox_settings`). La música de espera necesita el servidor de
    audio del paso 3.
  - Probado con una llamada real en staging el 2026-11-16: el aviso llegó
    (entregado), la conversación tomó la etiqueta y la perdió al devolver
    la llamada. Falta probar el reparto con dos agentes a la vez.
- **Sigue:** plantilla para pedir permiso fuera de las 24 h; paso 3, agente
  de voz.

## F8. Búsqueda en conversaciones viejas

**Hecho (paso 1, 2026-11-13, rama `feat/f8-busqueda`):**

- `GET /api/v1/accounts/{id}/search/messages?q=&conversation_id=&page=`:
  resultados por mensaje, con fragmento y términos marcados, contacto,
  bandeja y fecha. Ignora acentos y mayúsculas, encuentra otras formas de la
  palabra ("cuota" → "cuotas"), fragmentos ("presu") y errores de dos letras
  cambiadas ("presupeusto"). Respeta las bandejas de cada agente.
- Migración `0f8e5a1c2b3d`: extensiones `pg_trgm` y `unaccent`, función
  `alo_search_text` e índices GIN de texto completo y trigramas sobre
  `messages`, creados `CONCURRENTLY`. **En CTC: respaldar antes.**
- `GET …/messages?around=<id>`: abre la conversación en el mensaje (antes
  `after` traía los 20 más nuevos y un resultado de hace un año abría hoy).
- Bandeja: buscar ahora lista mensajes; al abrir uno, la conversación se
  centra en él, marcado, con "Ir a lo último".
- Herramienta MCP `search_messages`.

**Hecho (paso 2, semántica, 2026-11-13):**

- Tabla `message_embeddings` (migración `1a2f8e3b4c5d`, índice HNSW): un
  vector de EmbeddingGemma por mensaje de 12 caracteres o más. Lo escribe
  el cron `embed_messages_task` cada 3 minutos, por lotes, del más nuevo al
  más viejo: es a la vez el backfill. No hace nada si el servicio local no
  está configurado. Nunca OpenAI: sería un costo por mensaje sin medir (F6).
- La búsqueda junta texto y significado (fusión por rango, el texto pesa
  más). Umbral 0,25, medido con el modelo real: lo pertinente cae entre 0,15
  y 0,28 y el ruido de temas vecinos empieza en 0,22, así que el significado
  nunca decide solo. Los resultados sólo por significado salen marcados
  "Relacionado". Si el servicio no responde, queda la búsqueda por texto.
- Arreglado el hallazgo del paso 1: abrir una conversación por número
  ahora aplica `ConversationPolicy#show?` (admin, miembro de la bandeja o del
  equipo) en todos los endpoints de una conversación; las acciones masivas
  saltean las que el agente no puede ver.

- Buscador dentro del chat: lupa en el encabezado de la conversación, busca
  sólo ahí (texto y significado) y abre el chat en el mensaje elegido.

- **Arreglado el 2026-11-15:** desde el 13/11 el servicio de Gemma de develop
  se caía por memoria cada 3 minutos (lotes de 64 × 2000 caracteres) y había
  0 vectores de mensajes. Ahora lotes de 16 (encode de a 4), 1000 caracteres
  y `MemoryMax=3072M`: sin caídas, pico 2,0 GB, ~16 mensajes cada 3 minutos.
  Al instalar el servicio en CTC, usar la unidad nueva.

**Falta:**

- Audios e imágenes. El dueño no quiere servicios pagos para esto
  (2026-11-15): opciones gratis, Whisper local (transcribe, 1-2 GB más) o
  Gemma completo (audio e imagen, ~4,4 GB). Probar Whisper local en develop. El servicio carga EmbeddingGemma 2 *sólo texto* (~2 GB);
  el modelo completo con imagen y audio pide ~4,4 GB. Medir en staging con
  notas de voz e imágenes antes de decidir: imágenes con Gemma; audios con
  Gemma, con transcripción o con las dos (un vector dice de qué trata un
  audio, no qué se dijo).

## F9. EmbeddingGemma 2

- Corre en sombra en develop desde el 2026-11-09. Después de 1 o 2 semanas:
  contar en cuántos casos coinciden los dos modelos
  (`same_decision` / `same_top1` en el log del backend, ver
  `docs/operacion/embeddings.md`).
- Revisar con el dueño la regla de autorespuesta de Instagram con umbral
  0,55 antes de pasar esa cuenta a Gemma.
- Pasar cuenta por cuenta; en CTC hoy no está configurado (sigue OpenAI).
- **Revisión del 2026-11-15:** la sombra no juntó datos. En develop, 0
  comentarios de Instagram por reglas y 0 artículos de Help Center en la
  semana; en CTC tampoco hay uso (0 reglas, 0 artículos, 5 comentarios en 30
  días). Sin tráfico real, la decisión queda con la medición offline que ya
  dio a Gemma por encima de OpenAI. Propuesta: pasar las cuentas de develop
  a Gemma ya (gratis, local) y en CTC instalar el servicio (hay 5,4 GB
  libres de 8) recién cuando empiecen a usar respuestas automáticas o el
  Help Center. La búsqueda de la Bandeja (F8) ya usa Gemma.
- **Hecho el 2026-11-15:** las 6 cuentas de develop leen con Gemma
  (`scripts/embeddings_gemma.py modelo <cuenta> gemma`). La sombra sigue
  prendida (ahora compara contra OpenAI). La regla 3 de Demo Co (0,55 en
  OpenAI) usa el umbral por defecto de Gemma, 0,15. Volver atrás: `modelo
  <cuenta> openai`.

## F10. Jev y Laya

- **Revisión antes de empezar (2026-11-15, agente B):**
  - **Los términos de Jev prohíben el plan original.** El contrato de
    TypeSafe (Master Customer Agreement, 2.3(b)) no deja usar el servicio ni
    sus respuestas para «model distillation» ni para entrenar un modelo que
    imite sus respuestas. Entrenar Laya con las decisiones de Jev queda
    descartado. Las respuestas son del cliente y TypeSafe no entrena con
    nuestros datos, pero puede guardarlos para telemetría y abuso.
  - **Jev:** `POST /v1/systemone` (choice, score y noul con
    probabilidades), USD 0,042 por millón de tokens de entrada (menos de un
    centavo cada mil decisiones). No publica resultados en español.
  - **Laya:** Apache 2.0, local, endpoint compatible con Jev. Sin entrenar
    rinde poco (0,36 de acierto, por debajo de elegir siempre lo más
    común); entrenada llega a 0,77. Hay checkpoint multilingüe (322M), CPU
    200–460 ms por decisión. Se entrena en Kaggle (2×T4).
  - **Ya tenemos** clasificación local con EmbeddingGemma (respuestas
    automáticas de Instagram): sirve de línea base gratis.
  - **Datos en CTC:** 29 conversaciones (desde el 6 de noviembre), 3 con
    etiqueta, 2 con equipo, ninguna con prioridad. No alcanza para entrenar
    nada todavía.
- **Camino elegido por el dueño (2026-11-15):** Jev ahora, sin entrenar
  Laya con sus respuestas; Laya aparte y más adelante, entrenada solo con
  etiquetas de personas.
- **Paso 1, Jev en modo sombra — hecho el 2026-11-15, en develop y en
  staging:**
  - **Ajustes → Clasificación** (solo administradores), tres pestañas:
    - **Configuración:** prender el modo sombra y editar las preguntas
      (intención, sentimiento, urgencia y equipo) con sus opciones. Las del
      equipo salen de los equipos de la cuenta.
    - **Etiquetar:** una persona lee la conversación y elige las respuestas
      sin ver las del servicio. El equipo que asigna un agente también
      cuenta como etiqueta.
    - **Resultados:** cuántas veces coincide el servicio con las personas,
      confianza promedio y costo del mes (también en Gastos por uso, IA).
  - Cada mensaje de un cliente programa una decisión 45 s después; varios
    mensajes seguidos se juntan en una. Al servicio le llegan los últimos
    12 mensajes (hasta 6.000 caracteres) anonimizados: correos, enlaces,
    números de 7 cifras o más, y los nombres del cliente y de la gente de
    la cuenta.
  - Las decisiones se guardan pero todavía no cambian nada que vea el
    agente.
  - Solo corre con el modo sombra prendido y el servicio configurado. Se
    configura en Ajustes → Instalación → Inteligencia artificial
    («Servicio de decisiones»: clave, dirección y modelo). Para pasar a
    Laya alcanza con cambiar la dirección y el modelo.
  - Las respuestas de Jev nunca se usan para entrenar: Laya se va a
    entrenar con las etiquetas de personas.
  - Código en `app/domains/decisions/` y en
    `frontend/components/settings/decisions/`. Probado con un Jev falso
    local, no con el real.
  - De paso: el worker relee la configuración de Ajustes → Instalación
    cada 20 s. Antes la leía solo al arrancar, así que una clave cargada
    desde el panel no llegaba a las tareas hasta reiniciarlo.
- **Para usarlo:** el dueño crea la cuenta en TypeSafe y carga la clave en
  Ajustes → Instalación (nunca por chat). Después prende el modo sombra y
  etiqueta conversaciones para ver cuánto acierta.
- **Jev real (2026-11-15):** el dueño cargó la clave en staging. Una
  prueba con una conversación inventada salió bien: `jev-1.14.0`, intención
  `inscripcion` (0,98), sentimiento `positivo` (0,97), urgencia `media`
  (0,77); 662 tokens de entrada, US$ 0,000028. La respuesta tiene la forma
  que espera el código.
- **De punta a punta en staging (2026-11-15):** el dueño prendió el modo
  sombra en la cuenta 1. Un mensaje de cliente se clasificó 45 s después
  en el worker, que tomó la clave sin reiniciarse: intención `reclamo`
  (0,81), sentimiento `molesto` (0,85), urgencia `media` (0,55) y equipo
  Postventa (0,21); 1.070 tokens, US$ 0,000045.
- **Falta:** juntar etiquetas en la pestaña Etiquetar y, con los
  resultados, decidir si las decisiones pasan a hacer algo (sugerir o
  asignar equipo, prioridad). Laya cuando haya suficientes etiquetas.
- **En CTC desde el 2026-11-15** (panel compilado a las 22:05): falta
  cargar la clave de Jev en su Instalación y prender el modo sombra en
  Ajustes → Clasificación. La pregunta del equipo usa los equipos de la
  cuenta; si no hay equipos, no se hace.

## F11. CRM (Krayin)

El dueño eligió sumar las cuatro cosas (2026-11-13), en este orden:

- **Oportunidades con embudo — hecho el 2026-11-13** (rama `feat/f11-crm`):
  embudos con etapas (abierta, ganada o perdida, con probabilidad), un
  embudo de ventas por defecto por cuenta, oportunidades con valor,
  contacto, producto, responsable, cierre estimado y conversación de
  origen. Tablero Kanban en CRM → Oportunidades (se arrastran las
  tarjetas entre etapas), marca de "estancada" y de cierre vencido, editor
  de etapas para administradores, y las oportunidades en la ficha del
  contacto. Backend en `app/domains/crm/`, panel en `components/crm/`.
- **Actividades y tareas — hecho el 2026-11-13:** tarea, llamada, reunión o
  correo, con vencimiento, responsable, contacto y oportunidad. CRM → Tareas
  las agrupa en vencidas, hoy, próximas y sin fecha (o hechas), con
  "Mías/Todas" y una casilla para marcarlas hechas; también aparecen en la
  ficha del contacto. Al vencer, el responsable recibe un aviso (en la app,
  por correo y push, según Ajustes → Notificaciones), una sola vez: lo
  revisa el tick de 5 minutos del worker. Tipo de aviso nuevo
  `crm_activity_due` (10).
- **Empresas — hecho el 2026-11-13:** nombre, web, correo, teléfono,
  dirección, identificación fiscal y notas. CRM → Empresas lista y busca;
  la ficha de cada empresa muestra sus personas (se agregan y quitan ahí) y
  las oportunidades de esas personas. La ficha del contacto muestra su
  empresa y permite asignarla o crear una nueva en el momento. Usa la
  columna `contacts.company_id` que ya existía (sin clave foránea); la
  migración limpió sus valores viejos, que no apuntaban a nada.
- **Origen del contacto — hecho el 2026-11-13:** cada contacto guarda cómo
  llegó: el canal de su primera conversación (WhatsApp, Instagram, chat del
  sitio…), o el anuncio, publicación o enlace directo cuando Meta lo informa
  (con el título del anuncio). Lo primero que llegó no se pisa. También se
  puede indicar a mano (recomendación, evento o feria, visita, llamada,
  sitio web, otro) con un detalle libre. Se ve en la ficha y en la lista de
  contactos, y se filtra por origen, canal y detalle (Filtros → Origen;
  sirve para segmentos). La migración completó los contactos existentes
  con su conversación más vieja. Columnas `contacts.source*`; lógica en
  `app/domains/crm/origin.py`.
- **Pedidos del dueño, 2026-11-13 — hecho:** foto del contacto subida a
  mano desde su ficha (Meta ya no la reemplaza; `POST/DELETE
  /contacts/{id}/avatar`), y la Agenda con el mismo formato que el
  Calendario de publicaciones (día, semana y mes; clic en un hueco para
  agendar).
- **Catálogo de Meta (pedido del dueño, 2026-11-13).** Pedido: que los
  productos del CRM (en CTC, los cursos) se sincronicen con un catálogo de
  Meta (Commerce Manager, Catalog API), y usarlo en:
  - WhatsApp: mandar uno o varios productos en un chat (mensajes de
    producto y multiproducto) desde la Bandeja o el bot; los pedidos que
    arma el contacto llegan por el webhook (`order`) y pueden crear una
    oportunidad en el embudo;
  - Instagram y Facebook: etiquetar productos en publicaciones y anuncios
    de catálogo.
  Requisitos: permiso `catalog_management` (revisión de Meta con su
  video); conectar el catálogo a la cuenta de WhatsApp Business. El pago
  dentro de WhatsApp no existe en Uruguay (se cobra por fuera); confirmar
  si Uruguay tiene tiendas de Instagram/Facebook habilitadas.
  - **Sincronización — hecha el 2026-11-14 (agente B):** CRM → Productos →
    tarjeta "Catálogo de Meta". Un administrador pega el ID del catálogo y
    el token de un usuario del sistema con `catalog_management`; queda en
    `integrations_hooks` (`app_id = "meta_catalog"`). Los productos activos
    se envían con `items_batch` (los inactivos o borrados se quitan); los
    que no tienen descripción, precio con moneda, enlace o imagen no se
    envían y dicen qué les falta; lo que Meta rechaza se muestra en cada
    producto. Cada cambio en un producto sincroniza a los 30 segundos
    (tarea `sync_meta_catalog_task`). El id del producto en Meta
    (`retailer_id`) es su SKU o `alo-{id}`, guardado en
    `products.meta_retailer_id`. Lógica en `app/domains/crm/meta_catalog.py`.
    **Arreglado el 2026-11-15** (en develop, todavía no en CTC): después de
    una sincronización, los cambios de la hora siguiente se perdían (ARQ
    no acepta el mismo id de trabajo mientras guarda su resultado).
  - **WhatsApp — hecho el 2026-11-14 (agente A), en develop:** botón
    Productos en la Bandeja, pedidos por el webhook que abren una
    oportunidad y pestaña Catálogo en la sección WhatsApp (ver F5).
  - **Sigue (más adelante):** etiquetar productos en Instagram y Facebook.
- **F11 terminada:** las cuatro partes elegidas, más foto del contacto,
  Agenda tipo calendario y sincronización con el catálogo de Meta.
- Pendiente para más adelante: abrir una oportunidad desde la bandeja
  (el campo `conversation_id` ya existe) y presupuestos.

## F12. Grafos

Para más adelante, cuando la app esté lista.

## F13. Multi-idioma

Detalle en `PLAN.i18n.md`.

- **Hecho el 2026-11-12, en develop:** estructura propia sin librerías
  (`frontend/lib/i18n/`) y **toda la interfaz del panel traducida** a
  español, inglés, portugués, francés, alemán, japonés y coreano. Cada
  usuario elige en Ajustes → Mi perfil → Idioma (se guarda en
  `ui_settings.locale`); sin sesión, selector en el login; si no eligió,
  el del navegador. `node scripts/i18n-pendientes.mjs` en `frontend/` quedó
  en 58 textos, todos marcas o términos técnicos (empezó en 1254).
- **Backend, hecho el 2026-11-12:** correos (confirmación, recuperar
  contraseña, invitaciones, avisos), avisos push y por WhatsApp en el idioma
  de cada destinatario (`app/core/i18n/`); Instalación y Plugs traducidos
  en el panel; quien nunca eligió idioma queda con el que ve al entrar.
- **También hecho:** errores de la API con códigos que el panel traduce;
  fechas y números en el idioma del panel; revisión en el navegador; guía
  de la plantilla de WhatsApp en cada idioma (`docs/whatsapp-aviso-derivacion.md`).
- **Decidido:** español como idioma por defecto (el inglés, el día que haya
  público internacional). El bot de clientes, más adelante y por fuera del
  sistema, usando la CLI o el MCP.
- **Falta:** cargar y aprobar en Meta las variantes de la plantilla de
  WhatsApp en los idiomas que se usen.

## F14. Foto del contacto

- **Hecho el 2026-11-12, en develop:** columnas `avatar_url` y
  `avatar_refreshed_at` en `contacts` (migración `c2d3e4f5a6b8`). La foto
  de Instagram y Messenger (`profile_pic` del Graph) se baja a MinIO unos
  segundos después del primer mensaje (trabajo de ARQ) y se renueva cada 7
  días para los contactos activos en los últimos 30 (cron diario 04:23 UTC,
  hasta 200 por corrida). Se sirve por `GET /contacts/{id}/avatar` y llega
  en `thumbnail`; `Avatar` la muestra en la lista y el encabezado de la
  Bandeja, el panel del contacto y la lista de Contactos, y cae a las
  iniciales si no hay o no carga. Las iniciales ya ignoran símbolos y lo que
  va entre paréntesis ("Lucía Pereira (demo)" da "LP").
- **Falta probarlo con Meta real** (en develop o CTC): que el Graph devuelva
  `profile_pic` con los permisos actuales. Antes de la revisión de la app,
  Meta solo responde por personas con rol en la app; sin foto quedan las
  iniciales, sin error.
- Los contactos viejos reciben foto en la primera corrida del cron después
  de desplegar, si escribieron en los últimos 30 días.
- WhatsApp sigue con iniciales (la API no da la foto). Gravatar para email:
  no se hizo (opcional en el plan, apagado por defecto).
- Al borrar un contacto, su foto queda en MinIO (clave fija por contacto,
  pesa pocos KB). Borrarla junto con el contacto si llega a importar.

## F15. Canal de aviso por agente

- Esperar lo que prefieren los agentes de CTC (Sofía lo consulta el
  2026-11-11). Telegram con un bot propio sería la opción gratis.

## F17. Funciones de respond.io

- **Comparación (2026-11-16, agente B):** respond.io es el producto más
  parecido a AloStudio. Lo que tiene y nosotros no, con lo que decidió el
  dueño:

| # | Función | Decisión del dueño |
|---|---|---|
| 1 | Ayuda de IA al escribir: reformular, traducir, resumir | Sí. Con modelo de un proveedor, en el plan más caro y con créditos de IA; con un modelo liviano en la VPS, para todos |
| 2 | Conversions API de Meta (avisarle a Meta qué chats de anuncios terminan en venta) | Sí, le sirve a CTC |
| 3 | Workflows visuales: preguntar y esperar la respuesta, ramas, esperas | A acordar entre el dueño y el agente B: propios o con n8n |
| 4 | Notas de cierre (motivo al cerrar una conversación, para reportes) | Sí |
| 5 | Resumen de llamadas con IA | Sí, en el plan más caro; lo prende el superadmin de cada instalación y gasta créditos de IA |
| 6 | Agente de IA que atiende llamadas | Contemplado (F7 paso 3) |
| 7 | Etapas del contacto | Sí, con la nomenclatura de respond.io |
| 8 | TikTok como canal de mensajes | Sí |
| 9 | Llamadas de Messenger y telefonía VoIP | Sin decidir (el dueño preguntó qué es VoIP) |
| 10 | Ocultar el teléfono y el correo del cliente a los agentes | Tentativo |
| 11 | Integraciones | Google, login y Calendar: sí. HubSpot, Salesforce, Zapier y Make: no. n8n: ver el 3 |
| — | 2FA y SSO; apps nativas | Sin decidir |

- **Notas:**
  - 1: hace falta un modelo de lenguaje. Con OpenAI (ya configurado) cuesta
    menos de US$ 0,001 por texto. Un modelo local de 1 a 4 mil millones de
    parámetros en la VPS de CTC (4 núcleos, sin GPU) tardaría varios
    segundos por texto: hay que medirlo antes de decidir.
  - 3: la licencia de n8n (Sustainable Use License) permite usarlo para el
    negocio propio, no ofrecérselo a clientes que pagan. Meterlo adentro de
    AloStudio para los clientes de los planes pide su licencia comercial.
    Que CTC lo use para sí mismo, conectado por webhooks y la API, sí se
    puede.
  - 8: es TikTok según el orden de la tabla que vio el dueño.
  - 11: el login con Google ya está hecho; falta crear el cliente OAuth en
    Google Cloud y cargar `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` en
    Ajustes → Instalación.
- **4, notas de cierre — hecho el 2026-11-17 (agente B, rama
  `feat/f17-notas-de-cierre`):**
  - Ajustes → Notas de cierre (administradores): prenderlas, hacerlas
    obligatorias y editar los motivos (5 por defecto, hasta 30). Vienen
    apagadas.
  - Al tocar «Resolver» en una conversación se abre una ventana con los
    motivos y una nota opcional. Queda una nota privada en la conversación
    («Nota de cierre: motivo») y una fila en `conversation_closings`. Las
    automatizaciones, las acciones masivas y la API resuelven sin preguntar.
  - Estadísticas: tarjeta «Motivos de cierre» con los cierres del período
    por motivo; la ve cualquiera de la cuenta, como el resto de los reportes.
  - Dominio `app/domains/closing/`, migración `d7e8f9a0b1c4`. Probado en
    local de punta a punta (ajustes, cierre, nota y reporte).

---

## Pendientes sueltos (no son de una fase)

- **Sofía, en cada dispositivo:** activar el push en Ajustes →
  Notificaciones → Este dispositivo y probar el sonido. Si quiere, el aviso
  por WhatsApp con su número.
- **Agentes en las bandejas de CTC:** resuelto el 2026-11-11. Sofía Costa es
  administradora (chats y publicaciones) y Yamila Gonzalez agente (solo
  chats); las dos están en las 4 bandejas.
- **Revisiones de Meta de CTC y de Skiev:** los borradores están listos; los
  envía el dueño. Después, borrar el contenido de prueba en Meta.
- **Bot de CTC:** las frases que nunca debe decir (`never_say_phrases`)
  siguen sin cargar hasta que el dueño lo confirme con el director.
- **Capacitación del 11/11:** abrir el PPTX en PowerPoint antes, nunca se
  probó ahí.
- **Tests de webhooks** (`test_webhooks_router.py`): dos fallan cuando hay
  Redis al alcance, porque la entrega se encola en el worker. Hacer que el
  test fuerce la entrega inmediata.
- **Colores con transparencia** (`bg-x/NN` sobre colores del tema) no generan
  CSS: falta el arreglo central en la configuración de Tailwind.
