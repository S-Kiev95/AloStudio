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

Estado: los tres corregidos en esta rama, con casos en
`tests/integration/test_tenant_isolation.py`.

Ya validados: los integrantes de equipos (401 "Invalid User IDs", como
Chatwoot), `contact_id`, `inbox_id` y `source_id` al crear una
conversación o un contact inbox, la unión de contactos, participantes,
`assignment_policy_id`, `conversation_ids` de las macros, `product_ids` de
Instagram, `channel_id` de los plugs y `handoff_assignee_id`.

Queda para revisar: `campaign_id` en mensajes (solo se guarda como marca,
riesgo bajo) y los ids dentro de JSON (condiciones y acciones de
automatizaciones y macros, filtros guardados, CRM).

### 1.c Lo que falta auditar

- **Worker (ARQ):** cada tarea recibe ids. Ver que no mezcle cuentas al
  cargar relaciones (por ejemplo el canal de otra cuenta).
- **Webhooks entrantes** (Meta, email, Telegram, SMS): el ruteo por
  `phone_number_id`, `page_id`, `instagram_id` y dirección de correo tiene
  que caer en una sola bandeja. Qué pasa si dos cuentas conectan el mismo
  número o página.
- **MCP:** revisado el 2026-11-10. El token MCP está atado a una cuenta
  (`mcp_tokens.account_id`) y cada herramienta lee `ctx.account`; las
  lecturas por id comparan `account_id`, y el canal de Instagram sale de un
  post o comentario ya buscado dentro de la cuenta. Sin hallazgos. Falta el
  agente de chat, si corre fuera del MCP.
- **Tiempo real:** las suscripciones por `pubsub_token` solo reciben eventos
  de su usuario o cuenta.
- **Públicas:** widget del sitio, centro de ayuda, CSAT, OAuth. Que un token
  de una cuenta no dé acceso a otra.
- **Búsqueda y vectores:** filtros de cuenta en la búsqueda full-text, en
  `article_embeddings` y en los vectores de autorespuestas.
- **Reportes y exportaciones:** filtran por cuenta.

### 1.d Tests

Un archivo de integración `tests/integration/test_tenant_isolation.py` con
dos cuentas: la cuenta B intenta leer, cambiar y referenciar datos de la
cuenta A por cada camino encontrado. Cada hallazgo suma su caso.

## Pasos siguientes (necesitan decisiones del dueño)

2. **Alta de clientes:** registro, creación de cuenta y conexión de canales
   con Embedded Signup de WhatsApp y los OAuth de Meta.
3. **Facturación:** proveedor de pagos, moneda, planes y límites. El código
   del webhook de pagos no puede tirar excepciones.
4. **Límites de uso:** cuotas por cuenta en el worker y la API.
5. **Operación:** panel interno de cuentas, métricas, borrado y exportación
   de datos de una cuenta.
6. **Enterprise:** script de despliegue en servidor dedicado, como CTC hoy.
7. **Legal:** términos, privacidad y acuerdo de tratamiento de datos.
