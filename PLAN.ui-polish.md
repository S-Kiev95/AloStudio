# PLAN — Ajustes de interfaz (sidebar, transiciones, inicio, calendario, bandeja, Instagram)

Pedido del dueño (2026-11-08), con capturas. Rama `feat/ui-polish`, worktree `C:\Users\Zeek\Desktop\AloStudio-ui`, sale de `develop` (`78d1e5b`). **Solo frontend.** Lo hace Argon y lo revisa Claude contra este documento, en el navegador.

## Reglas para el agente

Trabajá **solo** en `C:\Users\Zeek\Desktop\AloStudio-ui`; no leas `C:\Users\Zeek\Desktop\Postiz` ni otros worktrees; **no toques el backend** (`app/`, `alembic/`, `tests/` de Python); sin `git push`, sin `ssh`, sin `.env*`, sin bases, sin contenedores; **sin librerías nuevas** de npm. Commits chicos en `feat/ui-polish`, uno por punto de abajo, en español con el estilo del repo (`feat(diseño): ...`, `fix(diseño): ...`), cada uno terminado en `Co-Authored-By: Antigravity <noreply@google.com>`. Al final completá **Estado** con lo hecho y la salida real de `npm run typecheck`, `npm run lint` y `npm test` en `frontend/`.

- Seguí el sistema de diseño: `docs/design-neon/DESIGN.md` y `frontend/DESIGN-SYSTEM.md`. Mirá cómo están hechos componentes parecidos antes de escribir uno nuevo.
- **Sin modificadores de opacidad sobre colores del tema** (`bg-primary/60`, `text-neon/50`…): Tailwind 3 no genera esas clases con nuestros colores. Usá los tokens CSS (`var(--...)`).
- Todo tiene que funcionar en **tema claro y oscuro**, en escritorio y en móvil (en móvil no se rompe nada de lo que ya funciona).
- Accesibilidad: cada botón nuevo con `aria-label` en español y `aria-expanded` cuando abre o cierra algo; foco visible; se puede usar con teclado.
- Respetá `prefers-reduced-motion: reduce`: sin animaciones ni transiciones de página en ese caso.
- No cambies textos, rutas, datos ni llamadas a la API.

## 1. Sidebar colapsable

Archivos: `frontend/components/shell/dashboard-shell.tsx`, `sidebar-nav.tsx`, `app-icons.tsx`, y el cartel `frontend/components/brand/neon-wordmark.tsx`.

- Un botón en la sidebar (arriba, junto a la marca, o abajo, lo que quede más prolijo) la colapsa y la vuelve a abrir.
- **Colapsada** queda angosta y muestra **solo la "A" de AloStudio** arriba (la primera letra del cartel, con el mismo neón; sin las escenas animadas del cartel completo, encendida y fija) y **solo los iconos** del menú, incluido Ajustes abajo. Cada icono muestra su nombre como `title`/tooltip al pasar el mouse, y el ítem activo se sigue distinguiendo.
- El contenido ocupa el espacio liberado. La transición del ancho es suave (~200 ms) y sin saltos del contenido.
- El estado se recuerda por navegador en `localStorage` (envuelto en `try/catch`), y al cargar no hay parpadeo visible entre abierta y colapsada.
- En móvil, el menú actual sigue funcionando igual: esto aplica a escritorio.

## 2. View Transitions entre páginas

Hoy `frontend/app/accounts/[accountId]/template.tsx` aplica `.page-enter`. Agregá transiciones entre páginas con la **View Transitions API** del navegador (`document.startViewTransition` o el soporte de Next 15 si es estable; nada experimental que pida cambiar `next.config`).

- Al navegar dentro de la cuenta, el contenido principal hace un fundido corto (150–250 ms). La sidebar y la barra superior **no** se animan: quedan fijas (`view-transition-name` propio).
- Si el navegador no soporta la API, se navega como hoy, sin error. Con `prefers-reduced-motion: reduce`, sin transición.
- Que no rompa el `.page-enter` ni el cartel animado; si `.page-enter` queda redundante, sacalo.

## 3. Inicio: iconos de "Ahora mismo" como los de la sidebar

