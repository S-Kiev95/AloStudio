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
> sumás o si preferís que las haga yo.

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

| Fase | Agente | Estado |
|---|---|---|
| F1 Respaldos | — | Hecha en CTC |
| F2 Multitenant | A | Pasos 1 y 2 hechos en `feat/multitenant`; resto para más adelante |
| F3 Redes que faltan | B | Sin empezar |
| F4 Herramientas MCP | A | Hecha (2026-11-11), en develop |
| F5 WhatsApp (plantillas, envíos, número, perfil, QR) | A | En develop (2026-11-13); falta CTC |
| F6 Gastos por uso | A | Sin empezar |
| F7 Llamadas y voz | B | Sin empezar |
| F8 Búsqueda en conversaciones viejas | A | Hecha para texto (2026-11-13), en develop: palabras y significado; faltan audios e imágenes |
| F9 EmbeddingGemma | A | En develop, comparando en sombra con OpenAI |
| F10 Jev y Laya | B | Sin empezar |
| F11 CRM (Krayin) | B | Oportunidades, tareas y empresas hechas (2026-11-13); sigue el origen del contacto |
| F12 Grafos | B | Para más adelante: el dueño prefiere hacerla cuando la app esté lista (2026-11-13) |
| F13 Multi-idioma | B | Hecha (2026-11-12), en develop: 7 idiomas, correos, avisos y errores traducidos; falta cargar en Meta la plantilla de WhatsApp en otros idiomas |
| F14 Foto del contacto | B | Hecha (2026-11-12), en develop; falta probarla con Meta real |
| F15 Canal de aviso por agente | A | Idea; esperando la opinión de los agentes de CTC |

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
  En la Bandeja: botón "Plantilla" y `can_reply` false pasadas 24 h del
  último mensaje del contacto (solo se manda plantilla).
- Pendiente: pasarlo a CTC cuando el dueño lo pida; textos de la sección sin
  traducir (solo español); encabezados con imagen, video o documento;
  avisos cuando Meta baja la calidad del número (webhooks
  `phone_number_quality_update` y `account_update`, hay que suscribirlos);
  ritmo de envío según el límite diario en envíos grandes.

## F6. Gastos por uso

- Guardar el `pricing` de los estados de WhatsApp, tabla de precios por
  categoría y país, uso de IA por cuenta; mostrarlo en Estadísticas.

## F7. Llamadas y voz

- Revisar requisitos y costo de las llamadas de WhatsApp; investigar lives;
  agentes de voz después.

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

**Falta:**

- Audios e imágenes. El servicio carga EmbeddingGemma 2 *sólo texto* (~2 GB);
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

## F10. Jev y Laya

Sin cambios respecto del plan.

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
- **Sigue:** origen del contacto.
- **Catálogo de Meta (pedido del dueño, 2026-11-13):** que los productos
  del CRM (en CTC, los cursos) se sincronicen con un catálogo de Meta
  (Commerce Manager, Catalog API), y usarlo en:
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
