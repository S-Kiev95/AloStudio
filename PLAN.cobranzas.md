# PLAN — Cobranzas: ventas al contado, fiadas o en cuotas, y saldo por cliente

Pedido del dueño (2026-11-24): que el CRM sepa si una venta se cobró **al
contado**, **fiada** o **en partes**, por una o **varias ventas**, cuánto pagó
cada cliente, cuánto debe y qué está vencido.

Rama `feat/cobranzas`, worktree `C:\Users\Zeek\Desktop\AloStudio-cobranzas`, sale
de `develop`. Lo hace Neon (Antigravity) y lo revisa Claude contra este
documento; el dueño lo ve antes de que pase a develop.

## Lo que hay (partí de acá)

- **Oportunidades** (`app/domains/crm/models.py`, `CrmOpportunity`): `title`,
  `value` (Numeric 14,2), `currency`, `contact_id`, `product_id`, `owner_id`,
  `stage_id` (las etapas tienen `kind`: `open`, `won`, `lost`), `closed_at`.
  Una oportunidad **ganada** es una venta. Servicio, rutas y presentadores en
  `app/domains/crm/` (`service.py`, `router.py`, `schemas.py`, `presenters.py`).
- Panel: `frontend/components/crm/` (pestañas en `crm-tabs.tsx`; oportunidades
  en `opportunities-view.tsx` y `opportunity-dialog.tsx`; en la ficha del
  contacto, `contact-opportunities-card.tsx`; montos con `money.ts`).
- Contactos, empresas y productos ya existen; no los dupliques.

## Qué hacer

### 1. Modelo (una migración, una sola cabeza de Alembic sobre la de develop)

- **Forma de cobro de la venta**, en la oportunidad: `payment_terms`
  (`cash` contado | `credit` fiado | `installments` en cuotas, nulo mientras no
  se ganó) y, para fiado, `due_on` (fecha en que vence lo adeudado).
- **Cuotas** `crm_installments`: oportunidad, número, `due_on`, `amount`. Se
  generan al elegir «en cuotas» (cantidad, primera fecha, frecuencia mensual o
  cada N días; el monto se reparte y la última ajusta los centavos) y se pueden
  editar a mano mientras no tengan pagos.
- **Pagos** `crm_payments`: cuenta, contacto, `amount`, `currency`, `paid_on`,
  medio (`cash`, `transfer`, `card`, `other`), nota, `created_by`. Un pago es del
  **cliente**, no de una venta.
- **Imputaciones** `crm_payment_allocations`: pago, oportunidad (y cuota si
  aplica), `amount`. Así un pago puede cubrir **varias ventas** y una venta
  recibir **varios pagos** (pagos parciales). La suma imputada nunca supera el
  pago ni lo que debe la venta.
- Lo que no se imputa queda como **saldo a favor** del cliente.
- Montos siempre en `Decimal`; **sin convertir monedas**: los saldos se muestran
  por moneda.
- Al registrar una venta **al contado**, ofrecer crear el pago por el total en el
  mismo paso.

### 2. Reglas de negocio (en el servicio, con pruebas)

- **Debe de una venta** = valor − imputado. **Saldo del cliente** por moneda =
  suma de lo que deben sus ventas ganadas − saldo a favor.
- **Vencido:** cuota con `due_on` pasado y sin cubrir, o venta fiada con `due_on`
  pasado y sin cubrir. Días de atraso.
- **Imputación automática** al registrar un pago: a lo más viejo primero (la
  cuota o venta que vence antes), con opción de elegir a mano a qué ventas va.
- Si una venta deja de estar ganada o cambia el valor con pagos imputados, no se
  borra nada en silencio: se avisa y se pide decidir (dejar el pago como saldo a
  favor).
- Borrar un pago: solo administradores; registrar y editar: cualquier miembro.
  Queda `created_by`.

### 3. API

Rutas bajo `/api/v1/accounts/{id}/crm/`: forma de cobro y cuotas de una
oportunidad; alta, edición, baja y listado de pagos (con imputaciones); cuenta
corriente de un contacto (ventas, pagos, saldo por moneda, vencido); **cuentas
por cobrar** (contactos con deuda, total, vencido, días de atraso, filtros por
vencido / por vencer / responsable, orden, paginado) y un resumen (total a
cobrar, vencido, cobrado en el mes).

