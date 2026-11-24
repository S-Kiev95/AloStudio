# PLAN — Plantillas y firmas de correo con lienzo y con IA

Pedido del dueño (2026-11-24): en Correo, poder **diseñar plantillas** a nivel de
**organización** y de **usuario**, con **firmas**, en un **lienzo** donde se
diseñe de forma gráfica, pegando un HTML propio, o pidiéndoselo a la IA (con un
texto o con una imagen de ejemplo).

Rama `feat/plantillas-correo`, worktree `C:\Users\Zeek\Desktop\AloStudio-correo`,
sale de `develop`. Lo hace un agente (Neon, en Antigravity) y lo revisa Claude
contra este documento.

## Lo que ya existe (partí de acá, no lo rehagas)

- **Membretes de la organización:** tabla `email_templates` (`account_id`,
  `name`, `template_html` con `{{contenido}}` obligatorio, `template_design`
  JSONB), `app/domains/email/models.py`, `templates_service.py`,
  `templates_router.py` (`/api/v1/accounts/{id}/email_templates`, solo
  administradores) y `test_send.py` (mandar una prueba).
- **Cómo sale un correo:** `app/domains/email/template.py` arma el HTML con
  estilos en línea (Gmail y Outlook tiran los `<style>`); `mailer.py` resuelve el
  membrete de la bandeja (`Inbox.email_template_id`) y pega la firma del agente.
- **Firma del agente:** `users.message_signature`, texto plano que se escapa
  (ver la explicación al principio de `template.py`).
- **Panel:** `frontend/components/settings/email-templates/` con tres modos
  (`blocks` — `block-editor.tsx` —, `design` y `code`), vista previa y prueba de
  envío; `components/settings/inboxes/email-template-panel.tsx` elige el
  membrete de cada bandeja.
- **IA disponible:** `app/core/llm.py` (OpenAI, si la instalación tiene clave y
  respetando el tope de gasto de la cuenta, `ai_usage`) y `app/core/local_llm.py`
  (modo Free: Groq/NVIDIA o local). Para imágenes, `app/core/media_ai.py`
  (`describe`, NVIDIA y Groq). Mirá cómo `app/domains/help_assistant/` elige
  entre Free y Fast.

## Reglas para el agente

- Trabajá **solo** en `C:\Users\Zeek\Desktop\AloStudio-correo`. No leas ni toques
  otros worktrees.
- Podés tocar **backend y frontend del dominio de correo** (`app/domains/email/`,
  `app/domains/users/` solo para la firma, `frontend/components/settings/email-templates/`,
  lo de perfil y lo que haga falta para conectarlo). **No toques**
  `app/mcp/tools/`, `app/domains/agent/`, `app/domains/ai_agent/` ni
  `components/whatsapp/` (son de otro agente).
- **Migraciones:** una sola cabeza de Alembic encadenada sobre la última de
  `develop` (`alembic heads` tiene que dar una). Con `upgrade` y `downgrade`.
- Pruebas contra la base de pruebas local (Postgres `127.0.0.1:5433`
  `alostudio_test`, Redis `127.0.0.1:6380`), con estas variables:
  `DATABASE_URL=postgresql+asyncpg://alostudio:alostudio@127.0.0.1:5433/alostudio_test`,
  `DATABASE_URL_SYNC=postgresql+psycopg://alostudio:alostudio@127.0.0.1:5433/alostudio_test`,
  `REDIS_URL=redis://127.0.0.1:6380/15`, `ARQ_REDIS_URL=redis://127.0.0.1:6380/14`.
  El Python es `C:\Users\Zeek\Desktop\AloStudio\.venv\Scripts\python.exe`. Si
  Docker no responde, abrí Docker Desktop y esperá.
- **Nada de** `git push`, `ssh`, `.env*`, bases que no sean la de pruebas, ni
  borrar contenedores. Nada fuera del worktree.
- **Sin librerías nuevas de npm.** En Python solo si es imprescindible para
  sanear HTML (`nh3`, que es chica y segura); anotalo en **Estado**.
- Sin modificadores de opacidad sobre colores del tema (`bg-primary/60`…).
- Textos del panel en los **7 idiomas** (`frontend/lib/i18n/messages/*`, el
  español es la fuente) y del backend en `app/core/i18n/` si corresponde.
- Commits chicos en español con el estilo del repo (`feat(correo): ...`), cada
  uno con todo lo que dice su mensaje, terminados en
  `Co-Authored-By: Antigravity <noreply@google.com>`.
