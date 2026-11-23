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

- ~~Al borrar una bandeja conectada por Embedded Signup, desuscribir la app
  de la WABA~~ **Hecho (2026-11-23):** `embedded_signup.release_waba` desde
  `DELETE /inboxes/:id`, con el token del negocio; no si otra bandeja usa
  la misma WABA, y si Meta falla la bandeja se borra igual (queda en el log).
- Captcha en el registro, si el límite por IP no alcanza.

### Para el lanzamiento (pedido del dueño, 2026-11-10)

- **Elegir y pagar un plan al registrarse:** el registro termina en el
  paso 3 (facturación). La cuenta queda en prueba o suspendida hasta que
  el pago se confirme.
- **Entrar con cuentas de otros servicios:** además del email, Facebook, X
  y los demás que se decidan. Google ya existe (`app/domains/auth/google.py`):
  revisar que en multitenant cree la cuenta con el mismo flujo del registro.

## Paso 3. Facturación con Polar (2026-11-15, en curso)

El dueño eligió **Polar** (polar.sh): cobra como Merchant of Record
(se ocupa de impuestos e IVA de cada país), suscripciones y portal del
cliente. Rama `feat/multitenant`; no se mergea hasta tener F2 completo.

### Backend (hecho, tests en `tests/integration/test_billing_polar.py`)

- Ajustes → Instalación, grupo "Cobros (Polar)": `POLAR_ACCESS_TOKEN`,
  `POLAR_WEBHOOK_SECRET`, `POLAR_SERVER` (`sandbox` / `production`).
- Los planes son los **productos recurrentes de Polar** (se leen de Polar,
  no se cargan acá). `GET /accounts/{id}/billing/plans`.
- `POST /accounts/{id}/billing/checkout {product_id}`: enlace de pago de
  Polar con `external_customer_id` y `metadata.account_id` = la cuenta.
- `POST /accounts/{id}/billing/portal`: portal de Polar (tarjeta,
  facturas, cancelar). `GET /accounts/{id}/billing`: plan, estado y si da
  acceso (`active` o `trialing`).
- Webhook `POST /webhooks/polar`: firma Standard Webhooks (secretos
  nuevos y viejos de Polar), rechaza repeticiones de más de 5 minutos,
  guarda cada evento por `webhook-id` (un reintento no se aplica dos veces)
  y **nunca tira error**: si algo falla queda en `billing_events.error` y
  responde 202. Los `subscription.*` actualizan `account_subscriptions`.
- Tablas `account_subscriptions` y `billing_events` (migración
  `7e3c9a1f5b2d`).
- Tests de la rama: base aparte `alostudio_test_mt` (la de develop va
  adelantada en migraciones).

### Bloqueo sin plan (hecho 2026-11-15)

Solo con `MULTITENANT=true`; en una instalación propia (CTC, Enterprise) no
hace nada ni consulta la base.

- **API:** `account_context` (lo usan todas las rutas de cuenta, también
  vía `require_admin`) responde **402** `{"error": "This account has no
  active plan", "code": "subscription_required"}` si la suscripción no está
  `active` ni `trialing`. El frontend traduce por `code`.
- **Abierto sin plan:** `/billing/*` usa `require_billing_admin` (solo
  membresía y admin, sin chequeo de plan) para elegir plan y pagar. También
  la cuenta en sí (`GET`/`PATCH /accounts/{id}`) y su lista de agentes, que
  no pasan por `account_context` y no consumen nada. Un agente no admin de
  una cuenta sin plan recibe 401 en `/billing`: la pantalla le dice que le
  pida al admin.
- **MCP:** `resolve_token` rechaza los tokens "API y MCP" y los de OAuth de
  una cuenta sin plan (401 del MCP).
- **Tiempo real:** el websocket rechaza la suscripción a `account_<id>`.
- **Sigue andando:** widget web, centro de ayuda y media pública.
- No se borra nada: al volver a pagar, el webhook pone la suscripción en
  `active` y todo vuelve a andar.
- Sin bloquear todavía: los webhooks de entrada (WhatsApp, Instagram...)
  siguen guardando mensajes, para no perder conversaciones; las
  autorespuestas y la IA del worker se cortan con los topes por plan.
- Tests en `test_billing_polar.py` (402, estados, instalación propia, MCP).

### Pantallas de plan y facturación (hecho 2026-11-15)

En los 7 idiomas (`messages/*/billing.ts`). Solo con `MULTITENANT=true`.

