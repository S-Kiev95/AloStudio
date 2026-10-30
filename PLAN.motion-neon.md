# PLAN — Cartel de neón y movimiento

Pedido del dueño (2026-10-30): más vida en el frontend. La marca "AloStudio" brilla como un cartel de neón de verdad (letras que se encienden, alguna que titila, variaciones de brillo) y las páginas entran con una transición en vez de aparecer de golpe.

Rama `feat/motion-neon`, worktree `C:\Users\Zeek\Desktop\AloStudio-motion`, sale de `main` (`e70dc79`). **Solo frontend.** Lo hace un agente (Argon) y lo revisa Claude contra este documento.

## Insumos

- `docs/design-neon/DESIGN.md` (sobre todo "The Ignition Rule" y la sección de movimiento) y `frontend/DESIGN-SYSTEM.md`.
- `frontend/app/globals.css`: `.neon-wordmark`, `.neon-sign`, `.lit-tube-ignite`, `@keyframes lit-ignite` y el bloque `@media (prefers-reduced-motion: reduce)`.
- La marca aparece en `components/shell/dashboard-shell.tsx` (menú lateral), `app/(auth)/layout.tsx` (login y demás) y `app/auth/sso/page.tsx`.

## Reglas para el agente

Las mismas de `PLAN.publishing-ui.md`: trabajá **solo** en `C:\Users\Zeek\Desktop\AloStudio-motion`; no leas `C:\Users\Zeek\Desktop\Postiz` ni los otros worktrees de AloStudio; **no toques el backend**; sin `git push`, sin `ssh`, sin `.env*`, sin bases, sin contenedores; **sin librerías nuevas** de npm (nada de Framer Motion: todo con CSS y React; si algo no se puede sin una librería, anotalo en **Estado** y no lo hagas). Commits chicos en `feat/motion-neon`, en español con el estilo del repo (`feat(diseño): ...`), cada uno con todo el cambio que describe su mensaje y terminado en `Co-Authored-By: Antigravity <noreply@google.com>`. Commiteá seguido. Al final completá **Estado** con la salida real y completa de `npm run typecheck`, `npm run lint` y `npm test` en `frontend/`.

## Notas de las revisiones anteriores (cumplilas)

- **Sin modificadores de opacidad sobre colores del tema** (`bg-primary/60`, `text-neon/50`…): Tailwind 3 no genera esas clases con nuestros colores. Usá los tokens (`var(--neon-core)`, `var(--neon-halo)`…) en CSS u `opacity-*`.
- Todo movimiento se apaga con `prefers-reduced-motion: reduce` (sumalo al bloque que ya existe en `globals.css`).
- Cada commit tiene que contener todo el cambio que describe su mensaje.

## 1. Excepción a la regla de encendido (decisión del dueño)

"The Ignition Rule" dice que nada titila ni se repite. El dueño pidió que la **marca** sí lo haga, así que es una excepción **solo** para el logo "AloStudio": botones, pestañas, campos y el resto de la interfaz siguen como están. Agregá a `docs/design-neon/DESIGN.md`, junto a esa regla, un párrafo "Excepción: el cartel de la marca" que diga qué se permite (lo de la sección 2) y que lo decidió el dueño el 2026-10-30.

## 2. El cartel "AloStudio"

- Un componente `components/brand/neon-wordmark.tsx` (`NeonWordmark`, con `className` y `as`/`href` opcionales si hace falta) que reemplace el texto suelto en los tres lugares. Cada letra en su `<span>` con `aria-hidden`, y el conjunto con `aria-label="AloStudio"` para que un lector de pantalla diga la palabra una vez.
- **Encendido** al montar (una vez): las letras se prenden de izquierda a derecha en ~900 ms en total, cada una con uno o dos parpadeos cortos antes de quedar firme (como un tubo que arranca).
- **Zumbido** después: cada 15–45 s (al azar), **una** letra al azar baja el brillo y vuelve en 150–400 ms, a veces con un parpadeo doble; muy de vez en cuando (≈ 1 de cada 4 veces) dos letras seguidas. Nunca más de 3 destellos por segundo (WCAG 2.3.1). La variación es de brillo y `text-shadow`, no de color ni de tamaño.
- **Solo en tema oscuro**: en el claro la marca es cobalto plano y se queda quieta (como hoy).
- Con `prefers-reduced-motion: reduce`: ni encendido ni zumbido, la marca aparece encendida y fija.
- Los temporizadores se limpian al desmontar; con la pestaña oculta (`document.hidden`) no se programa ningún zumbido.
- Que no cambie el tamaño ni el lugar del logo: no puede mover el layout al animar.

## 3. Entrada de las páginas

- `app/accounts/[accountId]/template.tsx` (el `template` de Next se vuelve a montar en cada navegación) que envuelva las páginas en un `div` con una entrada de 220 ms: de `opacity: 0; transform: translateY(6px)` a su lugar, curva `cubic-bezier(0.16, 1, 0.3, 1)` (la de la regla de encendido). Sin salida animada.
- Que no afecte el menú lateral ni la barra superior (están en el `layout`, que no se vuelve a montar).
- Con `prefers-reduced-motion`, sin animación.
- Las páginas de `(auth)` (login, etc.): la tarjeta entra con la misma curva al cargar (una vez).

## 4. Tests

Con Vitest como el resto: `NeonWordmark` expone "AloStudio" una sola vez a lectores de pantalla (`getByLabelText`/`getByRole`), tiene una letra por `span`, y con `matchMedia("(prefers-reduced-motion: reduce)")` en `true` no programa temporizadores (usá `vi.useFakeTimers()`); el `template` renderiza a sus hijos. Actualizá los tests existentes que busquen el texto "AloStudio" si dejan de encontrarlo.

## Fuera de alcance

Librerías de animación, View Transitions experimentales de React/Next, animar listas o tarjetas, sonidos, y cualquier cambio de backend.

## Terminado cuando

Lo de las secciones 1 a 4 con typecheck, lint y tests en verde, y la marca se enciende y zumba en tema oscuro sin mover el layout.

## Estado

(Lo completa el agente al terminar.)
