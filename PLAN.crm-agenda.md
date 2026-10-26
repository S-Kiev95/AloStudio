# PLAN — Agenda de citas (CRM en AloStudio)

Primer paso de la salida de Postiz (Fase 7 del fork): que AloStudio cubra el CRM que hoy vive en Postiz. AloStudio ya tiene casi todo:

| CRM de Postiz | En AloStudio | Qué hace falta |
|---|---|---|
| Clientes | `contacts` (nombre, email, teléfono, notas, etiquetas, atributos) | Nada: el cliente **es** el contacto. |
| Productos | `products` (mismos campos) | Nada en el modelo. |
| Citas | — | **Todo lo de este plan.** |

Rama `feat/crm-agenda`, worktree `C:\Users\Zeek\Desktop\AloStudio-agenda`. El trabajo lo hace un agente y lo revisa Claude contra este documento.

## Reglas para el agente

1. Trabajá **solo** dentro de `C:\Users\Zeek\Desktop\AloStudio-agenda`. No abras ni leas `C:\Users\Zeek\Desktop\Postiz` ni `C:\Users\Zeek\Desktop\AloStudio` (salvo usar su `.venv`, ver abajo). Todo lo que necesitás está en este plan y en el código de este worktree.
2. Copiá los patrones del dominio `app/domains/products/` (models, schemas, service, presenters, router), de `tests/integration/test_products.py`, de `app/mcp/tools/contacts.py` y de `frontend/components/products/` + `frontend/app/accounts/[accountId]/products/page.tsx`. Nada de patrones nuevos ni librerías nuevas (ni Python ni npm).
3. Prohibido: `git push`, `ssh`, tocar archivos `.env*`, `docker compose down`, borrar volúmenes o contenedores, editar migraciones de Alembic existentes, cambiar código fuera del alcance de este plan.
4. Commits chicos en la rama `feat/crm-agenda`, mensajes en español con el estilo del repo (`feat(agenda): ...`, `test(agenda): ...`). Terminá cada commit con la línea `Co-Authored-By: Antigravity <noreply@google.com>`.
5. Al terminar, completá la sección **Estado** al final de este archivo: qué se hizo, qué quedó sin hacer y la salida de los tests.

## Entorno

- Python: usá el venv del repo principal desde este worktree: `..\AloStudio\.venv\Scripts\python.exe` (con el cwd en el worktree, `import app` resuelve a este worktree).
- Postgres de tests: los contenedores de Docker ya están corriendo (`alostudio-postgres`). Tests: `..\AloStudio\.venv\Scripts\python.exe -m pytest tests/integration/test_appointments.py -q -p no:cacheprovider`.
- Lint: `..\AloStudio\.venv\Scripts\python.exe -m ruff check app tests`.
- Migración: `..\AloStudio\.venv\Scripts\python.exe -m alembic heads` (hoy hay un solo head, `b5c6d7e8f9a0`).
- Frontend: `cd frontend && npm ci` una vez; después `npm run typecheck`, `npm run lint`, `npm test`.

## 1. Backend: dominio `app/domains/appointments/`

**Modelo `Appointment`** (tabla `appointments`, `TimestampMixin`):

| Campo | Tipo | Regla |
|---|---|---|
| `id` | BigInteger PK | |
| `account_id` | FK `accounts.id`, `ondelete=CASCADE`, not null | |
| `contact_id` | FK `contacts.id`, `ondelete=CASCADE`, not null | |
| `product_id` | FK `products.id`, `ondelete=SET NULL`, null | |
| `title` | String, not null | 1–255 caracteres |
| `description` | Text, null | |
| `starts_at` | DateTime con zona, not null | |
| `ends_at` | DateTime con zona, null | si viene, `>= starts_at` (422 si no) |
| `status` | String, not null, default `scheduled` | uno de `scheduled`, `confirmed`, `cancelled`, `done` |
| `notes` | Text, null | |
| `created_by_id` | FK `users.id`, `ondelete=SET NULL`, null | usuario que la creó |

