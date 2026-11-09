# Botón Enviar fuera del cuadro e íconos de Inicio más grandes

Pedido del dueño (2026-11-09), con capturas de CTC.

## 1. Bandeja: botón Enviar fuera del cuadro de texto

Hoy el botón redondo con el avión de papel está DENTRO del cuadro de texto
(`absolute right-2 top-1/2 -translate-y-1/2 rounded-full`), y el cuadro crece
con el texto. Al crecer se ve mal (botón flotando en el medio, scroll al lado).

El dueño quiere:
- El cuadro de texto ocupa todo el ancho, sin botón adentro (sacar el `pr-12`).
- El botón Enviar va FUERA del cuadro, abajo a la derecha, en la misma fila
  que los botones "Nota privada", "Respuestas rápidas" y el clip de adjuntar
  (esos quedan a la izquierda; Enviar a la derecha de esa fila).
- Se mantiene redondo (`rounded-full`), con solo el ícono del avión de papel,
  mismo color, `aria-label="Enviar"` y `title="Enviar"`, y el mismo
  comportamiento (deshabilitado sin texto ni adjuntos, estilo de nota privada
  cuando `isPrivate`).
- El cuadro sigue creciendo solo hasta ~6 líneas (efecto con
  `MAX_TEXTAREA_HEIGHT_PX`) y solo muestra scroll si el texto supera ese alto.
  Revisar que con Shift+Enter (líneas vacías) no aparezca scroll antes de tiempo.
- Con el botón fuera, el cuadro puede volver al padding normal del Textarea
  (quitar `py-[13px]`) si queda mejor; que una línea se vea prolija.

Archivos:
- `frontend/components/conversations/message-composer.tsx`
- `frontend/components/conversations/email-composer.tsx`: mismo criterio,
  botón Enviar fuera del cuadro, abajo a la derecha.

## 2. Inicio: íconos de "Ahora mismo" más grandes

En `frontend/components/overview/account-overview.tsx`, las tarjetas de
"Ahora mismo" (Abiertas, Sin atender, Sin asignar, Pendientes) tienen el ícono
en `h-5 w-5` junto a un número `text-2xl`. Se ven chicos: agrandarlos para que
acompañen al número (por ejemplo `h-7 w-7` u `h-8 w-8`, lo que quede mejor),
alineados verticalmente con el bloque número + etiqueta. Mismo estilo de línea
(`neon-nav`), sin cambiar colores. Solo esas tarjetas, no la lista de acciones.

## Reglas

- Respetar `frontend/DESIGN-SYSTEM.md`. No usar clases de opacidad tipo
  `bg-x/NN` sobre colores del tema (no generan CSS).
- No tocar backend ni otras pantallas.
- Actualizar los tests que fijen la posición o clases del botón si hace falta.
- Correr `npm run typecheck`, `npm run lint` y `npm test` en `frontend/` y que pasen.
- Commits en español, uno por punto:
  `fix(diseño): botón Enviar fuera del cuadro de texto, abajo a la derecha` y
  `fix(diseño): íconos de Ahora mismo más grandes en Inicio`.
- Al terminar, anotar al final de este archivo qué cambió y las salidas de las pruebas.

## Resultado

### Cambios realizados

1. **Bandeja — botón Enviar fuera del cuadro de texto (`frontend/components/conversations/message-composer.tsx`, `frontend/components/conversations/email-composer.tsx`, `frontend/components/conversations/message-composer.test.tsx`):**
   - En `MessageComposer`, se quitó el contenedor relativo y las clases `pr-12` y `py-[13px]` del `Textarea`, volviendo al padding normal (`py-2.5`) y ocupando todo el ancho.
   - El botón redondo (`rounded-full`, `h-8 w-8`, ícono `Send`, `aria-label="Enviar"`, `title="Enviar"`, variante primaria o estilo ámbar en `isPrivate`) se movió fuera del cuadro, a la derecha (`ml-auto`) de la fila inferior junto a "Nota privada", "Respuestas rápidas" y el botón de adjuntar archivos.
   - En el efecto de crecimiento automático del `Textarea`, se sumó el borde (`offsetHeight - clientHeight`) al `scrollHeight` para calcular `fullHeight` sobre `border-box` y mantener `overflowY = "hidden"` mientras `fullHeight <= MAX_TEXTAREA_HEIGHT_PX` (`144px`, ~6 líneas), evitando que aparezca scroll antes de tiempo al agregar líneas vacías con `Shift+Enter`.
   - En `EmailComposer`, se quitó `pr-12` y el contenedor relativo del `Textarea`, y se ubicó el botón redondo `Enviar` abajo a la derecha en la fila del pie (`flex items-center justify-between gap-3`) junto a la leyenda de firma.
   - Se actualizaron y ampliaron los tests en `message-composer.test.tsx`.