- **Elegí un plan:** `SubscriptionGate` (en el shell) reemplaza la página
  cuando la cuenta no tiene plan; cubre también el alta, porque una cuenta
  nueva entra sin plan. Muestra los planes de Polar con precio y días de
  prueba (`trial_days`, nuevo en `/billing/plans`); elegir uno abre el
  checkout de Polar. Un agente no admin ve "pedile a un administrador".
- **Cualquier 402** hace que se vuelva a pedir el estado, no los planes
  (`lib/query.ts`),
  así la pantalla aparece aunque el plan venza a mitad de sesión; un 402 no
  se reintenta.
- **Ajustes → Facturación** (`settings/billing`, en el menú solo en
  multitenant): plan, estado, renovación o fin de la prueba, botón al
  portal de Polar, y los planes mientras no haya uno activo. Al volver del
  checkout (`?checkout_id=`) consulta cada 3 s hasta que llega el webhook
  (un minuto como máximo). En una instalación propia la página da 404.
- `GET /billing` lo puede leer cualquier miembro (solo plan y estado);
  pagar y el portal siguen siendo de administradores.
- Tests en `components/billing/billing.test.tsx`.

### Planes (decididos 2026-11-15, creados en Polar **sandbox**)

Organización sandbox: `S Kiev` (`17fc0826-cf00-4bcb-a5db-5c1c26a53bed`).
Todos recurrentes mensuales, en USD, precio fijo.

| Plan | Precio | Prueba | Incluye | Producto | Precio (price id) |
|---|---|---|---|---|---|
| Basic | USD 10/mes | 30 días | Redes de Meta (Facebook, Instagram, WhatsApp, Messenger) | `552e7618-e08e-47e6-995b-8049bc827722` | `e139fc26-37a0-49a7-a3e4-661af6c4c7a5` |
| Pro | USD 25/mes | 30 días | Basic + resto de las redes | `cb6b25c0-813f-486c-80b7-5d19341f09dd` | `1aed31d0-33e4-4d8b-8e6e-6377db37fbda` |
| Max | USD 50/mes | sin prueba | Pro + llamadas de WhatsApp; tope de consumo USD 40/mes | `ab94ac2c-ab4f-4004-a184-f81ec4aee352` | `839dbfc0-5502-4f4c-8599-6be2cc96b54e` |

- Metadata de cada producto (para leer el plan sin depender del nombre):
  `plan` (`basic` / `pro` / `max`), `channels` (`meta` / `all`),
  `whatsapp_calls` (solo Max en `true`) y `usage_cap_usd_cents` (Basic
  500, Pro 1500, Max 4000).
- Tope de Max: más adelante se amplía con **paquetes de crédito** (productos
  de pago único en Polar); todavía no creados.
- Son IDs de sandbox: en producción hay que crearlos de nuevo y cambian.

### Topes por plan (hecho 2026-11-16)

Decisiones del dueño: correo, chat web y API vienen en todos los planes;
(2026-11-16, con los créditos: el tope pasa a ser solo de IA, ver abajo);
el tope suma IA y WhatsApp; Basic USD 5, Pro USD 15, Max USD 40.

- **De dónde salen:** la metadata del producto de Polar se copia en
  `account_subscriptions.plan_features` (migración `8f4d2b6a1c3e`) con
  cada webhook de suscripción, así que un plan se cambia en Polar sin
  deploy. Ojo: editar la metadata no dispara webhooks; cada cuenta toma
  el cambio en su próximo evento (renovación, cambio de plan). Valores en
  texto ("true", " Meta ", "1500") se leen igual; un tope que no es un
  número positivo se ignora. Solo con `MULTITENANT=true`.
- **Redes (Basic, `channels: meta`):** crear bandejas de Telegram o SMS y
  conectar para publicar LinkedIn, TikTok, X, Discord, Slack o Telegram
  responde **403** `plan_upgrade_required`. WhatsApp, Messenger,
  Instagram, Facebook, Threads, correo, chat web y API se permiten en
  todos. Lo ya conectado antes de bajar de plan no se borra ni se corta.
- **Llamadas (`whatsapp_calls`):** activarlas en un número, pedir permiso,
  llamar y atender dan 403 sin el plan; desactivarlas siempre se puede.
  Si una cuenta baja de Max con las llamadas prendidas en Meta, la llamada
  entrante se rechaza en el webhook (`action: reject`) en vez de sonar sin
  que nadie pueda atender.