### 4. Panel

- **Oportunidad ganada:** sección «Cobro» con la forma de cobro, las cuotas, lo
  pagado y lo que falta, y «Registrar pago».
- **Ficha del contacto:** tarjeta «Cuenta corriente» con el saldo (por moneda),
  lo vencido, sus ventas con lo que debe cada una y el historial de pagos.
- **Pestaña nueva del CRM «Cobranzas»:** cuentas por cobrar con filtros,
  totales arriba (a cobrar, vencido, cobrado este mes) y acceso a cada cliente.
- **Diálogo «Registrar pago»:** monto, fecha, medio, nota, y la imputación
  (automática a lo más viejo, o elegir ventas y montos), mostrando cómo queda el
  saldo antes de guardar.
- **Recordatorio:** desde la fila de un deudor, botón que abre su conversación
  de WhatsApp con un texto de recordatorio ya escrito (monto y vencimiento) para
  que el agente lo revise y lo mande. **No se manda nada solo.**
- Montos con `money.ts`; vencidos en el color de peligro del tema.
- Textos en los **7 idiomas** (`frontend/lib/i18n/messages/*`, el español es la
  fuente).

## Reglas

- Trabajá **solo** en `C:\Users\Zeek\Desktop\AloStudio-cobranzas`. Podés tocar el
  backend y el panel del CRM (`app/domains/crm/`, `frontend/components/crm/`, la
  ficha del contacto y lo necesario para conectarlo). **No toques**
  `app/mcp/tools/`, `app/domains/agent/`, `app/domains/ai_agent/` ni
  `components/whatsapp/` (son de otro agente); anotá en **Estado** qué
  herramientas MCP convendría sumar después.
- Pruebas contra la base de pruebas local (Postgres `127.0.0.1:5433`
  `alostudio_test`, Redis `127.0.0.1:6380`) con estas variables:
  `DATABASE_URL=postgresql+asyncpg://alostudio:alostudio@127.0.0.1:5433/alostudio_test`,
  `DATABASE_URL_SYNC=postgresql+psycopg://alostudio:alostudio@127.0.0.1:5433/alostudio_test`,
  `REDIS_URL=redis://127.0.0.1:6380/15`, `ARQ_REDIS_URL=redis://127.0.0.1:6380/14`.
  Python: `C:\Users\Zeek\Desktop\AloStudio\.venv\Scripts\python.exe`. Si Docker
  no responde, abrí Docker Desktop y esperá.
- Nada de `git push`, `ssh`, `.env*`, otras bases ni borrar contenedores.
- Sin librerías nuevas (ni npm ni Python).
- Sin modificadores de opacidad sobre colores del tema (`bg-primary/60`…).
- Commits chicos en español (`feat(crm): ...`), terminados en
  `Co-Authored-By: Antigravity <noreply@google.com>`.
- **Pruebas:** backend (forma de cobro, cuotas y redondeo, pagos parciales, un
  pago a varias ventas, imputación automática, saldo a favor, vencidos, saldos
  por moneda, permisos, cambio de una venta con pagos) y panel (registrar pago,
  cuenta corriente, cuentas por cobrar, con msw).
- Revisalo en el navegador con el backend local y el usuario de demostración, y
  dejá capturas en `docs/cobranzas/`.
- Al final completá **Estado** con la salida real de `ruff check`,
  `ruff format --check`, las pruebas del CRM, `alembic heads`, y en `frontend/`
  `npm run typecheck`, `npm run lint` y `npm test`.

## Estado

**Completado** en rama `feat/cobranzas` (`C:\Users\Zeek\Desktop\AloStudio-cobranzas`), sin dependencias nuevas ni cambios fuera del alcance permitido.

### Qué se implementó