Archivo: `frontend/components/overview/account-overview.tsx`. Las cuatro tarjetas (Abiertas, Sin atender, Sin asignar, Pendientes) usan hoy iconos y colores sueltos (uno amarillo, uno rojo, uno sobre un cuadrado gris). Que usen el **mismo set y el mismo estilo** que los iconos de la sidebar (`components/shell/app-icons.tsx` o los mismos de lucide con el mismo grosor y tamaño), en el color del tema, sin el cuadrado de fondo distinto. Elegí iconos que representen cada número. Revisá también las tarjetas de "Últimos 7 días" si tienen el mismo problema.

## 4. Calendario: cabecera alineada con las columnas

Archivo: `frontend/components/publications/calendar-view.tsx` (vista Semana). Los nombres de los días ("Lunes 02/11"…) no quedan centrados sobre sus columnas: la cabecera y la grilla tienen distinto ancho porque la grilla tiene barra de desplazamiento vertical y la cabecera no, o la columna de horas mide distinto. Hacé que **cada encabezado quede exactamente sobre su columna**, con o sin barra de desplazamiento (por ejemplo, misma plantilla de grilla en ambas y `scrollbar-gutter: stable`). Revisá también las vistas Día y Mes.

## 5. Bandeja: paneles laterales colapsables

Archivos: `frontend/components/conversations/inbox-shell.tsx`, `conversation-list.tsx`, `contact-panel.tsx`, `conversation-view.tsx`.

- El panel de la **lista de conversaciones** (izquierda) y el del **contacto** (derecha) se pueden colapsar cada uno por separado, para que el chat del medio gane espacio.
- Un botón chico en el borde de cada panel (o en la barra superior del chat) los colapsa y abre. Colapsado, el panel desaparece del todo o queda como una franja angosta con el botón para volver a abrirlo; nunca un hueco vacío.
- Se recuerda por navegador en `localStorage` (con `try/catch`). Transición suave del ancho.
- En pantallas chicas se mantiene el comportamiento actual (una columna a la vez).

## 6. Bandeja: botón Enviar dentro del cuadro de texto

Archivo: `frontend/components/conversations/message-composer.tsx` (y si corresponde `email-composer.tsx`, mismo criterio).

- El botón "Enviar" pasa a estar **dentro del cuadro de texto, abajo a la derecha**, como botón redondo o cuadrado chico **solo con el icono del avión de papel** (el `Send` que ya usa), con `aria-label="Enviar"` y `title="Enviar"`.
- El texto no puede quedar tapado por el botón: dejá el espacio necesario a la derecha del área de texto.
- Mantené todo lo demás: deshabilitado cuando no hay nada para mandar, el atajo de teclado que exista, Nota privada (si el composer cambia de color en nota privada, el botón también), Respuestas rápidas y adjuntos en la fila de abajo.
- Actualizá los tests del composer que buscan el botón por su texto "Enviar" para que lo busquen por su nombre accesible.

## 7. Instagram: botón "Instagram Login" con los colores de Instagram

Archivo: `frontend/components/instagram/instagram-connection.tsx`. Hoy "Facebook Login" es azul (primario) y "Instagram Login" es un botón neutro. Que el de Instagram tenga el **degradado de la marca Instagram** (de amarillo/naranja a rosa y violeta, p. ej. `#F58529 → #DD2A7B → #8134AF → #515BD4`), texto e icono en blanco, contraste AA, con el mismo tamaño, forma y estados (hover, foco, deshabilitado) que el de Facebook. Es una excepción de marca al sistema de diseño: anotala en `frontend/DESIGN-SYSTEM.md`.

## Tests

Vitest con Testing Library, junto a cada componente, siguiendo los tests que ya existen:

- Sidebar: colapsa y abre con el botón, `aria-expanded` cambia, colapsada muestra los iconos con su nombre accesible, y recuerda el estado (`localStorage` simulado).
- Bandeja: cada panel colapsa y abre por separado y recuerda su estado.
- Composer: el botón de enviar se encuentra por `getByRole("button", { name: "Enviar" })`, está deshabilitado sin texto y envía con texto.
- Calendario: si hay una forma razonable de comprobar que cabecera y grilla usan la misma plantilla de columnas, testealo; si no, explicá en Estado cómo lo verificaste.

## Fuera de alcance

Backend, textos, nuevas funciones, librerías nuevas, cambiar colores del tema o de otros botones, el cartel animado (salvo la "A" de la sidebar colapsada).

