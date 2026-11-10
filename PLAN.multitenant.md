# F2: AloStudio multitenant (rama `feat/multitenant`)

Bajada de la F2 de `PLAN.fases-futuras.md`. Arrancada el 2026-11-10.

## Dónde vive este trabajo

- **`main` es la instalación propia de CTC.** CTC queda como cliente con su
  instancia dedicada, el modelo "Enterprise" de la F2. Nada del multitenant
  entra en `main`.
- Todo va en la rama `feat/multitenant`, que salió de `develop`. Para
  mantenerla al día se mezcla `develop` en ella, nunca al revés: `develop`
  pasa a `main` en cada despliegue de CTC.
- Un arreglo que también le sirva a CTC va a `develop` como commit propio y
  después se trae a esta rama.
- No se despliega en ningún servidor sin que el dueño lo pida.

## Paso 1. Aislamiento entre cuentas

AloStudio separa los datos por `account_id`. En una instalación con muchas
cuentas, un usuario de una cuenta no puede ver, cambiar ni enumerar datos de
otra, ni siquiera probando ids.

Alcance medido: 340 rutas en 52 routers, 113 lecturas por id
(`session.get`), 9 grupos de herramientas MCP y 10 tareas del worker.

### 1.a Rutas: ids en la URL

Las rutas con id en la URL buscan el registro filtrando por la cuenta
(`_find_*_in_account`) o comparan `row.account_id` contra la cuenta del
pedido. Revisadas: agent bots (los de sistema tienen `account_id` nulo y
son de lectura), adjuntos (el público pide firma), publicaciones,
autorespuestas de Instagram, plantillas de WhatsApp, webhooks e
integraciones. Sin hallazgos.

### 1.b Rutas: ids en el cuerpo del pedido (hallazgos)

| # | Dónde | Qué pasa | Arreglo |
|---|---|---|---|
| 1 | `inboxes.service.add_members` (POST/PATCH `/inbox_members`) | Acepta `user_ids` de cualquier cuenta. El usuario ajeno no gana acceso, pero su nombre y email aparecen en la lista de miembros: un admin puede enumerar usuarios de otras cuentas | Solo usuarios de la cuenta; si no, 422 |
| 2 | `POST /conversations` (`assignee_id`, `team_id`) | Pasan directo a `create_conversation`: una conversación puede quedar asignada a un usuario o equipo de otra cuenta, que además recibe el aviso | Validar contra la cuenta; si no, 422 |
| 3 | `portal_id` al crear o editar una bandeja | No se valida: una bandeja puede quedar ligada al centro de ayuda de otra cuenta | Validar `Portal.account_id`; si no, 422 |

| 4 | `inbox_id` al crear o editar un webhook | No se valida. La respuesta muestra el nombre de la bandeja ajena; los webhooks por bandeja todavía no se entregan, pero cuando se activen recibirían sus eventos | Validar `Inbox.account_id`; si no, 422 |
| 5 | Bandeja de Facebook creada a mano | `page_id` es único solo por cuenta, y los mensajes entrantes se reparten por `page_id`: una segunda cuenta con la misma página recibiría mensajes de la primera. El OAuth ya lo impedía; la carga manual no | Rechazar una página que ya está en otra cuenta, 422 |
| 6 | WhatsApp entrante (`_for_channel`) | Si el canal no tiene guardado su `phone_number_id`, aceptaba cambios que nombran cualquier número | Un canal sin id solo acepta cambios que no nombran número |

Estado: los seis corregidos en esta rama, con casos en
`tests/integration/test_tenant_isolation.py`.

Ya validados: los integrantes de equipos (401 "Invalid User IDs", como
Chatwoot), `contact_id`, `inbox_id` y `source_id` al crear una
conversación o un contact inbox, la unión de contactos, participantes,
`assignment_policy_id`, `conversation_ids` de las macros, `product_ids` de
Instagram, `channel_id` de los plugs, `handoff_assignee_id`, la bandeja de
las campañas (se valida al crear y no se puede cambiar) y los equipos y
agentes dentro de automatizaciones y macros (se resuelven dentro de la
cuenta de la conversación).

### 1.c Resto de la auditoría (2026-11-10)

- **Worker (ARQ):** las tareas cargan por id y siguen las relaciones del
  propio registro; el envío de campañas busca los contactos con
  `account_id` de la campaña. Sin hallazgos.
- **Webhooks entrantes:** firma de Meta y de Twilio activa en CTC y en
  develop (`META_VERIFY_WEBHOOK_SIGNATURE`, `TWILIO_VERIFY_SIGNATURE`; la
  clave de Meta se carga desde Ajustes). Número de WhatsApp, id de
  Instagram, bot de Telegram y correo son únicos en toda la instalación.
  Hallazgos 5 y 6 arriba.
- **MCP:** el token está atado a una cuenta y cada herramienta lee
  `ctx.account`; las lecturas por id comparan `account_id`. Sin hallazgos.
- **Tiempo real:** para suscribirse hace falta el `pubsub_token` del
  usuario y, para el canal de la cuenta, ser miembro. Sin hallazgos.
- **Públicas:** el widget resuelve todo desde el token del sitio y el del
  visitante; el centro de ayuda usa un slug único y filtra artículos,
  categorías y vectores por portal; la configuración de la instalación es
  solo para superadministradores. Sin hallazgos.
- **Búsqueda y reportes:** filtran siempre por la cuenta, también cuando
  se pide una bandeja, agente o equipo por id. Sin hallazgos.