1. **Modelo y migración (`c0b2a4e6f8a1` sobre `f5b7d9e1a3c5`, cabeza única):**
   - `crm_opportunities`: `payment_terms` (`cash` | `credit` | `installments`, nulo mientras no está ganada) y `due_on`.
   - `crm_installments`: cuotas numeradas por oportunidad con `due_on` y `amount` (`Numeric(14,2)`), generación mensual o cada N días ajustando centavos en la última cuota, editables mientras no tengan pagos imputados.
   - `crm_payments` y `crm_payment_allocations`: pagos a nivel contacto (`amount`, `currency`, `paid_on`, `method`, `note`, `created_by_id`) e imputaciones a una o varias ventas/cuotas. Lo no imputado queda como saldo a favor. Todo cálculo usa `Decimal` y nunca convierte monedas.
2. **Servicio y API (`/api/v1/accounts/{account_id}/crm/`):**
   - `GET|PUT /opportunities/{id}/billing` (incluye opción `register_payment` para ventas al contado en el mismo paso) y `PATCH /opportunities/{id}/installments/{inst_id}`.
   - `GET|POST /payments`, `POST /payments/preview`, `GET|PATCH|DELETE /payments/{id}` (`DELETE` solo administradores; alta y edición cualquier miembro conservando `created_by`).
   - Imputación automática a lo más viejo primero (por vencimiento de cuota o venta) u opción manual por venta.
   - Protección HTTP `409` (`opportunity_has_payments`) si una venta con pagos imputados deja de estar ganada, cambia valor/moneda/contacto o se intenta eliminar, exigiendo confirmación explícita (`release_allocations`) para dejar esos pagos como saldo a favor sin borrar nada en silencio.
   - `GET /contacts/{id}/statement`, `GET /receivables` (filtros `status=overdue|upcoming`, `owner_id`, `q`, orden y paginado) y `GET /receivables/summary`.
3. **Panel y 7 idiomas (`es`, `en`, `pt`, `fr`, `de`, `ja`, `ko`):**
   - Nueva pestaña **Cobranzas** (`/accounts/{id}/collections`) con totales por moneda arriba (a cobrar, vencido en color de peligro, cobrado este mes), tabla filtrable de deudores, botón «Registrar pago» y botón «Recordar por WhatsApp».
   - Sección **Cobro** dentro de `OpportunityDialog` para oportunidades ganadas (forma de cobro, contado con pago en un paso, fiado con vencimiento, generador/editor de cuotas, historial y botón «Registrar pago»).
   - Tarjeta **Cuenta corriente** en la ficha del contacto (saldos por moneda, vencido, ventas con deuda e historial de pagos con alta/edición y baja solo admin).
   - Diálogo **Registrar pago** con previsualización en vivo de cómo queda el saldo antes de guardar (imputación automática o manual).
   - **Recordatorio por WhatsApp:** abre `/accounts/{id}/conversations/{display_id}?draft=...` con el texto precargado (monto y vencimiento) en `MessageComposer` para que el agente lo revise y envíe; nunca envía nada solo.
   - Capturas verificadas con backend local y usuario `demo@example.com` (cero errores de consola) en `docs/cobranzas/`:
     - `docs/cobranzas/01-cobranzas-lista.png`
     - `docs/cobranzas/02-registrar-pago-dialog.png`
     - `docs/cobranzas/03-cuenta-corriente-contacto.png`
     - `docs/cobranzas/04-recordatorio-whatsapp-borrador.png`
     - `docs/cobranzas/05-oportunidad-ganada-cobro.png`

### Herramientas MCP sugeridas para sumar después

*(No se tocó `app/mcp/tools/`, `app/domains/agent/`, `app/domains/ai_agent/` ni `components/whatsapp/`.)*

- `crm_get_contact_statement(contact_id)`: consultar saldo por moneda, ventas impagas, cuotas vencidas e historial de pagos de un cliente.
- `crm_list_receivables(status, owner_id, q, sort, page)` y `crm_receivables_summary()`: listar deudores, montos vencidos y resumen del mes.
- `crm_set_opportunity_billing(opportunity_id, payment_terms, due_on, generate|installments, register_payment)`: configurar forma de cobro y cuotas de una venta ganada.
- `crm_preview_payment(...)` y `crm_create_payment(...)`: simular imputación (automática o manual) y registrar un pago (con confirmación humana en el agente antes de mutar).
- `crm_draft_payment_reminder(contact_id)`: devolver el texto sugerido de recordatorio con monto y vencimiento para revisión del agente (sin envío automático).

