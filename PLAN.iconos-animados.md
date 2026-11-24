# PLAN — Íconos animados

Pedido del dueño (2026-11-24): animar los íconos propios de la app. Ejemplos que
dio: en el **reloj de arena** la arena cae y, cuando termina, se da vuelta y
empieza de nuevo; en la **bandeja** cae una carta; en el **reloj** giran las
agujas; en **CRM** la personita llega caminando. «Y así con cada uno»: algunos
(los relojes) en bucle constante, otros solo al pasar el mouse.

**El dueño lo quiere ver antes de pasarlo a develop**: rama
`feat/iconos-animados`, worktree `C:\Users\Zeek\Desktop\AloStudio-iconos`, sale
de `develop`. Lo hace Neon (Antigravity) y lo revisa Claude contra este
documento; después el dueño lo prueba.

## Lo que hay

- `frontend/components/shell/app-icons.tsx`: el set propio de íconos (SVG 24×24,
  línea redondeada con un relleno suave detrás, todo en `currentColor`). Los usa
  el menú lateral (`components/shell/sidebar-nav.tsx`, `dashboard-shell.tsx`) e
  Inicio (`components/overview/account-overview.tsx`: tarjetas «Ahora mismo» con
  `InboxIcon`, `ClockIcon`, `UnassignedIcon`, `HourglassIcon`, y accesos rápidos).
- Íconos del set: `HomeIcon`, `CalendarIcon`, `AgentIcon`, `StatsIcon`,
  `MediaIcon`, `InboxIcon`, `PeopleIcon`, `BookIcon`, `MegaphoneIcon`,
  `BarsIcon`, `ClockIcon`, `UnassignedIcon`, `HourglassIcon`, `MessagesIcon`
  (más los de marca de Instagram y WhatsApp, y los de plegar el menú).
- Guías: `frontend/DESIGN-SYSTEM.md` y `docs/design-neon/DESIGN.md` (ojo con
  «The Ignition Rule»: lo que se mueve tiene que tener motivo; acá el dueño lo
  pide expresamente para estos íconos).

## Qué hacer

1. **Una animación por ícono**, dibujada en el mismo SVG (partes con `<g>` y
   clases), con **CSS** (keyframes en `globals.css` o en un módulo) y sin
   librerías. Que se lea a 20–24 px: pocas partes en movimiento, curvas suaves.
   - **En bucle constante** (solo donde el dueño lo pidió o es «tiempo que pasa»):
     - `HourglassIcon`: la arena baja de arriba a abajo; al terminar, el reloj
       gira 180° y vuelve a empezar (ciclo de ~4–6 s, calmo).
     - `ClockIcon`: las agujas giran (minutero visible, horario lento).
   - **Al pasar el mouse** (sobre el ícono o sobre su fila/tarjeta: el `group`
     del enlace del menú o de la tarjeta de Inicio), una vez, ~0,6–1 s:
     - `InboxIcon`: cae una carta dentro de la bandeja.
     - `PeopleIcon` (CRM): la personita entra caminando desde un costado.
     - `UnassignedIcon`: la persona se asoma o la «x» se sacude.
     - `CalendarIcon`: pasa una hoja o se marca un día.
     - `AgentIcon`: las chispas titilan / se encienden.
     - `StatsIcon` y `BarsIcon`: las barras / la línea suben.
     - `MediaIcon`: la imagen aparece (sol que sale o montaña que sube).
     - `BookIcon` (Centro de ayuda): las páginas se abren.
     - `MegaphoneIcon` (Campañas): ondas de sonido salen del megáfono.
     - `MessagesIcon`: aparecen los puntitos de «escribiendo».
     - `HomeIcon`: se enciende la ventana o sale humo de la chimenea.
     - Instagram y WhatsApp: un pulso leve.
   - Si para alguno se te ocurre algo mejor y en el mismo espíritu, hacelo y
     anotalo en **Estado**.
2. **Cuándo se mueven**
   - Los de bucle: en Inicio, en las tarjetas de «Ahora mismo». En el menú
     lateral, el reloj de arena y el reloj **no** giran todo el tiempo (sería
     ruido): ahí solo al pasar el mouse. Hacelo con una prop (`animate="loop" |
     "hover" | "none"`) o una clase en el contenedor.
   - Al pasar el mouse sobre la fila del menú o la tarjeta, no solo sobre el
     dibujito. También con foco de teclado (`:focus-visible`).
   - El ícono del ítem **activo** del menú no se anima solo.
   - `prefers-reduced-motion: reduce`: todo quieto (sumalo al bloque que ya
     existe en `globals.css`).
   - Pausar los bucles cuando la pestaña no se ve no hace falta con CSS, pero que
     no haya JS corriendo en bucle.
3. **No cambiar** el tamaño, el trazo ni el aspecto en reposo de los íconos: quieto
   tiene que verse igual que hoy (salvo el reloj de arena, que muestra la arena).
   Siguen en `currentColor` para que el neón del menú aplique.
4. **Página de muestra** para que el dueño los vea juntos: una ruta solo de
   desarrollo, por ejemplo `app/dev/iconos/page.tsx` (que en producción dé 404,
   p. ej. con `process.env.NODE_ENV`), con cada ícono a 24 y a 48 px, en claro y
   oscuro, con su modo (bucle o hover) y su nombre.
5. **Pruebas** en vitest: que cada ícono siga renderizando, que la prop de modo
   ponga las clases correctas y que con `prefers-reduced-motion` no haya
   animación (al menos que la clase/atributo esté). Actualizá las pruebas del
   menú y de Inicio si cambia algo.

## Reglas

- Trabajá **solo** en `C:\Users\Zeek\Desktop\AloStudio-iconos`. Solo frontend.
- Nada de `git push`, `ssh`, `.env*`, bases ni contenedores. Sin librerías nuevas
  (nada de Framer Motion ni Lottie): SVG + CSS.
- Sin modificadores de opacidad sobre colores del tema (`bg-primary/60`…).
- Animaciones con `transform` y `opacity` (baratas para el navegador);
  `transform-box: fill-box` y `transform-origin` correctos para que giren sobre su
  centro.
- Commits chicos en español (`feat(ui): ...`), terminados en
  `Co-Authored-By: Antigravity <noreply@google.com>`.
- Revisalo en el navegador (`npm run dev` en `frontend/`; la página de muestra no
  necesita backend) y dejá capturas o un GIF/video corto en
  `docs/iconos-animados/`.
- Al final completá **Estado** con la salida real de `npm run typecheck`,
  `npm run lint` y `npm test` en `frontend/`, y la lista de cada ícono con su
  animación y su modo.

## Estado

(Lo completa el agente.)
