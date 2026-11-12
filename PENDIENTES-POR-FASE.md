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

| Fase | Agente | Estado |
|---|---|---|
| F1 Respaldos | — | Hecha en CTC |
| F2 Multitenant | A | Pasos 1 y 2 hechos en `feat/multitenant`; resto para más adelante |
| F3 Redes que faltan | B | Sin empezar |
| F4 Herramientas MCP | A | Hecha (2026-11-11), en develop |
| F5 Plantillas de WhatsApp | A | Sin empezar |
| F6 Gastos por uso | A | Sin empezar |
| F7 Llamadas y voz | B | Sin empezar |
| F8 Búsqueda en conversaciones viejas | A | Sin empezar |
| F9 EmbeddingGemma | A | En develop, comparando en sombra con OpenAI |
| F10 Jev y Laya | B | Sin empezar |
| F11 CRM (Krayin) | B | Sin empezar |
| F12 Grafos | B | Sin empezar |
| F13 Multi-idioma | B | Interfaz en 7 idiomas, correos y avisos en el idioma del destinatario, en develop (2026-11-12); falta el bot externo (Alicia), errores de la API y revisión en navegador |
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

## F5. Plantillas de WhatsApp

- Pantalla para listar, crear, editar y borrar plantillas, con vista previa
  y aviso de cambios de estado; mandar plantillas desde la Bandeja pasadas
  las 24 h.

## F6. Gastos por uso

- Guardar el `pricing` de los estados de WhatsApp, tabla de precios por
  categoría y país, uso de IA por cuenta; mostrarlo en Estadísticas.

## F7. Llamadas y voz

- Revisar requisitos y costo de las llamadas de WhatsApp; investigar lives;
  agentes de voz después.

## F8. Búsqueda en conversaciones viejas

- Búsqueda por mensaje con salto al mensaje (texto completo de Postgres en
  español + `pg_trgm`); semántica después, con F9; herramienta MCP
  `search_messages`.

## F9. EmbeddingGemma 2

- Corre en sombra en develop desde el 2026-11-09. Después de 1 o 2 semanas:
  contar en cuántos casos coinciden los dos modelos
  (`same_decision` / `same_top1` en el log del backend, ver
  `docs/operacion/embeddings.md`).
- Revisar con el dueño la regla de autorespuesta de Instagram con umbral
  0,55 antes de pasar esa cuenta a Gemma.
- Pasar cuenta por cuenta; en CTC hoy no está configurado (sigue OpenAI).

## F10 a F12

Sin cambios respecto del plan: Jev y Laya, CRM con base Krayin y grafos.

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
- **Falta:** el bot que atiende clientes (Alicia) vive fuera del repo: la
  regla para responder en el idioma del cliente está en `INTEGRATIONS.md`,
  falta aplicarla allá con el visto bueno del dueño. Además: errores de la
  API como códigos traducibles, la plantilla de WhatsApp aprobada en otros
  idiomas, y revisar las pantallas en el navegador en cada idioma.

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