- Al final completá **Estado** con la salida real de: `ruff check` y
  `ruff format --check` del backend tocado, las pruebas de `tests/` del correo,
  y en `frontend/` `npm run typecheck`, `npm run lint` y `npm test`.

## 1. Alcance: organización y usuario

- **Plantillas de la organización** (las de hoy): las crean los administradores
  y se asignan a bandejas. Siguen igual.
- **Plantillas personales:** cada usuario puede tener las suyas (solo las ve y
  edita él). Agregá `user_id` opcional a `email_templates` (nulo = de la
  organización); el nombre es único por cuenta y dueño. Rutas para que cualquier
  miembro maneje **las suyas**; las de la organización siguen solo para
  administradores.
- **Cuál se usa al responder:** la personal que el usuario marque como «la mía
  por defecto» si tiene una; si no, la de la bandeja; si no, la de siempre.
  Documentá la regla en `mailer.py`.

## 2. Firmas

- **Firma de la organización** (una por cuenta, la edita un administrador) y
  **firma del usuario**, las dos con diseño (HTML) además de texto.
- Se insertan con variables en la plantilla: `{{firma}}` (la del usuario o, si
  no tiene, la de la organización) y `{{firma_organizacion}}`. Sin la variable,
  la firma va al final, como hoy.
- La firma de texto actual (`message_signature`) sigue funcionando: si no hay
  firma con diseño, se usa esa, escapada como hoy.
- Variables de usuario disponibles en firmas: nombre, cargo, correo, teléfono,
  foto (las que ya tenga el perfil; no inventes campos nuevos salvo cargo y
  teléfono si no existen, en la misma migración).

## 3. El lienzo

Un editor que sirve para plantillas y firmas, reemplazando o ampliando
`block-editor.tsx` (sin librerías nuevas):

- **Gráfico:** bloques arrastrables (encabezado con logo, texto, imagen, botón,
  separador, columnas de 2, redes sociales, espacio, firma, `{{contenido}}`),
  reordenar con arrastrar y soltar (HTML5 drag and drop o punteros), panel de
  propiedades del bloque elegido (colores, alineación, tamaño, márgenes,
  enlace). Deshacer/rehacer.
- **HTML:** pegar o escribir HTML propio con vista previa al lado, en un
  `iframe` con `sandbox` (sin scripts). Importar un `.html`.
- **Vista previa:** escritorio y celular, modo claro y oscuro del cliente de
  correo, con datos de ejemplo.
- Lo que guarda el lienzo va en `template_design` para reabrirlo; el HTML final
  sale con **estilos en línea y tablas** (lo que respetan Gmail y Outlook).

## 4. Pedírselo a la IA

- Botón «Diseñar con IA» en el lienzo: un texto («membrete azul con el logo a la
  izquierda y redes abajo») y/o **una imagen de ejemplo** (captura de un correo
  que les guste).
- Ruta nueva en el backend, por ejemplo
  `POST /api/v1/accounts/{id}/email_templates/generate` con `{prompt, image?,
  kind: "template"|"signature"}` → `{html, notes}`.
- La imagen se lee con `media_ai.describe` (NVIDIA y Groq) y su descripción
  entra al pedido. El HTML lo escribe el modelo de texto: OpenAI si la cuenta
  usa Fast y tiene clave (con `ai_usage` y el tope de gasto), si no el modo Free
  (`local_llm`). Si ninguno responde: «Servicios de AI temporalmente fuera,
  intenta mañana».
- Lo que devuelve la IA **se sanea** igual que el HTML que pega una persona y
  tiene que incluir `{{contenido}}` (plantillas) o no (firmas); si falta, se
  agrega. Se abre en el lienzo como HTML editable, nunca se guarda solo.
- Dejá la función del servicio separada de la ruta, para que después el Agente
  (de otro agente) la use como herramienta. Anotalo en **Estado**.

## 5. Seguridad del HTML

- **Saneado en el servidor** al guardar y al generar: sin `<script>`,
  `<iframe>`, `<object>`, `<form>`, manejadores `on*`, `javascript:` ni
  `data:` salvo imágenes. Imágenes por `https` o subidas a la biblioteca de
  medios.
- La vista previa del panel siempre en `iframe sandbox`.
- Pruebas que demuestren que un HTML malicioso sale limpio.

## 6. Pruebas

- Backend: plantillas personales (crear, listar solo las propias, no ver las de
  otro, la organización solo administradores), firmas (de organización y de
  usuario, variables, caída al texto viejo), qué plantilla se usa al responder,
  saneado, y la ruta de IA con el modelo simulado (respx), incluida la caída a
  `ai_down`.
