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

(Lo completa el agente.)