### 1.d Requisitos para el alta de clientes (paso 2)

Salen de la auditoría y no son arreglos de una línea:

- **Probar que el canal es de quien lo conecta.** Hoy una bandeja de
  WhatsApp, Instagram o Facebook se puede crear a mano con cualquier
  número o id. Con muchos clientes, una cuenta podría registrar el número
  o el Instagram de otra empresa (por ejemplo después de que esa empresa
  se dé de baja, con la suscripción de Meta todavía activa) y recibir los
  mensajes de sus clientes. En multitenant los canales de Meta se conectan
  solo por Embedded Signup y OAuth, que sacan el id del token; la carga
  manual queda apagada o verifica contra la Graph API que el token tiene
  acceso a ese id.
- **Un solo webhook de WhatsApp para la app.** Con una sola app de Meta
  como tech provider, Meta manda los eventos de todos los números a una
  misma dirección. Hoy la dirección lleva el número
  (`/webhooks/whatsapp/{phone_number}`) y los cambios de otros números se
  descartan. Hace falta una ruta de app que reparta cada cambio por
  `phone_number_id`.
- **Superadministrador desde el día uno.** Si no hay ninguno, la
  configuración de la instalación la controla el administrador de la
  primera cuenta.

### 1.e Tests

`tests/integration/test_tenant_isolation.py`: dos cuentas, y la cuenta A
intenta referenciar usuarios, equipos, portales, bandejas y páginas de la
B por cada camino encontrado. Cada hallazgo nuevo suma su caso.

## Pasos siguientes (necesitan decisiones del dueño)

2. **Alta de clientes** (en curso, ver "Paso 2" abajo).
3. **Facturación:** proveedor de pagos, moneda, planes y límites. El código
   del webhook de pagos no puede tirar excepciones.
4. **Límites de uso:** cuotas por cuenta en el worker y la API.
5. **Operación:** panel interno de cuentas, métricas, borrado y exportación
   de datos de una cuenta.
6. **Enterprise:** script de despliegue en servidor dedicado, como CTC hoy.
7. **Legal:** términos, privacidad y acuerdo de tratamiento de datos.

## Paso 2. Alta de clientes (2026-11-10)

### Backend (hecho, con tests en `tests/integration/test_multitenant_onboarding.py`)

- **`MULTITENANT`** (variable de entorno, apagada por defecto). Prendida:
  - `POST /inboxes` rechaza WhatsApp, Instagram y Facebook cargados a mano
    (422): se conectan solo con Embedded Signup y OAuth.
  - El registro (`POST /api/v1/accounts`, con `ENABLE_ACCOUNT_SIGNUP`)
    crea la cuenta sin confirmar, manda el correo de confirmación, no abre
    sesión y limita a 5 registros por hora por IP. El login ya rechazaba a
    quien no confirmó.
  - La configuración de la instalación es solo para superadministradores
    (sin la regla del "admin de la primera cuenta").
- **`GET /api/v1/installation/public`**: `signup_enabled` y `multitenant`
  para las pantallas sin login.
- **Webhook único de WhatsApp** `GET/POST /webhooks/whatsapp`: handshake
  con `WHATSAPP_VERIFY_TOKEN`, firma de Meta, y cada cambio va a la cuenta
  cuyo canal tiene ese `phone_number_id` (si dos canales lo tienen, no se
  entrega y queda en el log). La ruta por número sigue funcionando.
- **Embedded Signup de WhatsApp**
  (`/api/v1/accounts/{id}/whatsapp/embedded_signup`): canje del código,
  `debug_token` (el token es de nuestra app y tiene permiso sobre esa
  WABA), número leído de Meta, suscripción de la app a la WABA apuntando al
  webhook único, y recién ahí se guarda el canal. Un número de otra cuenta
  se rechaza; uno de la misma cuenta se reconecta con token nuevo. Registra
  el número en la Cloud API si Meta dice que hace falta.
- Ajustes nuevos en Ajustes → Instalación: `WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID`
  y `WHATSAPP_VERIFY_TOKEN`.

### Frontend (Argon, `PLAN.registro-y-whatsapp.md`)

Página de registro, link en el login, botón "Conectar WhatsApp" con el SDK
de Meta y formularios manuales de Meta ocultos en multitenant.

### Lo que hace el dueño del lado de Meta (antes de probar en serio)

1. En la app de Meta multi-cliente: producto WhatsApp, y en Facebook Login
   for Business una configuración de tipo "WhatsApp Embedded Signup"; su
   ID va a `WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID`.
2. Webhook de la app (WhatsApp → Configuración): URL
   `https://<dominio>/webhooks/whatsapp`, token = `WHATSAPP_VERIFY_TOKEN`,
   campos `messages`, `message_echoes`, `messaging_handovers` y `standby`.
3. Tech Provider: verificación del negocio y acceso avanzado a
   `whatsapp_business_management` y `whatsapp_business_messaging` en la
   revisión de la app.
4. En el servidor multitenant: `MULTITENANT=true`, `ENABLE_ACCOUNT_SIGNUP`
   cuando se quiera abrir el registro, y un superadministrador creado antes
   de abrirlo.

### Pendiente del paso 2

- Al borrar una bandeja conectada por Embedded Signup, desuscribir la app
  de la WABA (`DELETE /{waba_id}/subscribed_apps`) para que Meta no siga
  mandando sus mensajes.
- Captcha en el registro, si el límite por IP no alcanza.