- Frontend: el lienzo (agregar, mover, editar y borrar bloques; pasar a HTML y
  volver), la vista previa en `iframe sandbox`, y el diálogo de IA con msw.

## 7. Cómo lo vas a probar a mano

- Levantá el backend y el panel locales (`npm run dev` en `frontend/`), entrá
  con el usuario de demostración y armá una plantilla personal, una firma con
  diseño y una plantilla generada con IA (si no hay claves locales, con el modelo
  simulado). Dejá capturas en `docs/plantillas-correo/`.

## Estado

Completado en la rama `feat/plantillas-correo` (worktree `C:\Users\Zeek\Desktop\AloStudio-correo`).

### Resumen de implementación

1. **Alcance organización y usuario:**
   - Migración única de Alembic `alembic/versions/f5b7d9e1a3c5_email_personal_templates_and_signatures.py` encadenada sobre `e4a6c8b0d2f4` (`upgrade` y `downgrade` probados).
   - `email_templates.user_id` (nullable FK `users.id`) e `is_default` con índices únicos parciales por cuenta/dueño y a lo sumo una plantilla personal por defecto por usuario y cuenta.
   - Rutas de organización solo para administradores (`/api/v1/accounts/{id}/email_templates*`) y rutas personales para cualquier miembro (`/api/v1/accounts/{id}/email_templates/personal*`).
   - Precedencia al enviar documentada en `app/domains/email/mailer.py` y `app/domains/email/templates_service.py`: plantilla personal por defecto del remitente → plantilla de la bandeja (`channel.email_template_id`) → HTML propio de la casilla → layout integrado.

2. **Firmas con diseño y variables:**
   - Tabla `email_signatures` (una firma por organización `user_id IS NULL` editable por administradores y una personal por `(account_id, user_id)`), rutas `/api/v1/accounts/{id}/email_signatures/{organization|personal}` y servicio `app/domains/email/signatures_service.py`.
   - Variables de plantilla `{{firma}}` (usuario o, si no tiene, organización) y `{{firma_organizacion}}`; si no se incluye variable de firma, se agrega al final. Caída automática a `users.message_signature` / `channel_email.signature` escapados como texto plano cuando no hay firma con diseño.
   - Variables de perfil en firmas: `{{nombre}}`, `{{cargo}}` (columna `users.job_title` agregada en la misma migración y expuesta en `PUT /api/v1/profile` y `ProfileView`), `{{correo}}`, `{{telefono}}` (`custom_attributes.phone_number`) y `{{foto}}` / `{{foto_url}}`.

3. **El lienzo (sin librerías nuevas de npm):**
   - `frontend/lib/inboxes/email-blocks.ts` ampliado con bloques de encabezado con logo (`header`), texto, imagen (subida directa + biblioteca de medios), botón, separador, columnas de 2 (`columns`), redes sociales (`social`), espacio, firma y `{{contenido}}`, más modo `signature` compacto. Salida 100% con tablas y estilos en línea.
   - `frontend/components/settings/email-templates/block-editor.tsx`: arrastrar y soltar (HTML5 drag & drop desde paleta y reordenamiento + flechas accesibles), inspector de propiedades por bloque y deshacer/rehacer (botones y `Ctrl+Z` / `Ctrl+Y`).
   - Modo HTML con vista previa al lado, importación de `.html` y chips de variables.
   - `frontend/components/settings/email-templates/email-preview-frame.tsx`: vista previa siempre dentro de `<iframe sandbox="" srcDoc={...}>`, con selector Escritorio/Celular y Claro/Oscuro (también aplicado a `EmailDesigner` en bandejas).
   - Textos en los 7 idiomas (`es`, `en`, `pt`, `fr`, `de`, `ja`, `ko`).

4. **Diseño con IA (reusable por el Agente):**
   - Servicio desacoplado de la ruta HTTP: `app/domains/email/ai_design.py` → **`generate_email_design(session, *, account, prompt, kind, image)`** (lista para envolver como herramienta MCP del Agente).
   - Ruta `POST /api/v1/accounts/{id}/email_templates/generate` (`{prompt, image?, kind: "template"|"signature"}` → `{html, notes, mode, seen}`).
   - Descripción de imágenes de ejemplo vía `app.core.media_ai.describe` (NVIDIA / Groq), generación con OpenAI cuando la cuenta tiene Fast + clave (respetando `ai_usage` y `ai_budget_reached`), si no `local_llm` (Free), y caída controlada `email_ai.ai_down` (HTTP 503) con «Servicios de AI temporalmente fuera, intenta mañana».
   - La salida se sanea siempre con `sanitize_email_html`, garantiza `{{contenido}}` en plantillas y lo elimina en firmas; en el panel se abre en HTML editable y nunca se guarda sola.