### Verificaciones reales

#### `ruff check`
```text
$ python -m ruff check app/domains/crm/ alembic/versions/c0b2a4e6f8a1_crm_billing_and_payments.py tests/integration/test_crm_billing.py
All checks passed!
```

#### `ruff format --check`
```text
$ python -m ruff format --check app/domains/crm/billing.py app/domains/crm/models.py app/domains/crm/presenters.py app/domains/crm/router.py app/domains/crm/schemas.py app/domains/crm/service.py alembic/versions/c0b2a4e6f8a1_crm_billing_and_payments.py tests/integration/test_crm_billing.py
8 files already formatted
```

#### `alembic heads`
```text
$ python -m alembic heads
c0b2a4e6f8a1 (head)
```

#### Pruebas del CRM (`pytest`)
```text
$ python -m pytest tests/integration/test_crm_billing.py tests/integration/test_crm_pipeline.py -v
collected 19 items
tests/integration/test_crm_billing.py::test_payment_terms_cash_one_step_and_open_opp_rejected PASSED [  5%]
tests/integration/test_crm_billing.py::test_installments_generation_rounding_and_manual_edits PASSED [ 10%]
tests/integration/test_crm_billing.py::test_partial_payments_multi_sale_auto_allocation_and_credit_balance PASSED [ 15%]
tests/integration/test_crm_billing.py::test_manual_allocations_validation_and_multi_currency_isolation PASSED [ 21%]
tests/integration/test_crm_billing.py::test_overdue_receivables_filters_sorting_summary_and_whatsapp_link PASSED [ 26%]
tests/integration/test_crm_billing.py::test_payment_permissions_and_created_by PASSED [ 31%]
tests/integration/test_crm_billing.py::test_changing_or_reopening_paid_sale_requires_explicit_decision PASSED [ 36%]
tests/integration/test_crm_pipeline.py::test_an_account_starts_with_the_default_pipeline PASSED [ 42%]
tests/integration/test_crm_pipeline.py::test_opportunity_lifecycle PASSED [ 47%]
tests/integration/test_crm_pipeline.py::test_title_is_required_and_references_stay_in_the_account PASSED [ 52%]
tests/integration/test_crm_pipeline.py::test_agents_sell_but_only_admins_shape_the_pipeline PASSED [ 57%]
tests/integration/test_crm_pipeline.py::test_editing_stages PASSED       [ 63%]
tests/integration/test_crm_pipeline.py::test_new_pipeline_and_default_cannot_be_deleted PASSED [ 68%]
tests/integration/test_crm_pipeline.py::test_activity_lifecycle_and_filters PASSED [ 73%]
tests/integration/test_crm_pipeline.py::test_due_activities_notify_their_owner_once PASSED [ 78%]
tests/integration/test_crm_pipeline.py::test_company_with_its_people_and_their_opportunities PASSED [ 84%]
tests/integration/test_crm_pipeline.py::test_company_needs_a_name_and_stays_in_its_account PASSED [ 89%]
tests/integration/test_crm_pipeline.py::test_first_conversation_sets_origin_and_ad_upgrades_it PASSED [ 94%]
tests/integration/test_crm_pipeline.py::test_origin_set_by_hand_shown_and_filterable PASSED [100%]
============================= 19 passed in 15.02s =============================
```

#### `frontend/` — `npm run typecheck`, `npm run lint` y `npm test`
```text
$ npm run typecheck
> alostudio-frontend@0.1.0 typecheck
> tsc --noEmit
(exit code 0)

$ npm run lint
> alostudio-frontend@0.1.0 lint
> next lint
✔ No ESLint warnings or errors

$ npm test
> alostudio-frontend@0.1.0 test
> vitest run
 Test Files  135 passed (135)
      Tests  622 passed (622)
   Duration  77.68s
```