- **Tope de consumo:** `limit_reached` de F6 corta también cuando IA +
  WhatsApp del mes llegan al tope del plan (IA, plantillas, campañas;
  las respuestas dentro de las 24 h siguen). WhatsApp suma solo si Meta
  factura la cuenta en USD (no hay tipo de cambio); si no, cuenta solo IA
  y queda en el log. Los topes que pone un admin en Gastos siguen además.
- **Pantallas:** el 403 se muestra traducido ("Tu plan no incluye esto…")
  y Facturación muestra el consumo del mes contra el tope.
- Tests en `test_billing_polar.py` y `billing.test.tsx`; probado en la
  instalación local (Telegram bloqueado con Basic, barra de consumo).

### Sandbox primero, producción después (dueño, 2026-11-15)

Todo F2 se termina y se prueba de punta a punta contra Polar **sandbox**:
registro, elegir plan, checkout, prueba gratis de 30 días, renovación,
pago rechazado (bloqueo sin borrar datos), portal y cancelación, con el
webhook apuntando al servidor de prueba. Recién con eso probado se pasa a
producción: crear los tres productos en Polar producción, token y webhook
nuevos, `POLAR_SERVER=production` y actualizar los IDs acá.

### Prueba en sandbox (2026-11-15, instalación local + túnel)

Backend de la rama en :8010 con `MULTITENANT=true` y base
`alostudio_mt_dev`, frontend en :3010, `.env.local` (ignorado) con el
token y el secreto; webhook de Polar sandbox
`67532852-1beb-4576-9c89-5fe00aefe6d8` a un túnel `trycloudflare` (la URL
cambia cada vez que se abre el túnel: actualizar el webhook en Polar).

Anduvo:

- Registro, correo de confirmación (MailHog) y "Elegí un plan" al entrar.
- Planes leídos de Polar con precio y días de prueba; checkout de Basic
  con 30 días gratis ($0 hoy, después $10/mes), pagado con la tarjeta de
  prueba.
- Webhooks firmados por el túnel: `subscription.created`, `.active`,
  `.updated` aplicados y `order.paid` ignorado; la cuenta pasa a
  `trialing` y el panel abre.
- Ajustes → Facturación y el portal de Polar (suscripción en prueba y el
  pedido).
- Cancelar al final del período: sigue con acceso, "Termina el…".
- Revocar: `canceled` al instante y vuelve "Elegí un plan", sin borrar
  datos.

Arreglado en la prueba: Polar rechaza correos de dominios que no reciben
mail y el checkout ni empezaba (ahora se reintenta sin precargar el
correo); errores de Polar legibles; con la prueba cancelada Facturación
decía "la prueba termina" en vez de "termina", y mostraba una fecha vieja
sin acceso.

Sin probar todavía: renovación real y pago rechazado (`past_due`), que en
sandbox necesitan esperar el ciclo o una tarjeta de prueba que falle.
El checkout de Polar no funciona dentro del navegador de la app de Claude
(error de React de la página de Polar); en Chrome sí.

### Créditos de IA (decidido y hecho 2026-11-16)

Para cuando el tope del plan no alcanza: el cliente carga saldo y la IA
sigue andando después del tope.

**Decisiones del dueño**

- **Solo IA.** WhatsApp no entra en créditos ni en el tope del plan: con
  Embedded Signup Meta se lo cobra directo al cliente, y contarlo acá era
  cobrárselo dos veces. Al implementar, sacar WhatsApp de
  `plan_month_spend` (queda solo IA; el tope de WhatsApp que el admin pone
  en Gastos sigue igual). Los topes de USD 5 / 15 / 40 pasan a ser de IA.
- **Monto libre desde USD 5.** El margen baja cuanto más carga:

  | Carga (USD, sin impuestos) | Margen | Crédito que recibe |
  |---|---|---|
  | 5 a 49,99 | 50 % | la mitad (USD 5 → 2,50; 20 → 10) |
  | 50 a 99,99 | 35 % | el 65 % (USD 50 → 32,50) |
  | 100 o más | 25 % | el 75 % (USD 100 → 75; 200 → 150) |

  Efecto escalón buscado: USD 50 da más que USD 49 (32,50 contra 24,50),
  así que la pantalla tiene que mostrar "con USD 50 recibís 32,50" para
  empujar al tramo siguiente.
- **Sin vencimiento, para todos los planes.** El saldo queda aunque
  cambie o se cancele el plan; se usa cuando vuelve a tener uno (sin
  plan activo la cuenta igual está bloqueada con 402).