5. **Seguridad y nueva dependencia Python:**
   - Dependencia Python agregada en `pyproject.toml`: **`nh3>=0.3`** (instalada `nh3==0.3.8` en `.venv`), usada en `app/domains/email/sanitize.py::sanitize_email_html` al guardar plantillas, firmas, HTML de bandeja y al generar con IA.
   - Bloquea `<script>`, `<iframe>`, `<object>`, `<embed>`, `<form>`, `<style>`, `<svg>`, atributos `on*`, URLs `javascript:` / `vbscript:` / `data:` (salvo imágenes raster `data:image/(png|jpeg|gif|webp);base64,...` en `<img src>`) y CSS peligroso (`expression()`, `url(javascript:...)`, `position:fixed`).

### Salida real de verificaciones

#### Alembic (`alembic heads`, `upgrade head`, `downgrade -1`, `upgrade head`)
```text
f5b7d9e1a3c5 (head)
INFO  [alembic.runtime.migration] Running upgrade e4a6c8b0d2f4 -> f5b7d9e1a3c5, email: personal templates, rich org/user signatures, and user job title
INFO  [alembic.runtime.migration] Running downgrade f5b7d9e1a3c5 -> e4a6c8b0d2f4, email: personal templates, rich org/user signatures, and user job title
INFO  [alembic.runtime.migration] Running upgrade e4a6c8b0d2f4 -> f5b7d9e1a3c5, email: personal templates, rich org/user signatures, and user job title
```

#### Backend lint y formato (`ruff check` y `ruff format --check` sobre los 21 archivos tocados)
```text
=== RUFF CHECK ===
All checks passed!
=== RUFF FORMAT CHECK ===
21 files already formatted
```

#### Pruebas backend (`pytest` correo + perfil contra `alostudio_test`)
```text
........................................................................ [ 39%]
........................................................................ [ 79%]
.....................................                                    [100%]
181 passed in 61.82s (0:01:01)
```
Archivos ejecutados: `tests/unit/test_email_sanitize.py`, `tests/unit/test_email_template.py`, `tests/unit/test_email_ai_design.py`, `tests/unit/test_email_attachments.py`, `tests/unit/test_email_poll_isolation.py`, `tests/unit/test_email_probe.py`, `tests/unit/test_email_threading.py`, `tests/integration/test_email_templates.py`, `tests/integration/test_email_branding.py`, `tests/integration/test_email_outbound.py`, `tests/integration/test_email_inbound.py`, `tests/integration/test_email_assets.py`, `tests/integration/test_email_poll_task.py`, `tests/integration/test_inbox_builder_email.py`, `tests/integration/test_profile_router.py`.

#### Frontend (`npm run typecheck`, `npm run lint`, `npm test`)
```text
> alostudio-frontend@0.1.0 typecheck
> tsc --noEmit

> alostudio-frontend@0.1.0 lint
> next lint
✔ No ESLint warnings or errors

> alostudio-frontend@0.1.0 test
> vitest run
 Test Files  128 passed (128)
      Tests  583 passed (583)
   Duration  87.49s
```

### Prueba manual y capturas (`docs/plantillas-correo/`)

Levantados backend local (`uvicorn` sobre `alostudio_test` con proveedor LLM simulado local) y panel (`npm run dev`), entrando con usuario demo (`demo@alostudio.example.com`):

- `docs/plantillas-correo/01-plantilla-personal-lienzo.png` — Plantilla personal creada en el lienzo de bloques, marcada como predeterminada y con vista previa en vivo (`iframe sandbox`).
- `docs/plantillas-correo/02-vista-previa-celular-oscuro.png` — Vista previa en modo Celular (`375px`) y tema Oscuro del cliente de correo.
- `docs/plantillas-correo/03-firma-con-diseno.png` — Pestaña Firmas (firma personal y firma de la organización con variables de perfil y guardado confirmado).
- `docs/plantillas-correo/04-disenar-con-ia.png` — Resultado de «Diseñar con IA» abierto en HTML editable con vista previa en `iframe sandbox` y notas de la IA sin guardado automático.