Índices: `account_id`; `contact_id`; `(account_id, starts_at)`. Borrado físico, igual que productos.

**Migración Alembic** nueva con `down_revision = "b5c6d7e8f9a0"`, con `upgrade` y `downgrade`.

**Endpoints** `/api/v1/accounts/{account_id}/appointments` (registrar el router en `app/main.py` junto a `products_router`):

- `GET ""` — filtros opcionales `from` y `to` (ISO 8601, sobre `starts_at`, `from` inclusivo y `to` exclusivo), `contact_id`, `status`, `page` (base 1, 50 por página, igual que productos). Orden `starts_at` ascendente.
- `POST ""`, `GET "/{appointment_id}"`, `PATCH "/{appointment_id}"`, `DELETE "/{appointment_id}"`.
- `contact_id` y `product_id` tienen que ser de la misma cuenta: si no, 422 con mensaje claro. Cita de otra cuenta o inexistente: 404 como en productos.
- Permisos: leer y escribir, admin **o** agente (las citas las cargan los agentes). Usar las mismas dependencias de `app/core/deps.py` que el resto.
- Presenter: todos los campos, más `contact: {id, name, email, phone_number}` y `product: {id, name, price, currency} | null`, fechas en ISO 8601.

## 2. MCP

Archivo `app/mcp/tools/appointments.py`, registrado igual que `contacts.py`, con las mismas comprobaciones de permisos:

- `list_products(enabled: bool | None = None)`.
- `list_appointments(from: str | None, to: str | None, contact_id: int | None, status: str | None)`.
- `create_appointment(contact_id, title, starts_at, ends_at=None, product_id=None, notes=None)`.
- `update_appointment_status(appointment_id, status)`.

Que las tools llamen al `service` del dominio: nada de lógica duplicada.

## 3. Frontend

- Página `frontend/app/accounts/[accountId]/agenda/page.tsx` + componentes en `frontend/components/agenda/`.
- Vista semanal (lunes a domingo, navegación semana anterior/siguiente/hoy) y vista de lista con filtro por estado. Fechas en la zona horaria del navegador.
- Crear y editar en un diálogo: contacto (buscador sobre la API de contactos), producto opcional, título, inicio, fin, notas, estado. Cambiar estado y borrar desde la cita.
- Ítem "Agenda" en `frontend/components/shell/nav.ts`, junto a "Productos".
- En el detalle de contacto (`frontend/app/accounts/[accountId]/contacts/[contactId]`), un bloque "Próximas citas" con las citas futuras del contacto y un botón para agendar.
- Textos en español, como el resto de la app. Respetar `frontend/DESIGN-SYSTEM.md` y los componentes de `frontend/components/ui/`.
- El cliente de API: seguir cómo lo hace `frontend/components/products/` (no agregar librerías de fetch).

## 4. Importador desde Postiz

`scripts/import_postiz_crm.py`: recibe `--account-id` y `--file export.json` y carga el CRM exportado de Postiz. Formato del JSON (lo genera Claude desde Postiz, el agente no lo produce):

```json
{
  "customers": [{"id": "ckx…", "name": "…", "email": "…|null", "phone": "…|null", "notes": "…|null", "tags": ["…"], "customAttributes": {}, "externalContactId": 12}],
  "products": [{"id": "ckx…", "name": "…", "sku": null, "description": null, "price": "1200.00", "currency": "UYU", "url": null, "imageUrl": null, "enabled": true}],
  "appointments": [{"id": "ckx…", "customerId": "ckx…", "productId": "ckx…|null", "title": "…", "description": null, "startDate": "2026-10-20T13:00:00.000Z", "endDate": null, "status": "SCHEDULED|CONFIRMED|CANCELLED|DONE", "notes": null}]
}
```

- Cliente → contacto: si `externalContactId` existe en la cuenta, se usa ese contacto; si no, se busca por email y después por teléfono; si no aparece, se crea. Las `notes` del cliente se agregan como `Note` del contacto y los `tags` como etiquetas.
- Idempotente: guardar el id de Postiz en `custom_attributes.postiz_crm_id` (contactos) y en un campo equivalente para productos y citas, de modo que correrlo dos veces no duplique nada.
- `--dry-run` que muestra qué crearía sin escribir.
- Test de integración del importador con un JSON chico.