## Terminado cuando

Los siete puntos funcionan en claro y oscuro, en escritorio sin romper móvil, con typecheck, lint y tests en verde.

## Estado

Completado en `feat/ui-polish` (un commit por punto):

1. **Sidebar colapsable (`4ba43a0`)**:
   - `frontend/components/brand/neon-wordmark.tsx`: agregado prop `collapsed` que renderiza únicamente el monograma `"A"` con la estética neón (`neon-sign-char` encendido y fijo, sin los timers de escenas animadas del cartel completo) y `aria-label="AloStudio"`.
   - `frontend/components/shell/app-icons.tsx`: agregados `SidebarCollapseIcon` y `SidebarExpandIcon` con el trazo compartido del sistema (`strokeWidth={1.75}`).
   - `frontend/components/shell/dashboard-shell.tsx` y `frontend/components/shell/sidebar-nav.tsx`: la barra lateral de escritorio (`lg:grid-cols-[236px_1fr]` → `lg:grid-cols-[68px_1fr]`, transición de `200ms ease-out` respetando `motion-reduce:transition-none`) se colapsa y expande con un botón accesible (`aria-label="Colapsar menú lateral"` / `"Expandir menú lateral"`, `aria-expanded`), muestra solo los iconos (incluido `Ajustes`) con `title` y `aria-label`, y persiste el estado en `localStorage` (`alostudio:sidebar-collapsed`) envuelto en `try/catch` (con lectura sincronizada antes del pintado para evitar parpadeo). El cajón móvil se mantiene intacto.
   - Tests en `frontend/components/brand/neon-wordmark.test.tsx` y `frontend/components/shell/nav.test.tsx`.

2. **View Transitions entre páginas (`03f74ad`)**:
   - `frontend/app/accounts/[accountId]/template.tsx`: intercepta en fase de captura los clics primarios en enlaces internos de la cuenta y envuelve `router.push` en `document.startViewTransition` cuando la API está disponible y `prefers-reduced-motion: reduce` no está activo; si el navegador no soporta la API o el usuario prefiere movimiento reducido, navega normalmente sin error.
   - `frontend/app/globals.css` y `frontend/components/shell/dashboard-shell.tsx`: asignados `view-transition-name: app-sidebar` (`.vt-sidebar`), `view-transition-name: app-topbar` (`.vt-topbar`) sin animación para que permanezcan fijos, y `view-transition-name: account-page` (`.vt-page`) con fundido corto (`160ms`/`200ms`) desactivado bajo `prefers-reduced-motion: reduce`.
   - Tests en `frontend/app/accounts/[accountId]/template.test.tsx`.

3. **Inicio: iconos de "Ahora mismo" como los de la sidebar (`e71175c`)**:
   - `frontend/components/overview/account-overview.tsx`: reemplazados los iconos de Lucide con colores sueltos (amarillo, rojo, cuadrado gris) en las cuatro tarjetas de "Ahora mismo" (Abiertas, Sin atender, Sin asignar, Pendientes) y en "Últimos 7 días" por iconos SVG con el mismo trazo y clase `.neon-nav` que usa la sidebar (`InboxIcon`, `UnattendedIcon`, `UnassignedIcon`, `PendingClockIcon`), en el color del tema y sin cuadrado de fondo distinto.
   - Tests en `frontend/components/overview/account-overview.test.tsx`.

4. **Calendario: cabecera alineada con las columnas (`907ab79`)**:
   - `frontend/components/publications/calendar-view.tsx`: movida la cabecera `calendar-day-headers` dentro del contenedor desplazable `calendar-hourly-scroller` como `sticky top-0 z-30` con `scrollbarGutter: "stable"` y compartiendo la misma constante `hourlyGridColumns` (`gridTemplateColumns: "56px repeat(7, minmax(0, 1fr))"` en Semana y `"56px minmax(0, 1fr)"` en Día) entre la cabecera y cada fila horaria, eliminando el desfase por el ancho de la barra de scroll vertical. En la vista Mes, cabecera y celdas comparten `gridTemplateColumns: "repeat(7, minmax(0, 1fr))"`.
   - **Verificación en tests** (`frontend/components/publications/calendar-view.test.tsx`): se comprueba que `calendar-day-headers` está dentro de `calendar-hourly-scroller` (`scroller.contains(headers)`), que `scroller.style.scrollbarGutter === "stable"`, y que `headers.style.gridTemplateColumns` coincide exactamente con el `style.gridTemplateColumns` de todas las filas `[data-testid^="slot-"]` tanto en vista Semana (`56px repeat(7, minmax(0, 1fr))`) como en vista Día (`56px minmax(0, 1fr)`), además de verificar `repeat(7, minmax(0, 1fr))` en la vista Mes.