**Números (a confirmar la comisión de Polar al implementar: hoy ~4 % +
USD 0,40, más extra por tarjeta internacional)**

| Carga | Crédito | Comisión Polar aprox. | Queda para AloStudio |
|---|---|---|---|
| 5 | 2,50 | 0,60 | 1,90 |
| 20 | 10 | 1,20 | 8,80 |
| 50 | 32,50 | 2,40 | 15,10 |
| 100 | 75 | 4,40 | 20,60 |

El crédito se descuenta al costo real de la IA (el `cost` estimado de
cada `usage_records` de tipo `ai`, con los precios del proveedor), así
que el margen de arriba es lo que queda limpio. Si cambian los precios
del proveedor, se actualiza la tabla de precios de `usage/ai.py`, no los
créditos.

**En Polar**

- Un producto de pago único "Créditos de IA" con precio libre
  (`amount_type: custom`, mínimo 500 centavos, USD) y metadata
  `{"kind": "ai_credits"}`.
- El checkout lleva `metadata.account_id` y `external_customer_id`, como
  el de los planes.
- Se acredita con el webhook `order.paid` (hoy llega y se ignora): monto
  `net_amount` (sin impuestos, que van al país del cliente). `order.refunded`
  quita lo que quede sin usar de esa carga.

**Cómo se guarda (sin descuentos por cada llamada)**

- Tabla `credit_purchases`: cuenta, `order_id` de Polar (único, para que
  un reintento no acredite dos veces), pagado, crédito, margen aplicado,
  fecha, reembolsado.
- El saldo no se descuenta en cada llamada a la IA (evita carreras y
  escrituras por mensaje): se calcula.
  - Exceso de un mes = lo que gastó en IA ese mes por encima del tope del
    plan (0 si no lo pasó).
  - Saldo = créditos comprados − suma de excesos de los meses desde la
    primera compra.
- `limit_reached(..., "ai")` corta solo si el mes pasó el tope **y** el
  saldo llegó a 0. El tope que pone el admin en Gastos sigue cortando
  igual (es su freno, aunque tenga saldo).

**Pantallas**

- Facturación: saldo de créditos, barra del mes (tope del plan + cuánto
  del saldo se lleva usado), botón "Cargar créditos" con el monto y lo
  que recibe, mostrando el tramo siguiente ("con USD 50 recibís 32,50").
- Historial de cargas (monto, crédito, fecha) y el portal de Polar para
  las facturas.
- Avisos: al llegar al tope del plan ("seguís con tus créditos") y cuando
  el saldo baja de USD 1 o se termina.

**Cómo quedó hecho**

- Producto de Polar sandbox "Créditos de IA"
  `e6359a1f-d606-4537-a9b1-06d95a48cf50` (precio libre, mínimo USD 5,
  sugerido 20, metadata `kind: ai_credits`). El webhook ya recibe
  `order.refunded`. En producción hay que crearlo de nuevo.
- Tablas `credit_purchases` (migración `9a5e3c7b2d4f`) y
  `credit_month_usages` (`a6b8d0f2c4e1`): cada mes cerrado guarda una vez
  el crédito que usó, con el tope de ese momento, así un cambio de plan
  posterior no reescribe el pasado y el saldo no relee todo el historial.
- Solo cuenta lo gastado **después** de la primera compra (lo que se pasó
  antes, con la IA ya cortada, no sale del crédito). Meses en UTC.
- Crédito redondeado a medio centavo hacia arriba, igual en backend
  (`credit_for`) y en la pantalla (`creditFor`).
- Un `order.*` que llega sin `product` queda con error para reprocesar
  en vez de perderse.
- Rutas: `GET /billing/credits` y `POST /billing/credits/checkout
  {amount}`; `GET /billing` suma `credit_balance`.
- Probado en sandbox: carga de USD 20 → USD 10 de crédito, la IA vuelve a
  andar pasada el tope y Facturación muestra saldo, tramos e historial.

**Riesgos**

- Un cliente con saldo y un agente de IA en loop puede gastar todo el
  saldo en un día: por eso el tope del admin en Gastos sigue valiendo
  como freno, y conviene un aviso cuando un día gasta más que el promedio.
- Saldo sin vencimiento es plata cobrada por servicio aún no prestado:
  revisarlo con el contador (puede tener que contarse como pasivo).

### Falta

