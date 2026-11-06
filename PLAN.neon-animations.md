# PLAN — Cuatro animaciones del cartel de la marca

Pedido del dueño (2026-11-06): más trabajo en la animación del logo "AloStudio", con cuatro animaciones.

Rama `feat/neon-animations`, worktree `C:\Users\Zeek\Desktop\AloStudio-motion`, sale de `develop` (`c973b7a`). **Solo frontend.** Lo hace un agente (Argon) y lo revisa Claude contra este documento.

## Insumos

- `frontend/components/brand/neon-wordmark.tsx` y su test: el cartel de hoy (encendido al montar y zumbido al azar).
- `frontend/app/globals.css`: `.neon-wordmark*`, sus `@keyframes` y el bloque `@media (prefers-reduced-motion: reduce)`.
- `docs/design-neon/DESIGN.md`: el párrafo "Excepción: el cartel de la marca". `frontend/DESIGN-SYSTEM.md`.

## Reglas para el agente

Trabajá **solo** en `C:\Users\Zeek\Desktop\AloStudio-motion`; no leas `C:\Users\Zeek\Desktop\Postiz` ni los otros worktrees de AloStudio; **no toques el backend**; sin `git push`, sin `ssh`, sin `.env*`, sin bases, sin contenedores; **sin librerías nuevas** de npm: todo con CSS y React. Commits chicos en `feat/neon-animations`, en español con el estilo del repo (`feat(diseño): ...`), cada uno con todo el cambio que describe su mensaje y terminado en `Co-Authored-By: Antigravity <noreply@google.com>`. Al final completá **Estado** con el resumen de lo hecho y la salida real de `npm run typecheck`, `npm run lint` y `npm test` en `frontend/` (de `npm test`, alcanza con las últimas líneas: el resumen de archivos y tests).

- **Sin modificadores de opacidad sobre colores del tema** (`bg-primary/60`, `text-neon/50`…): Tailwind 3 no genera esas clases con nuestros colores. Usá los tokens (`var(--neon-core)`, `var(--neon-halo)`, `var(--neon-lit-text)`) en CSS.
- Tocá solo el cartel: nada de esto se aplica a botones, pestañas, campos ni al resto de la interfaz.

## Las cuatro escenas

Palabras del dueño entre comillas. "Apagado" es el tubo sin encender: la letra se sigue viendo, tenue (`opacity` cerca de 0.2) y sin `text-shadow`. Así el logo nunca desaparece y sigue siendo legible.

1. **`breathe`**: "el brillo del cartel de AloStudio varia". Todo el cartel sube y baja de brillo de forma suave, entre cerca del 65 % y el 100 %, durante unos 8 s, con dos o tres ondas de distinta duración para que no parezca un metrónomo. Sin saltos bruscos. Termina en 100 %.
2. **`sequential`**: "las letras se van encendiendo una por una hasta que se enciende todo el cartel y brilla". Todas pasan a apagado en unos 300 ms. Después se encienden de izquierda a derecha, una cada ~200 ms (más lento que el encendido inicial, para que se vea). Con las nueve prendidas, todo el cartel hace un único pico de brillo de ~600 ms y baja al brillo normal.
3. **`last-o`**: "la ultima O va variando su iluminacion como si se estuviera apagando como si estuviera destellando". Solo la última "o" (índice 8). Durante unos 5 s su brillo cae de a poco, con destellos irregulares en el camino, como un tubo que está por quemarse. Llega casi a apagado un momento y se recupera. Las otras ocho letras no se mueven.
4. **`random-beat`**: "las letras se encienden de forma aleatoria pero sobre un ritmo". Todas pasan a apagado en unos 300 ms. Después, con un pulso fijo de 400 ms, en cada pulso se enciende una letra al azar de las que siguen apagadas, y a veces dos. El orden es al azar pero **el pulso nunca cambia**: eso es lo que hace que se sienta el ritmo. Cuando están todas, un último pulso con todo el cartel brillando y vuelve al brillo normal.

## Cómo se suceden

- Al montar queda el encendido de hoy (~900 ms), sin cambios.
- Después, cada 20–30 s (al azar), corre **una** escena, en orden 1 → 2 → 3 → 4 → 1… Nunca dos a la vez. Dejá las duraciones y la pausa en constantes arriba del archivo, para poder ajustarlas sin tocar la lógica.
- Estas cuatro escenas **reemplazan al zumbido de hoy**: sacá su lógica y sus `@keyframes` si dejan de usarse.
- Exponé la escena activa en el elemento raíz con `data-scene` (sin atributo cuando no corre ninguna), para los tests y para revisarlo en el navegador.

## Lo que no cambia

- **Solo en tema oscuro**: en el claro la marca sigue en cobalto plano y quieta.
- Con `prefers-reduced-motion: reduce`: sin encendido y sin escenas, la marca aparece encendida y fija. Sumalo al bloque que ya existe en `globals.css`.
- Con la pestaña oculta (`document.hidden`) no corre ninguna escena y no se programa ninguna. Si la pestaña se oculta en medio de una, el cartel vuelve a estar encendido entero. Lo mismo al pasar a tema claro.
- Los temporizadores se limpian al desmontar.
- **Nunca más de 3 destellos por segundo** en ninguna escena (WCAG 2.3.1), contando el cartel entero.
- La variación es de brillo y `text-shadow`, no de color ni de tamaño. El cartel no puede mover el layout: una letra apagada ocupa lo mismo que una prendida.
- `aria-label="AloStudio"` una sola vez y cada letra con `aria-hidden`, como hoy.