## 5. Tests

- `tests/integration/test_appointments.py`: CRUD, filtros de fecha y estado, `ends_at < starts_at` → 422, contacto o producto de otra cuenta → 422, cita de otra cuenta → 404, agente puede crear, borrar el producto deja `product_id` en null.
- Tests de las tools MCP si hay un patrón de tests de tools en `tests/` (buscalo); si no, al menos uno de `create_appointment`.
- Frontend: tests vitest del componente de vista semanal (agrupado por día) siguiendo los existentes.

## Fuera de alcance

Webhooks salientes de citas, recordatorios automáticos (WhatsApp/email), sincronización con Google Calendar, borrar el CRM de Postiz. Si algo de esto parece necesario, anotalo en **Estado** y no lo hagas.

## Terminado cuando

Todos los tests nuevos y los de `tests/integration/test_products.py` pasan, `ruff` sin errores, `npm run typecheck`, `npm run lint` y `npm test` pasan, y la sección **Estado** está completa.

## Estado

### Qué se hizo

1. **Backend — Dominio `app/domains/appointments/` y migración Alembic**:
   - Modelo `Appointment` (`app/domains/appointments/models.py`) con `TimestampMixin`, FKs (`accounts.id` `CASCADE`, `contacts.id` `CASCADE`, `products.id` `SET NULL`, `users.id` `SET NULL`), índices (`account_id`, `contact_id`, `(account_id, starts_at)`), borrado físico y `external_id` opcional único por cuenta para idempotencia de importación (también agregado `external_id` nullable con constraint `(account_id, external_id)` en `products` sin alterar comportamiento existente).
   - Migración `alembic/versions/c6d7e8f9a0b1_crm_appointments.py` con `down_revision = "b5c6d7e8f9a0"`, `upgrade` y `downgrade` verificados contra Postgres.
   - Schemas (`schemas.py`), servicio (`service.py`), presenter (`presenters.py`, incluyendo `contact` y `product` embebidos y fechas ISO 8601) y router HTTP (`router.py`) registrado en `app/main.py` junto a `products_router`.
   - Endpoints `GET`, `POST`, `GET /{appointment_id}`, `PATCH /{appointment_id}` y `DELETE /{appointment_id}` bajo `/api/v1/accounts/{account_id}/appointments` accesibles para `administrator` y `agent`, con validaciones `ends_at >= starts_at` (422), pertenencia de `contact_id` y `product_id` a la misma cuenta (422) y aislamiento multi-tenant (404).

2. **MCP (`app/mcp/tools/appointments.py` + registro en `app/mcp/tools/__init__.py`)**:
   - Tools `list_products`, `list_appointments` (con alias `from` en el schema JSON), `create_appointment` y `update_appointment_status`, reutilizando las validaciones de cuenta/permisos de `contacts.py` y delegando toda la lógica a los servicios de `products` y `appointments`.

3. **Frontend (`frontend/app/accounts/[accountId]/agenda/page.tsx` y `frontend/components/agenda/*`)**:
   - Cliente de API React Query en `frontend/lib/api/appointments.ts` siguiendo `frontend/lib/api/products.ts`.
   - Vista semanal lunes a domingo en la zona horaria del navegador (`week-view.tsx` + `week-utils.ts`) con navegación semana anterior / Hoy / semana siguiente, y vista de lista con paginación y filtro por estado (`agenda-view.tsx`).
   - Diálogo de creación/edición (`appointment-dialog.tsx`) con buscador de contactos contra la API, selector de producto opcional, título, inicio, fin, estado y notas; cambio rápido de estado y borrado desde cada cita.
   - Ítem `"Agenda"` en `frontend/components/shell/nav.ts` junto a `"Productos"`.
   - Bloque `"Próximas citas"` con botón `"Agendar cita"` integrado en el detalle del contacto (`frontend/components/contacts/contact-detail-view.tsx` + `contact-appointments-card.tsx`).