2. **Inicio — íconos de "Ahora mismo" más grandes (`frontend/components/overview/account-overview.tsx`, `frontend/components/overview/account-overview.test.tsx`):**
   - En `LiveCard`, se agrandaron los íconos de las cuatro tarjetas de "Ahora mismo" (Abiertas, Sin atender, Sin asignar, Pendientes) de `h-5 w-5` a `h-8 w-8` con `gap-3.5`, manteniendo `neon-nav` y la alineación vertical (`flex items-center`) junto al bloque número (`text-2xl`) + etiqueta (`text-xs`), sin tocar la lista de "Accesos rápidos".
   - Se actualizó el test en `account-overview.test.tsx` para verificar el tamaño `h-8 w-8`.

### Salidas de las pruebas (`frontend/`)

```text
> alostudio-frontend@0.1.0 typecheck
> tsc --noEmit


> alostudio-frontend@0.1.0 lint
> next lint

`next lint` is deprecated and will be removed in Next.js 16.
For new projects, use create-next-app to choose your preferred linter.
For existing projects, migrate to the ESLint CLI:
npx @next/codemod@canary next-lint-to-eslint-cli .

✔ No ESLint warnings or errors

> alostudio-frontend@0.1.0 test
> vitest run


 RUN  v2.1.9 C:/Users/Zeek/Desktop/AloStudio-send2/frontend

 ✓ components/publications/network-rules.test.ts (7 tests) 29ms
 ✓ components/brand/neon-wordmark.test.tsx (7 tests) 243ms
 ✓ components/shell/nav.test.tsx (5 tests) 485ms
 ✓ components/oauth/oauth-consent.test.tsx (5 tests) 558ms
   ✓ Pantalla de consentimiento OAuth > muestra la app, el permiso y las cuentas, y al autorizar vuelve a la app con el código 314ms
 ✓ components/publications/publication-detail-dialog.test.tsx (2 tests) 586ms
   ✓ PublicationDetailDialog > habilita Reintentar y Actualizar estadísticas para un administrador en partially_published y Borrar en failed 338ms
 ✓ components/publications/analytics-view.test.tsx (3 tests) 570ms
 ✓ components/conversations/message-composer.test.tsx (6 tests) 718ms
   ✓ MessageComposer instant send > shows each message at once and sends them in order, one at a time 346ms
 ✓ components/settings/signatures/signatures-view.test.tsx (2 tests) 903ms
   ✓ SignaturesView > lista firmas, crea (cuerpo correcto y conteo de puntos de código), edita y borra 670ms
 ✓ components/settings/inboxes/email-transport-panel.test.tsx (13 tests) 983ms
 ✓ components/agenda/week-view.test.tsx (3 tests) 708ms
   ✓ AgendaView > loads the current week in weekly view, navigates weeks, and filters by status 371ms
 ✓ components/instagram/instagram-connection.test.tsx (9 tests) 680ms
 ✓ components/conversations/conversation-list.test.tsx (5 tests) 869ms
   ✓ ConversationList > offers one channel option per channel the account has 329ms
 ✓ components/settings/autoposts/autoposts-view.test.tsx (2 tests) 1100ms
   ✓ AutopostsView > lista feeds con revisado hace y último error, prueba el feed (entradas y error 422), crea, edita y borra 1049ms
 ✓ components/settings/sets/sets-view.test.tsx (2 tests) 1027ms
   ✓ SetsView > lista sets con canales y fecha, crea en modo set con el editor, edita y borra 962ms
 ✓ components/settings/plugs/plugs-view.test.tsx (3 tests) 1194ms
   ✓ PlugsView > pide mensaje solo cuando la acción tiene message_max, cuenta UTF-8 de Threads y permite listar, crear, editar y borrar 758ms
 ✓ components/settings/inboxes/email-template-panel.test.tsx (15 tests) 1172ms
   ✓ EmailTemplatePanel > saves the authored HTML 340ms
 ✓ components/settings/oauth-apps/oauth-apps-view.test.tsx (7 tests) 1269ms
   ✓ Ajustes → Apps OAuth > lista las apps de la cuenta con su client ID, tipo, autorizaciones y la guía de conexión 315ms
 ✓ components/agent/agent-chat.test.tsx (14 tests) 1891ms
   ✓ Agente — lista de chats y navegación sin recarga > muestra los chats, la etiqueta 'Por confirmar', no recarga la lista al cambiar de chat y permite borrar con confirmación 420ms
 ✓ components/instagram/post-autoreply-rules.test.tsx (17 tests) 1854ms
   ✓ PostAutoreplyRules > saves a keyword rule 324ms
 ✓ components/settings/email-templates/email-templates-view.test.tsx (15 tests) 1697ms
 ✓ components/conversations/inbox-three-column.test.tsx (5 tests) 2111ms
   ✓ Bandeja en tres columnas y pestañas > muestra lista y estado vacío juntos, y cambia entre conversaciones sin recargar la lista 984ms
   ✓ Bandeja en tres columnas y pestañas > muestra el resumen de reportes de la bandeja y la lista de canales conectados 343ms
   ✓ Bandeja en tres columnas y pestañas > colapsa y abre cada panel lateral por separado y recuerda su estado en localStorage 684ms
 ✓ components/publications/calendar-view.test.tsx (9 tests) 2526ms
   ✓ CalendarView — grilla, paginación y estados > ubica cada publicación en su día y hora local, pide todas las páginas del rango y pinta el estado 661ms
   ✓ CalendarView — grilla, paginación y estados > alinea la cabecera con las columnas de la grilla en vistas Semana, Día y Mes usando el mismo contenedor y plantilla de columnas 327ms
 ✓ components/publications/publication-editor-dialog.test.tsx (8 tests) 3276ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > arma el cuerpo de publicación programada con fecha ISO, media_id reordenados, post_type y content_override 1143ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > arma borrador (draft: true) y respeta post_type: 'reels' en Instagram 417ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > muestra errores de la tabla de reglas antes de enviar y muestra el 422 del backend con message y errors[] 349ms
   ✓ PublicationEditorDialog — firmas y sets > 'Usar set' carga texto, medios y canales activos (ignorando channel: null) sin cambiar la fecha, y 'Guardar como set' envía el cuerpo esperado 365ms
   ✓ PublicationEditorDialog — TikTok > muestra la cuenta, exige elegir la visibilidad a mano y manda las elecciones 427ms
 ✓ lib/inboxes/email-blocks.test.ts (15 tests) 12ms
 ✓ components/instagram/post-reply-picker.test.tsx (11 tests) 689ms
 ✓ components/publications/media-library-view.test.tsx (3 tests) 523ms
 ✓ middleware.test.ts (7 tests) 39ms
 ✓ app/accounts/[accountId]/template.test.tsx (3 tests) 158ms
 ✓ components/conversations/email-message.test.tsx (9 tests) 293ms
 ✓ lib/inboxes/email-template-design.test.ts (12 tests) 9ms
 ✓ components/reports/summary-table.test.tsx (3 tests) 341ms
 ✓ components/settings/inboxes/email-branding-panel.test.tsx (7 tests) 412ms
 ✓ components/settings/installation/installation-view.test.tsx (7 tests) 618ms
 ✓ components/conversations/email-composer.test.tsx (8 tests) 431ms
 ✓ components/conversations/ai-handoff.test.tsx (5 tests) 391ms
 ✓ components/settings/assignment-policies/assignment-policies-view.test.tsx (3 tests) 550ms
 ✓ components/contacts/contacts-view.test.tsx (4 tests) 772ms
 ✓ components/conversations/conversation-filters.test.tsx (3 tests) 500ms
 ✓ components/overview/account-overview.test.tsx (3 tests) 514ms
   ✓ AccountOverview — encabezado con órbita de redes > muestra el saludo, la bajada y los botones hacia bandeja y calendario 344ms
 ✓ components/settings/inboxes/channel-form.test.tsx (4 tests) 627ms
 ✓ lib/api/fetcher.test.ts (6 tests) 12ms
 ✓ components/reports/reports-view.test.tsx (2 tests) 650ms
   ✓ ReportsView > renders live counters and summary metrics 402ms
 ✓ components/settings/mcp-tokens/mcp-tokens-view.test.tsx (2 tests) 455ms
 ✓ components/help-center/portal-detail-view.test.tsx (3 tests) 479ms
 ✓ lib/api/notifications.test.tsx (3 tests) 284ms
 ✓ components/settings/integrations/integration-app-view.test.tsx (2 tests) 344ms
 ✓ components/instagram/connect-capabilities-dialog.test.tsx (6 tests) 278ms
 ✓ components/reports/metric-chart.test.tsx (6 tests) 118ms
 ✓ components/instagram/autoreply-view.test.tsx (4 tests) 311ms
 ✓ lib/api/reports-gaps.test.ts (6 tests) 9ms
 ✓ lib/realtime/cable.test.ts (3 tests) 12ms
 ✓ components/conversations/conversation-participants.test.tsx (3 tests) 397ms
 ✓ components/settings/profile/profile-view.test.tsx (1 test) 244ms
 ✓ components/settings/automation/automation-rules-view.test.tsx (3 tests) 201ms
 ✓ components/ui/tabs.test.tsx (3 tests) 194ms
 ✓ components/settings/macros/macros-view.test.tsx (4 tests) 176ms
 ✓ components/conversations/message-composer-canned.test.tsx (2 tests) 267ms
 ✓ app/(auth)/login/page.test.tsx (3 tests) 510ms
   ✓ LoginPage — a dónde va después de entrar > vuelve a la ruta interna de next con sus parámetros (el consentimiento OAuth) 312ms
 ✓ components/settings/custom-attributes/custom-attributes-view.test.tsx (1 test) 188ms
 ✓ components/campaigns/campaigns-view.test.tsx (1 test) 192ms
 ✓ components/settings/csat/csat-view.test.tsx (1 test) 248ms
 ✓ components/instagram/comments-panel.test.tsx (2 tests) 258ms
 ✓ components/settings/agents/agents-view.test.tsx (1 test) 272ms
 ✓ components/settings/inboxes/facebook-page-connect.test.tsx (2 tests) 326ms
 ✓ components/campaigns/campaign-analytics-panel.test.tsx (1 test) 183ms
 ✓ components/settings/canned-responses/canned-responses-view.test.tsx (2 tests) 642ms
   ✓ CannedResponsesView > sends the debounced search term to the backend 383ms
 ✓ components/settings/integrations/integrations-view.test.tsx (1 test) 175ms
 ✓ components/settings/webhooks/webhooks-view.test.tsx (1 test) 177ms
 ✓ components/conversations/conversation-actions.test.tsx (1 test) 271ms
 ✓ components/help-center/articles-panel.test.tsx (2 tests) 874ms
   ✓ ArticlesPanel search > sends the debounced query to the articles endpoint 511ms
   ✓ ArticlesPanel search > clears the search with the reset button 358ms
 ✓ lib/api/errors.test.ts (8 tests) 6ms
 ✓ components/shell/page-header.test.tsx (2 tests) 175ms
 ✓ components/reports/traffic-heatmap.test.tsx (3 tests) 180ms
 ✓ components/products/products-view.test.tsx (1 test) 174ms
 ✓ components/help-center/portals-view.test.tsx (1 test) 196ms
 ✓ lib/api/uploads.test.ts (3 tests) 61ms
 ✓ components/settings/agent-bots/agent-bots-view.test.tsx (1 test) 151ms
 ✓ lib/api/instagram.test.tsx (1 test) 122ms
 ✓ components/settings/teams/teams-view.test.tsx (1 test) 133ms
 ✓ components/ui/button.test.tsx (3 tests) 142ms
 ✓ components/conversations/channel-badge.test.tsx (5 tests) 117ms
 ✓ components/settings/labels/labels-view.test.tsx (1 test) 219ms
 ✓ components/settings/notifications/push-toggle.test.tsx (1 test) 142ms
 ✓ components/agenda/week-utils.test.ts (4 tests) 27ms
 ✓ components/help-center/portal-form.test.tsx (1 test) 196ms
 ✓ app/privacidad/page.test.tsx (3 tests) 173ms
 ✓ components/crm/crm-tabs.test.tsx (1 test) 90ms
 ✓ components/reports/bot-metrics-cards.test.tsx (1 test) 48ms
 ✓ app/terminos/page.test.tsx (2 tests) 110ms
 ✓ lib/time.test.ts (4 tests) 4ms
 ✓ lib/auth/schemas.test.ts (3 tests) 4ms
 ✓ app/eliminacion-de-datos/page.test.tsx (2 tests) 86ms

 Test Files  92 passed (92)
      Tests  401 passed (401)
   Start at  15:44:43
   Duration  18.59s (transform 7.61s, setup 53.80s, collect 67.27s, tests 44.63s, environment 193.15s, prepare 19.18s)
```

