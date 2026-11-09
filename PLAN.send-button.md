# Ajuste del botón Enviar del composer

Pedido del dueño (2026-11-09): el botón Enviar con el ícono del avión de papel
quedó dentro del cuadro de texto, pero pegado abajo. Debe:

1. Quedar centrado verticalmente respecto del alto del cuadro de texto (a medio
   camino entre el borde de arriba y el de abajo), a la derecha.
2. Ser redondo (círculo), mismo tamaño (h-8 w-8) y mismo color.

Archivos:
- `frontend/components/conversations/message-composer.tsx` (botón con
  `absolute bottom-2 right-2 h-8 w-8 rounded-control p-0`, cerca de la línea 272).
- `frontend/components/conversations/email-composer.tsx` (mismo botón, línea ~117).

Reglas:
- Si el textarea crece al escribir varias líneas, el botón debe seguir centrado
  verticalmente en el cuadro y no tapar el texto (el texto ya deja espacio a la
  derecha; mantenerlo).
- Respetar `frontend/DESIGN-SYSTEM.md`. No usar clases de opacidad tipo `bg-x/NN`
  sobre colores del tema (no generan CSS).
- No tocar backend ni otras pantallas.
- Correr `npm run typecheck`, `npm run lint` y `npm test` en `frontend/` y que pasen.
- Un commit en español: `fix(diseño): botón Enviar redondo y centrado en el cuadro de texto`.
- Al terminar, anotar al final de este archivo qué cambió y las salidas de las pruebas.

## Resultado

### Cambios realizados