- ~~Créditos: avisos de saldo bajo y de "seguís con créditos"; alerta si
  un día gasta mucho más que el promedio.~~ **Hecho (2026-11-23):** con el
  mismo aviso de "tope de gasto" (`meta.source`: `plan`, `credit`,
  `spike`), cada uno con su texto en el correo. Créditos: al quedar en el
  20 % o menos de la última compra y al terminarse, una vez por compra
  ("seguís con créditos" va en el aviso del 100 % del tope del plan). Día
  fuera de lo normal: el gasto de IA de hoy llega a 3 veces el promedio de
  los 14 días anteriores y a USD 1 como mínimo, una vez por día; una cuenta
  sin historial no avisa. Columnas en la misma migración `c8e0a2b4d6f1`.
- ~~Avisos al 80 % y 100 % del tope del plan~~ **Hecho (2026-11-23):** el
  mismo aviso de "tope de gasto" (así llega a quien ya tiene sus
  preferencias guardadas), una vez por nivel y mes, con el gasto de IA del
  mes contra el tope del plan; actor `AccountSubscription` (migración
  `c8e0a2b4d6f1`: `cap_notified_month` / `cap_notified_level`). El correo
  dice que al 100 % la IA sigue con créditos o se frena, y lleva a
  Facturación (también el push y el panel). Solo con `MULTITENANT=true`.
- El control del tope suma 5 a 7 consultas por llamada a la IA y por envío
  de plantilla (solo multitenant). Si pesa, guardar el gasto del mes por
  unos minutos.
- ~~Ocultar en la interfaz lo que el plan no incluye~~ **Hecho (2026-11-23):**
  `GET /billing` suma `allows` (canales de bandeja y redes permitidos, o
  `null` si son todos, y llamadas). El panel (`usePlanAllows`) muestra
  apagado lo que no entra, con "Tu plan no lo incluye" y "Ver planes":
  los canales al crear una bandeja y las redes para publicar. El botón de
  llamar no aparece sin llamadas, y en el número se pueden apagar pero no
  prender. Apagado en vez de oculto, para que se vea qué da un plan mayor.
  La API sigue rechazando igual (403).
- ~~Prueba gratis una sola vez~~ **Hecho (2026-11-23):** la suscripción
  guarda `trial_used` en cuanto Polar la manda en `trialing` (o con
  `trial_start`); desde ahí `/billing/plans` no ofrece días gratis y el
  checkout va con `allow_trial: false`. Para quien abre otra cuenta con el
  mismo correo o la misma tarjeta: prender **Prevent trial abuse** en Polar
  (Ajustes de la organización → Suscripciones), en sandbox y en producción.
- ~~Pago rechazado y renovación en sandbox~~ **Hecho (2026-11-23), con los
  avisos firmados de Polar en pruebas automáticas** (en el sandbox no se
  pueden forzar sin esperar el ciclo). Pago rechazado: Polar pone
  `past_due` y reintenta a los 2, 7, 14 y 21 días; la cuenta sigue abierta
  **7 días** desde `past_due_at` (decisión del dueño), con un aviso arriba
  de cada pantalla y "Actualizar la tarjeta" al portal (a los agentes les
  dice que avisen a un admin); después, 402 hasta que Polar cobre
  (`active`) o cancele. Migración `d9f1b3c5e7a2` (`past_due_at`).
  Renovación: `subscription.updated` con el nuevo `current_period_end`.
  Falta verlo con un cobro real: una tarjeta de prueba que falle en la
  renovación (Stripe 4000 0000 0000 0341) en un producto diario.
- ~~El registro dice solo "No se pudo crear la cuenta"~~ **Hecho (2026-11-23):**
  `lib/auth/signup-error.ts` lee qué campo rechazó la validación (correo,
  contraseña, nombres) y pasa a castellano los mensajes en inglés del alta
  (correo ya usado, correo inválido, faltan nombres).
- ~~Traducir las pantallas de registro y de Embedded Signup de WhatsApp~~
  **Hecho (2026-11-23):** `auth.signup.*` y `settingsInboxes.embedded.*`
  en los 7 idiomas. El registro pide 8 a 72 caracteres de contraseña, como
  el servidor (antes aceptaba 6).
- develop ya se trajo a la rama el 2026-11-15 (conflictos de login,
  Instagram y bandejas resueltos; la migración de facturación va después de
  `b4c5d6e7f8a1`). Al volver a traerlo, revisar que siga una sola cabeza.