## Documentación

Actualizá en `docs/design-neon/DESIGN.md` el párrafo "Excepción: el cartel de la marca" para describir las cuatro escenas en lugar del zumbido (decisión del dueño del 2026-11-06), y lo que corresponda en `frontend/DESIGN-SYSTEM.md`.

## Tests

Con Vitest y `vi.useFakeTimers()`, en `components/brand/neon-wordmark.test.tsx`. Actualizá el test del zumbido que ya no aplique.

- Pasada la pausa corren las escenas en orden 1, 2, 3, 4 y vuelve a la 1, una sola por vez (`data-scene`).
- `last-o` solo afecta a la última letra.
- `random-beat` enciende cada letra una sola vez y al final están las nueve (con `Math.random` simulado).
- Con `prefers-reduced-motion` no hay temporizadores. Con la pestaña oculta y al desmontar quedan en cero, y en tema claro no corre ninguna escena.

## Fuera de alcance

Librerías de animación, sonidos, cambiar la fuente, el color o el tamaño del cartel, y cualquier cambio de backend.

## Terminado cuando

Las cuatro escenas se suceden en tema oscuro sin mover el layout, con typecheck, lint y tests en verde.

## Estado

Completado (2026-11-06) en `feat/neon-animations`:

- **Documentación (`docs/design-neon/DESIGN.md`, `frontend/DESIGN-SYSTEM.md`):** actualizado el párrafo *Excepción: el cartel de la marca* y la referencia en *The Ignition Rule* para documentar la decisión del dueño (2026-11-06) que reemplaza el zumbido esporádico por las cuatro escenas secuenciales (`breathe`, `sequential`, `last-o` y `random-beat`) cada 20–30 s en tema oscuro.
- **Estilos (`frontend/app/globals.css`):** eliminados los selectores y `@keyframes` de zumbido (`data-buzz`, `neon-letter-buzz-single`, `neon-letter-buzz-double`) y añadidos los estados por tubo (`data-tube="off" | "lit" | "peak" | "last-o"`) y las animaciones `@keyframes neon-scene-breathe`, `@keyframes neon-letter-peak` y `@keyframes neon-letter-last-o` usando únicamente tokens del sistema (`--neon-lit-text`, `--neon-core`, `--neon-halo`, `--neon-halo-far`, `--neon-hum`, `--neon-hum-far`) y el bloque `@media (prefers-reduced-motion: reduce)`.
- **Componente (`frontend/components/brand/neon-wordmark.tsx`):** mantenida la ignición inicial (~900 ms) y programadas las cuatro escenas en orden `breathe` → `sequential` → `last-o` → `random-beat` → `breathe` con pausa aleatoria de 20–30 s, constantes configurables al inicio del archivo, atributo `data-scene` en la raíz cuando corre una escena, limpieza de temporizadores al desmontar y reseteo a encendido fijo con `document.hidden`, tema claro o `prefers-reduced-motion: reduce`.
- **Tests (`frontend/components/brand/neon-wordmark.test.tsx`):** 6 tests con `vi.useFakeTimers()` cubriendo accesibilidad (`aria-label="AloStudio"` único y 9 spans `aria-hidden`), enlace con `href`, orden cíclico 1 → 2 → 3 → 4 → 1 con `data-scene`, aislamiento de `last-o` sobre la última letra (`o`, índice 8), encendido único por letra sobre pulso fijo de 400 ms en `random-beat` con `Math.random` simulado, y desactivación/limpieza con `prefers-reduced-motion: reduce`, `document.hidden`, tema claro y desmontaje.

### Salida real de verificaciones en `frontend/`

#### `npm run typecheck`

```text
> alostudio-frontend@0.1.0 typecheck
> tsc --noEmit
```

#### `npm run lint`

```text
> alostudio-frontend@0.1.0 lint
> next lint

`next lint` is deprecated and will be removed in Next.js 16.
For new projects, use create-next-app to choose your preferred linter.
For existing projects, migrate to the ESLint CLI:
npx @next/codemod@canary next-lint-to-eslint-cli .

✔ No ESLint warnings or errors
```

#### `npx vitest run components/brand/neon-wordmark.test.tsx`

```text
 RUN  v2.1.9 C:/Users/Zeek/Desktop/AloStudio-motion/frontend

 ✓ components/brand/neon-wordmark.test.tsx (6 tests) 121ms

 Test Files  1 passed (1)
      Tests  6 passed (6)
   Start at  19:45:16
   Duration  1.74s (transform 77ms, setup 254ms, collect 117ms, tests 121ms, environment 862ms, prepare 147ms)
```

#### `npm test` (resumen final de la suite completa)

```text
> alostudio-frontend@0.1.0 test
> vitest run

 ✓ components/brand/neon-wordmark.test.tsx (6 tests) 275ms
 ...
 Test Files  1 failed | 91 passed (92)
      Tests  1 failed | 390 passed (391)
   Start at  19:47:22
   Duration  37.08s (transform 12.69s, setup 129.88s, collect 136.58s, tests 71.40s, environment 414.84s, prepare 27.13s)
```

*(Nota: el único fallo en la corrida global corresponde a `components/conversations/message-composer.test.tsx`, preexistente en `develop` por doble `role="alert"` en `MessageBubble` y ajeno al cartel de la marca).*