- `frontend/components/conversations/message-composer.tsx`: en el botón `Enviar` (línea 272), se reemplazó `absolute bottom-2 right-2 h-8 w-8 rounded-control p-0` por `absolute right-2 top-1/2 h-8 w-8 -translate-y-1/2 rounded-full p-0`, manteniéndolo redondo (`rounded-full`), del mismo tamaño (`h-8 w-8`), mismo color (primario o ámbar en nota privada), centrado verticalmente respecto del cuadro de texto y conservando `pr-12` en el `Textarea`.
- `frontend/components/conversations/email-composer.tsx`: en el botón `Enviar` (línea 117), se reemplazó `absolute bottom-2 right-2 h-8 w-8 rounded-control p-0` por `absolute right-2 top-1/2 h-8 w-8 -translate-y-1/2 rounded-full p-0`, manteniendo `pr-12` en el `Textarea`.

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


 RUN  v2.1.9 C:/Users/Zeek/Desktop/AloStudio-send/frontend

 ✓ components/publications/network-rules.test.ts (7 tests) 13ms
 ✓ components/brand/neon-wordmark.test.tsx (7 tests) 226ms
 ✓ components/shell/nav.test.tsx (5 tests) 374ms
 ✓ components/oauth/oauth-consent.test.tsx (5 tests) 564ms
 ✓ components/publications/analytics-view.test.tsx (3 tests) 473ms
 ✓ components/publications/publication-detail-dialog.test.tsx (2 tests) 611ms
   ✓ PublicationDetailDialog > habilita Reintentar y Actualizar estadísticas para un administrador en partially_published y Borrar en failed 357ms
 ✓ components/conversations/message-composer.test.tsx (5 tests) 731ms
   ✓ MessageComposer instant send > shows each message at once and sends them in order, one at a time 327ms
 ✓ components/instagram/instagram-connection.test.tsx (9 tests) 558ms
 ✓ components/settings/inboxes/email-transport-panel.test.tsx (13 tests) 939ms
 ✓ components/settings/signatures/signatures-view.test.tsx (2 tests) 889ms
   ✓ SignaturesView > lista firmas, crea (cuerpo correcto y conteo de puntos de código), edita y borra 684ms
 ✓ components/agenda/week-view.test.tsx (3 tests) 688ms
   ✓ AgendaView > loads the current week in weekly view, navigates weeks, and filters by status 349ms
 ✓ components/settings/inboxes/email-template-panel.test.tsx (15 tests) 1046ms
 ✓ components/conversations/conversation-list.test.tsx (5 tests) 881ms
   ✓ ConversationList > offers one channel option per channel the account has 336ms
 ✓ components/settings/sets/sets-view.test.tsx (2 tests) 992ms
   ✓ SetsView > lista sets con canales y fecha, crea en modo set con el editor, edita y borra 953ms
 ✓ components/settings/autoposts/autoposts-view.test.tsx (2 tests) 1098ms
   ✓ AutopostsView > lista feeds con revisado hace y último error, prueba el feed (entradas y error 422), crea, edita y borra 1049ms
 ✓ components/settings/plugs/plugs-view.test.tsx (3 tests) 1357ms
   ✓ PlugsView > pide mensaje solo cuando la acción tiene message_max, cuenta UTF-8 de Threads y permite listar, crear, editar y borrar 870ms
 ✓ components/settings/oauth-apps/oauth-apps-view.test.tsx (7 tests) 1311ms
   ✓ Ajustes → Apps OAuth > crea una app y muestra el secreto una sola vez 308ms
 ✓ components/instagram/post-autoreply-rules.test.tsx (17 tests) 1824ms
 ✓ components/settings/email-templates/email-templates-view.test.tsx (15 tests) 1801ms
 ✓ components/agent/agent-chat.test.tsx (14 tests) 1906ms
   ✓ Agente — lista de chats y navegación sin recarga > muestra los chats, la etiqueta 'Por confirmar', no recarga la lista al cambiar de chat y permite borrar con confirmación 480ms
 ✓ components/instagram/post-reply-picker.test.tsx (11 tests) 714ms
 ✓ components/conversations/inbox-three-column.test.tsx (5 tests) 2155ms
   ✓ Bandeja en tres columnas y pestañas > muestra lista y estado vacío juntos, y cambia entre conversaciones sin recargar la lista 984ms
   ✓ Bandeja en tres columnas y pestañas > muestra el resumen de reportes de la bandeja y la lista de canales conectados 375ms
   ✓ Bandeja en tres columnas y pestañas > colapsa y abre cada panel lateral por separado y recuerda su estado en localStorage 694ms
 ✓ lib/inboxes/email-blocks.test.ts (15 tests) 16ms
 ✓ components/publications/calendar-view.test.tsx (9 tests) 2753ms
   ✓ CalendarView — grilla, paginación y estados > ubica cada publicación en su día y hora local, pide todas las páginas del rango y pinta el estado 686ms
   ✓ CalendarView — grilla, paginación y estados > abre con la línea de ahora en el medio y respeta si el usuario se movió 349ms
   ✓ CalendarView — grilla, paginación y estados > deja crear otra publicación en una hora que ya tiene una 334ms
   ✓ CalendarView — grilla, paginación y estados > alinea la cabecera con las columnas de la grilla en vistas Semana, Día y Mes usando el mismo contenedor y plantilla de columnas 375ms
   ✓ CalendarView — conexión de canales y avisos de query > 'Agregar canal' con una red form abre el diálogo, envía { fields } y muestra el 422 sin cerrarlo 334ms
 ✓ components/publications/media-library-view.test.tsx (3 tests) 573ms
   ✓ MediaLibraryView > rechaza una imagen mayor a 30 MB y un video mayor a 200 MB antes de subir 306ms
 ✓ components/publications/publication-editor-dialog.test.tsx (8 tests) 3461ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > arma el cuerpo de publicación programada con fecha ISO, media_id reordenados, post_type y content_override 1173ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > arma borrador (draft: true) y respeta post_type: 'reels' en Instagram 439ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > muestra errores de la tabla de reglas antes de enviar y muestra el 422 del backend con message y errors[] 396ms
   ✓ PublicationEditorDialog — firmas y sets > 'Usar set' carga texto, medios y canales activos (ignorando channel: null) sin cambiar la fecha, y 'Guardar como set' envía el cuerpo esperado 368ms
   ✓ PublicationEditorDialog — TikTok > muestra la cuenta, exige elegir la visibilidad a mano y manda las elecciones 419ms
 ✓ middleware.test.ts (7 tests) 35ms
 ✓ app/accounts/[accountId]/template.test.tsx (3 tests) 152ms
 ✓ components/conversations/email-message.test.tsx (9 tests) 297ms
 ✓ lib/inboxes/email-template-design.test.ts (12 tests) 11ms
 ✓ components/reports/summary-table.test.tsx (3 tests) 354ms
 ✓ components/settings/inboxes/email-branding-panel.test.tsx (7 tests) 406ms
 ✓ components/settings/installation/installation-view.test.tsx (7 tests) 572ms
 ✓ components/conversations/email-composer.test.tsx (8 tests) 452ms
 ✓ components/conversations/conversation-filters.test.tsx (3 tests) 466ms
 ✓ components/overview/account-overview.test.tsx (3 tests) 474ms
   ✓ AccountOverview — encabezado con órbita de redes > muestra el saludo, la bajada y los botones hacia bandeja y calendario 317ms
 ✓ components/settings/assignment-policies/assignment-policies-view.test.tsx (3 tests) 554ms
 ✓ components/contacts/contacts-view.test.tsx (4 tests) 745ms
 ✓ components/conversations/ai-handoff.test.tsx (5 tests) 422ms
 ✓ lib/api/fetcher.test.ts (6 tests) 17ms
 ✓ components/settings/inboxes/channel-form.test.tsx (4 tests) 603ms
 ✓ components/reports/reports-view.test.tsx (2 tests) 678ms
   ✓ ReportsView > renders live counters and summary metrics 438ms
 ✓ components/instagram/connect-capabilities-dialog.test.tsx (6 tests) 306ms
 ✓ components/settings/mcp-tokens/mcp-tokens-view.test.tsx (2 tests) 479ms
 ✓ components/help-center/portal-detail-view.test.tsx (3 tests) 494ms
 ✓ lib/api/notifications.test.tsx (3 tests) 320ms
 ✓ components/settings/integrations/integration-app-view.test.tsx (2 tests) 393ms
 ✓ components/instagram/autoreply-view.test.tsx (4 tests) 373ms
 ✓ components/settings/automation/automation-rules-view.test.tsx (3 tests) 262ms
 ✓ components/reports/metric-chart.test.tsx (6 tests) 160ms
 ✓ lib/api/reports-gaps.test.ts (6 tests) 11ms
 ✓ components/conversations/conversation-participants.test.tsx (3 tests) 428ms
 ✓ lib/realtime/cable.test.ts (3 tests) 9ms
 ✓ components/settings/macros/macros-view.test.tsx (4 tests) 225ms
 ✓ components/ui/tabs.test.tsx (3 tests) 241ms
 ✓ components/settings/profile/profile-view.test.tsx (1 test) 261ms
 ✓ components/conversations/message-composer-canned.test.tsx (2 tests) 261ms
 ✓ components/campaigns/campaigns-view.test.tsx (1 test) 232ms
 ✓ components/settings/csat/csat-view.test.tsx (1 test) 293ms
 ✓ components/settings/custom-attributes/custom-attributes-view.test.tsx (1 test) 209ms
 ✓ app/(auth)/login/page.test.tsx (3 tests) 530ms
   ✓ LoginPage — a dónde va después de entrar > vuelve a la ruta interna de next con sus parámetros (el consentimiento OAuth) 333ms
 ✓ components/instagram/comments-panel.test.tsx (2 tests) 280ms
 ✓ components/settings/agents/agents-view.test.tsx (1 test) 315ms
   ✓ AgentsView > lists agents with role + pending badge + email 309ms
 ✓ components/settings/inboxes/facebook-page-connect.test.tsx (2 tests) 328ms
 ✓ components/campaigns/campaign-analytics-panel.test.tsx (1 test) 215ms
 ✓ components/settings/canned-responses/canned-responses-view.test.tsx (2 tests) 756ms
   ✓ CannedResponsesView > lists responses with their short codes and content 333ms
   ✓ CannedResponsesView > sends the debounced search term to the backend 414ms
 ✓ components/settings/integrations/integrations-view.test.tsx (1 test) 183ms
 ✓ components/settings/webhooks/webhooks-view.test.tsx (1 test) 183ms
 ✓ lib/api/errors.test.ts (8 tests) 9ms
 ✓ components/conversations/conversation-actions.test.tsx (1 test) 276ms
 ✓ components/help-center/articles-panel.test.tsx (2 tests) 903ms
   ✓ ArticlesPanel search > sends the debounced query to the articles endpoint 536ms
   ✓ ArticlesPanel search > clears the search with the reset button 361ms
 ✓ components/help-center/portals-view.test.tsx (1 test) 201ms
 ✓ components/reports/traffic-heatmap.test.tsx (3 tests) 212ms
 ✓ components/products/products-view.test.tsx (1 test) 206ms
 ✓ components/shell/page-header.test.tsx (2 tests) 188ms
 ✓ lib/api/uploads.test.ts (3 tests) 56ms
 ✓ components/settings/agent-bots/agent-bots-view.test.tsx (1 test) 179ms
 ✓ components/settings/notifications/push-toggle.test.tsx (1 test) 151ms
 ✓ components/settings/teams/teams-view.test.tsx (1 test) 161ms
 ✓ components/ui/button.test.tsx (3 tests) 146ms
 ✓ components/conversations/channel-badge.test.tsx (5 tests) 126ms
 ✓ components/settings/labels/labels-view.test.tsx (1 test) 232ms
 ✓ components/help-center/portal-form.test.tsx (1 test) 213ms
 ✓ components/agenda/week-utils.test.ts (4 tests) 30ms
 ✓ app/privacidad/page.test.tsx (3 tests) 199ms
 ✓ lib/api/instagram.test.tsx (1 test) 127ms
 ✓ components/crm/crm-tabs.test.tsx (1 test) 104ms
 ✓ app/terminos/page.test.tsx (2 tests) 110ms
 ✓ components/reports/bot-metrics-cards.test.tsx (1 test) 52ms
 ✓ lib/time.test.ts (4 tests) 5ms
 ✓ lib/auth/schemas.test.ts (3 tests) 4ms
 ✓ app/eliminacion-de-datos/page.test.tsx (2 tests) 82ms

 Test Files  92 passed (92)
      Tests  400 passed (400)
   Start at  01:00:58
   Duration  20.37s (transform 10.52s, setup 62.70s, collect 77.31s, tests 45.91s, environment 212.76s, prepare 18.93s)
```