5. **Bandeja: paneles laterales colapsables (`eaa5660`)**:
   - `frontend/components/conversations/inbox-shell.tsx`, `conversation-list.tsx`, `contact-panel.tsx`, `conversation-view.tsx`: los paneles de lista de conversaciones (izquierda) y de contacto (derecha) se colapsan y abren de forma independiente en escritorio (`lg:transition-[width] lg:duration-200 motion-reduce:transition-none`), quedando como una franja angosta (`lg:w-11`) con el botón para volver a abrirlos sin dejar huecos vacíos y manteniendo montada la lista oculta (`lg:hidden`) para no perder estado ni recargar queries al cambiar de conversación. Persistencia independiente en `localStorage` (`alostudio:inbox-list-collapsed` y `alostudio:inbox-contact-collapsed`) envuelta en `try/catch`. En pantallas chicas se conserva el comportamiento de una columna a la vez.
   - Tests en `frontend/components/conversations/inbox-three-column.test.tsx`.

6. **Bandeja: botón Enviar dentro del cuadro de texto (`eb2b0ca`)**:
   - `frontend/components/conversations/message-composer.tsx` y `frontend/components/conversations/email-composer.tsx`: el botón "Enviar" se ubicó dentro de un contenedor `relative` del `textarea`, abajo a la derecha (`bottom-2 right-2 h-8 w-8`), solo con el icono `Send`, `aria-label="Enviar"` y `title="Enviar"`, dejando `pr-12` en el `textarea` para no tapar el texto. En modo Nota privada (`isPrivate`), el botón acompaña el color ámbar de la nota.
   - Tests actualizados y ampliados en `frontend/components/conversations/message-composer.test.tsx` y `frontend/components/conversations/email-composer.test.tsx`.

7. **Instagram: botón "Instagram Login" con los colores de Instagram (`53fe73c`)**:
   - `frontend/app/globals.css` y `frontend/components/instagram/instagram-connection.tsx`: creada la utilidad `.btn-instagram-brand` con el degradado oficial `#F58529 → #DD2A7B → #8134AF → #515BD4`, texto e icono en blanco (`#FFFFFF`, contraste AA), mismo tamaño, bordes redondeados y estados (`hover`, `focus-visible`, `disabled`) que el botón de "Facebook Login". Documentada la excepción de marca en `frontend/DESIGN-SYSTEM.md`.
   - Tests en `frontend/components/instagram/instagram-connection.test.tsx`.

