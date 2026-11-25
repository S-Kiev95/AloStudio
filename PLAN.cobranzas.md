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

(Lo completa el agente.)
