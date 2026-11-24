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

(Lo completa el agente.)