### Salida real de `npm run typecheck`, `npm run lint` y `npm test` en `frontend/`

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


 RUN  v2.1.9 C:/Users/Zeek/Desktop/AloStudio-ui/frontend

 ✓ components/publications/network-rules.test.ts (7 tests) 24ms
 ✓ components/brand/neon-wordmark.test.tsx (7 tests) 290ms
 ✓ components/shell/nav.test.tsx (5 tests) 486ms
 ✓ components/publications/publication-detail-dialog.test.tsx (2 tests) 671ms
   ✓ PublicationDetailDialog > habilita Reintentar y Actualizar estadísticas para un administrador en partially_published y Borrar en failed 409ms
 ✓ components/oauth/oauth-consent.test.tsx (5 tests) 672ms
   ✓ Pantalla de consentimiento OAuth > muestra la app, el permiso y las cuentas, y al autorizar vuelve a la app con el código 356ms
 ✓ components/publications/analytics-view.test.tsx (3 tests) 573ms
 ✓ components/settings/signatures/signatures-view.test.tsx (2 tests) 912ms
   ✓ SignaturesView > lista firmas, crea (cuerpo correcto y conteo de puntos de código), edita y borra 708ms
 ✓ components/instagram/instagram-connection.test.tsx (9 tests) 677ms
 ✓ components/conversations/message-composer.test.tsx (5 tests) 869ms
   ✓ MessageComposer instant send > shows each message at once and sends them in order, one at a time 375ms
 ✓ components/settings/sets/sets-view.test.tsx (2 tests) 1027ms
   ✓ SetsView > lista sets con canales y fecha, crea en modo set con el editor, edita y borra 971ms
 ✓ components/agenda/week-view.test.tsx (3 tests) 797ms
   ✓ WeekView > renders Monday-to-Sunday columns and groups appointments by local day in chronological order 302ms
   ✓ AgendaView > loads the current week in weekly view, navigates weeks, and filters by status 429ms
 ✓ components/settings/inboxes/email-transport-panel.test.tsx (13 tests) 1192ms
 ✓ components/conversations/conversation-list.test.tsx (5 tests) 975ms
   ✓ ConversationList > offers one channel option per channel the account has 385ms
 ✓ components/settings/inboxes/email-template-panel.test.tsx (15 tests) 1245ms
   ✓ EmailTemplatePanel > saves the authored HTML 362ms
 ✓ components/settings/autoposts/autoposts-view.test.tsx (2 tests) 1287ms
   ✓ AutopostsView > lista feeds con revisado hace y último error, prueba el feed (entradas y error 422), crea, edita y borra 1237ms
 ✓ components/settings/plugs/plugs-view.test.tsx (3 tests) 1480ms
   ✓ PlugsView > pide mensaje solo cuando la acción tiene message_max, cuenta UTF-8 de Threads y permite listar, crear, editar y borrar 989ms
 ✓ components/settings/oauth-apps/oauth-apps-view.test.tsx (7 tests) 1503ms
   ✓ Ajustes → Apps OAuth > lista las apps de la cuenta con su client ID, tipo, autorizaciones y la guía de conexión 361ms
   ✓ Ajustes → Apps OAuth > crea una app y muestra el secreto una sola vez 358ms
 ✓ components/settings/email-templates/email-templates-view.test.tsx (15 tests) 2030ms
 ✓ components/instagram/post-autoreply-rules.test.tsx (17 tests) 2229ms
   ✓ PostAutoreplyRules > saves a keyword rule 351ms
 ✓ components/agent/agent-chat.test.tsx (14 tests) 2213ms
   ✓ Agente — lista de chats y navegación sin recarga > muestra los chats, la etiqueta 'Por confirmar', no recarga la lista al cambiar de chat y permite borrar con confirmación 584ms
 ✓ components/conversations/inbox-three-column.test.tsx (5 tests) 2385ms
   ✓ Bandeja en tres columnas y pestañas > muestra lista y estado vacío juntos, y cambia entre conversaciones sin recargar la lista 1097ms
   ✓ Bandeja en tres columnas y pestañas > muestra el resumen de reportes de la bandeja y la lista de canales conectados 387ms
   ✓ Bandeja en tres columnas y pestañas > colapsa y abre cada panel lateral por separado y recuerda su estado en localStorage 759ms
 ✓ components/publications/calendar-view.test.tsx (9 tests) 2920ms
   ✓ CalendarView — grilla, paginación y estados > ubica cada publicación en su día y hora local, pide todas las páginas del rango y pinta el estado 793ms
   ✓ CalendarView — grilla, paginación y estados > abre con la línea de ahora en el medio y respeta si el usuario se movió 361ms
   ✓ CalendarView — grilla, paginación y estados > deja crear otra publicación en una hora que ya tiene una 323ms
   ✓ CalendarView — grilla, paginación y estados > alinea la cabecera con las columnas de la grilla en vistas Semana, Día y Mes usando el mismo contenedor y plantilla de columnas 407ms
   ✓ CalendarView — conexión de canales y avisos de query > 'Agregar canal' con una red form abre el diálogo, envía { fields } y muestra el 422 sin cerrarlo 313ms
 ✓ components/publications/publication-editor-dialog.test.tsx (8 tests) 3973ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > arma el cuerpo de publicación programada con fecha ISO, media_id reordenados, post_type y content_override 1405ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > arma borrador (draft: true) y respeta post_type: 'reels' en Instagram 479ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > muestra errores de la tabla de reglas antes de enviar y muestra el 422 del backend con message y errors[] 497ms
   ✓ PublicationEditorDialog — firmas y sets > 'Usar set' carga texto, medios y canales activos (ignorando channel: null) sin cambiar la fecha, y 'Guardar como set' envía el cuerpo esperado 423ms
   ✓ PublicationEditorDialog — TikTok > muestra la cuenta, exige elegir la visibilidad a mano y manda las elecciones 496ms
   ✓ PublicationEditorDialog — TikTok > no deja publicar un video más largo de lo que admite la cuenta 317ms
 ✓ lib/inboxes/email-blocks.test.ts (15 tests) 16ms
 ✓ components/instagram/post-reply-picker.test.tsx (11 tests) 742ms
 ✓ middleware.test.ts (7 tests) 36ms
 ✓ components/publications/media-library-view.test.tsx (3 tests) 610ms
   ✓ MediaLibraryView > rechaza una imagen mayor a 30 MB y un video mayor a 200 MB antes de subir 331ms
 ✓ app/accounts/[accountId]/template.test.tsx (3 tests) 158ms
 ✓ components/conversations/email-message.test.tsx (9 tests) 314ms
 ✓ lib/inboxes/email-template-design.test.ts (12 tests) 12ms
 ✓ components/reports/summary-table.test.tsx (3 tests) 389ms
 ✓ components/settings/inboxes/email-branding-panel.test.tsx (7 tests) 437ms
 ✓ components/settings/installation/installation-view.test.tsx (7 tests) 1512ms
   ✓ Secciones colapsables > pliega y despliega una sección, con cuántos ajustes tiene listos 918ms
 ✓ components/conversations/conversation-filters.test.tsx (3 tests) 1929ms
   ✓ ConversationFilters > saves the current filter as a named view 1406ms
 ✓ components/conversations/ai-handoff.test.tsx (5 tests) 1838ms
   ✓ AiHandoff > shows why the AI handed it off and hands it back 687ms
   ✓ AiHandoff > shows who has the conversation on the button 622ms
 ✓ components/conversations/email-composer.test.tsx (8 tests) 2007ms
   ✓ EmailComposer > omits empty copy fields rather than sending blanks 515ms
   ✓ EmailComposer > will not send an empty reply 314ms
   ✓ EmailComposer > clears itself after sending 487ms
 ✓ components/overview/account-overview.test.tsx (3 tests) 2028ms
   ✓ AccountOverview — encabezado con órbita de redes > muestra el saludo, la bajada y los botones hacia bandeja y calendario 351ms
   ✓ AccountOverview — encabezado con órbita de redes > marca la órbita como decorativa con aria-hidden y renderiza las diez redes 1484ms
 ✓ components/settings/assignment-policies/assignment-policies-view.test.tsx (3 tests) 2147ms
   ✓ AssignmentPoliciesView > creates a policy, wrapping the body in assignment_policy 1026ms
   ✓ AssignmentPoliciesView > blocks submit when the fair-distribution limit is not positive 919ms
 ✓ components/contacts/contacts-view.test.tsx (4 tests) 2356ms
   ✓ ContactsView > filters the list when a company chip is clicked 1757ms
 ✓ components/settings/inboxes/channel-form.test.tsx (4 tests) 2146ms
   ✓ ChannelForm, creating an email inbox > draws a checkbox for a boolean field, not a text box 1709ms
 ✓ lib/api/fetcher.test.ts (6 tests) 20ms
 ✓ components/reports/reports-view.test.tsx (2 tests) 690ms
   ✓ ReportsView > renders live counters and summary metrics 436ms
 ✓ components/help-center/portal-detail-view.test.tsx (3 tests) 497ms
 ✓ components/settings/mcp-tokens/mcp-tokens-view.test.tsx (2 tests) 473ms
 ✓ components/settings/integrations/integration-app-view.test.tsx (2 tests) 432ms
 ✓ components/instagram/connect-capabilities-dialog.test.tsx (6 tests) 300ms
 ✓ lib/api/notifications.test.tsx (3 tests) 318ms
 ✓ components/reports/metric-chart.test.tsx (6 tests) 121ms
 ✓ components/instagram/autoreply-view.test.tsx (4 tests) 355ms
 ✓ lib/api/reports-gaps.test.ts (6 tests) 9ms
 ✓ lib/realtime/cable.test.ts (3 tests) 9ms
 ✓ components/settings/automation/automation-rules-view.test.tsx (3 tests) 195ms
 ✓ components/ui/tabs.test.tsx (3 tests) 205ms
 ✓ components/settings/macros/macros-view.test.tsx (4 tests) 189ms
 ✓ components/settings/profile/profile-view.test.tsx (1 test) 247ms
 ✓ components/conversations/conversation-participants.test.tsx (3 tests) 381ms
 ✓ components/settings/custom-attributes/custom-attributes-view.test.tsx (1 test) 188ms
 ✓ components/instagram/comments-panel.test.tsx (2 tests) 275ms
 ✓ components/conversations/message-composer-canned.test.tsx (2 tests) 253ms
 ✓ components/settings/csat/csat-view.test.tsx (1 test) 279ms
 ✓ components/campaigns/campaigns-view.test.tsx (1 test) 240ms
 ✓ app/(auth)/login/page.test.tsx (3 tests) 550ms
   ✓ LoginPage — a dónde va después de entrar > vuelve a la ruta interna de next con sus parámetros (el consentimiento OAuth) 330ms
 ✓ components/settings/agents/agents-view.test.tsx (1 test) 312ms
   ✓ AgentsView > lists agents with role + pending badge + email 305ms
 ✓ components/settings/inboxes/facebook-page-connect.test.tsx (2 tests) 897ms
   ✓ FacebookPageConnect > deja elegir entre varias Páginas y abre la bandeja creada 685ms
 ✓ components/settings/canned-responses/canned-responses-view.test.tsx (2 tests) 2064ms
   ✓ CannedResponsesView > sends the debounced search term to the backend 1782ms
 ✓ components/campaigns/campaign-analytics-panel.test.tsx (1 test) 179ms
 ✓ components/settings/integrations/integrations-view.test.tsx (1 test) 153ms
 ✓ lib/api/errors.test.ts (8 tests) 8ms
 ✓ components/conversations/conversation-actions.test.tsx (1 test) 258ms
 ✓ components/help-center/articles-panel.test.tsx (2 tests) 868ms
   ✓ ArticlesPanel search > sends the debounced query to the articles endpoint 504ms
   ✓ ArticlesPanel search > clears the search with the reset button 359ms
 ✓ components/settings/webhooks/webhooks-view.test.tsx (1 test) 182ms
 ✓ components/reports/traffic-heatmap.test.tsx (3 tests) 215ms
 ✓ components/shell/page-header.test.tsx (2 tests) 192ms
 ✓ components/help-center/portals-view.test.tsx (1 test) 877ms
   ✓ PortalsView > lists portals with archived badge and custom domain 848ms
 ✓ components/products/products-view.test.tsx (1 test) 1956ms
   ✓ ProductsView > lists products with price and status 1950ms
 ✓ lib/api/uploads.test.ts (3 tests) 65ms
 ✓ components/settings/agent-bots/agent-bots-view.test.tsx (1 test) 164ms
 ✓ components/conversations/channel-badge.test.tsx (5 tests) 133ms
 ✓ components/ui/button.test.tsx (3 tests) 161ms
 ✓ components/help-center/portal-form.test.tsx (1 test) 236ms
 ✓ components/agenda/week-utils.test.ts (4 tests) 29ms
 ✓ components/settings/notifications/push-toggle.test.tsx (1 test) 158ms
 ✓ components/settings/labels/labels-view.test.tsx (1 test) 232ms
 ✓ components/settings/teams/teams-view.test.tsx (1 test) 158ms
 ✓ app/privacidad/page.test.tsx (3 tests) 205ms
 ✓ lib/api/instagram.test.tsx (1 test) 129ms
 ✓ components/crm/crm-tabs.test.tsx (1 test) 127ms
 ✓ app/terminos/page.test.tsx (2 tests) 173ms
 ✓ components/reports/bot-metrics-cards.test.tsx (1 test) 70ms
 ✓ lib/time.test.ts (4 tests) 5ms
 ✓ lib/auth/schemas.test.ts (3 tests) 5ms
 ✓ app/eliminacion-de-datos/page.test.tsx (2 tests) 100ms

 Test Files  92 passed (92)
      Tests  400 passed (400)
   Start at  00:01:34
   Duration  27.07s (transform 8.94s, setup 96.78s, collect 91.94s, tests 65.64s, environment 275.77s, prepare 23.14s)
```