4. **Importador desde Postiz (`scripts/import_postiz_crm.py` + `app/domains/appointments/importer.py`)**:
   - CLI con `--account-id`, `--file` y `--dry-run`.
   - Resolución de cliente → contacto por `externalContactId` (en la misma cuenta), email, teléfono o creación nueva; idempotencia mediante `custom_attributes.postiz_crm_id` en contactos y `(account_id, external_id)` en productos y citas (además de marcador en `Note.content` para no duplicar notas al re-ejecutar).
   - Nota sobre etiquetas de contactos: `Contact` en AloStudio aún no tiene tabla puente `contact_labels` (solo conversaciones tienen `conversation_labels`, según `app/domains/contacts/models.py` y `app/domains/labels/service.py`), por lo que el importador asegura la existencia de cada tag normalizado en la tabla `labels` de la cuenta **y** persiste la lista deduplicada en `contact.custom_attributes["tags"]`.

5. **Tests**:
   - `tests/integration/test_appointments.py`: CRUD completo, filtros `from`/`to`/`status`/`contact_id`, `ends_at < starts_at` → 422, contacto/producto de otra cuenta → 422, cita de otra cuenta → 404, creación por rol `agent`, y `ON DELETE SET NULL` al borrar el producto asociado.
   - `tests/integration/test_mcp_appointment_tools.py`: cobertura de `list_products`, `create_appointment`, `list_appointments` (con `from`/`to`/`status`), `update_appointment_status` y validación de permisos/errores.
   - `tests/integration/test_import_postiz_crm.py`: `--dry-run`, importación completa y segunda corrida idempotente sin duplicados.
   - `frontend/components/agenda/week-view.test.tsx`: agrupación lunes–domingo por día local en orden cronológico, estados/producto/fallback de contacto, acciones de edición/estado/borrado y navegación/filtros en `AgendaView`.

### Qué quedó sin hacer / fuera de alcance

- Todo lo listado explícitamente en **Fuera de alcance** (no implementado por diseño):
  - Webhooks salientes de eventos de citas (`appointment_created`, `appointment_updated`, etc.).
  - Recordatorios automáticos por WhatsApp o email antes de `starts_at`.
  - Sincronización bidireccional con Google Calendar.
  - Eliminación del CRM en Postiz / ejecución real contra el dump productivo de Postiz (queda listo `scripts/import_postiz_crm.py` para correr con `--dry-run` y luego en firme cuando Claude genere `export.json`).
- Si en el futuro se incorpora una tabla relacional `contact_labels` para contactos, convendrá migrar/vincular `contact.custom_attributes["tags"]` hacia esa relación.

### Salida de verificaciones y tests

- **Ruff (`..\AloStudio\.venv\Scripts\python.exe -m ruff check app tests scripts/import_postiz_crm.py`)**:
  ```text
  All checks passed!
  ```
- **Alembic (`..\AloStudio\.venv\Scripts\python.exe -m alembic heads`)**:
  ```text
  c6d7e8f9a0b1 (head)
  ```
- **Pytest (`..\AloStudio\.venv\Scripts\python.exe -m pytest tests/integration/test_appointments.py tests/integration/test_mcp_appointment_tools.py tests/integration/test_import_postiz_crm.py tests/integration/test_products.py -q -p no:cacheprovider`)**:
  ```text
  ..........................                                               [100%]
  26 passed in 110.95s (0:01:50)
  ```
- **Frontend Typecheck (`npm run typecheck`)**:
  ```text
  > alostudio-frontend@0.1.0 typecheck
  > tsc --noEmit
  (0 errores)
  ```
- **Frontend Lint (`npm run lint`)**:
  ```text
  ✔ No ESLint warnings or errors
  ```
- **Frontend Vitest (`npm test`)**:
  ```text
  Test Files  68 passed (68)
       Tests  284 passed (284)
    Duration  12.13s
  ```
