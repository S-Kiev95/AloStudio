# Propuesta de integración: Anime.js v4 en AloStudio

> **Estado:** Propuesta lista para aprobación del dueño (sin cambios de código todavía).
> **Guía base:** `docs/design-neon/DESIGN.md` (*The Ignition Rule* + *Excepción: el cartel de la marca*) y `frontend/DESIGN-SYSTEM.md`.

---

## 1. Nota sobre la skill de `hyperframes`

Al ejecutar el comando pedido:

```bash
npx skills add https://github.com/heygen-com/hyperframes --skill animejs
```

El repositorio `heygen-com/hyperframes` se clonó correctamente pero actualmente lista 15 skills reorganizadas (`figma`, `hyperframes`, `hyperframes-cli`, `hyperframes-registry`, `media-use`, `remotion-to-hyperframes`, `reverse-any-video`, `slideshow`, `style-sampling`, `captions-overlay`, `changelog-video`, `cut-the-curve`, `motion-doctrine`, `oversized-cursor`, `seam-craft`) y devolvió `No matching skills found for: animejs`.

Para la implementación usaremos directamente la API oficial modular de **Anime.js v4** (`animejs` v4.x: `animate`, `createTimeline`, `stagger`, `createScope`, `waapi`, `spring`), con imports nombrados *tree-shakeable* y `createScope()` para limpieza automática en desmontajes de React y manejo nativo de `prefers-reduced-motion`.

---

## 2. Principios de movimiento en AloStudio

Antes de sumar animaciones, respetamos las reglas de `docs/design-neon/DESIGN.md`:

1. **The Ignition Rule:** la luz enciende **una sola vez** (`360 ms`, curva `cubic-bezier(0.16, 1, 0.3, 1)`), las transiciones entre estados toman `180–220 ms` y **nada parpadea ni hace bucles** (salvo la excepción explícita del cartel `AloStudio` en tema oscuro).
2. **Product Principle #2:** *"Fast daily operation beats showmanship inside the app; expression lives in identity details, not in friction."* Ninguna animación puede frenar a un operador que atiende 40 chats por hora.
3. **Accesibilidad total (`prefers-reduced-motion: reduce`):** mediante un helper central `useNeonScope()` basado en `createScope({ mediaQueries: { reduced: '(prefers-reduced-motion: reduce)' } })`, si `reduced` es `true` las animaciones se saltan (`duration: 0` o no se disparan) y los elementos aparecen en su estado final de inmediato.
4. **Rendimiento GPU-only:** animamos `transform` y `opacity` (y `box-shadow` solo en igniciones puntuales de 1 elemento), nunca `width`/`height`/`top`/`left` en listas largas.

---

## 3. Dónde suma Anime.js v4 (ordenado por valor visual y UX)

### A. Login con agujero negro (hero cinematográfico)
- **Dónde:** `frontend/app/(auth)/layout.tsx`, `frontend/app/(auth)/login/page.tsx` y `frontend/components/brand/floating-logos.tsx`.
- **Qué aporta Anime.js v4:** `createTimeline()` sincroniza con precisión de milisegundos las 4 fases (fractura de campos con `stagger()`, colapso de la tarjeta a esfera negra, señal de progreso hacia Three.js para el disco de acreción + estiramiento "chicle" de los logos 3D, y caída de cámara final en `2.6 s`).
- **Detalle completo y prototipo:** ver [`propuesta-login-agujero-negro.md`](./propuesta-login-agujero-negro.md) y [`prototipo-agujero-negro.html`](./prototipo-agujero-negro.html).

### B. Encendido neón unificado (cartel `AloStudio`, pestañas y fila activa)
- **Dónde:**
  - `frontend/components/brand/neon-wordmark.tsx` (actualmente orquestado con ~200 líneas de `setTimeout` manuales + `Map` de estados de React en cada paso).
  - `frontend/components/shell/sidebar-nav.tsx` (fila activa `.lit-tube-ignite`).
  - `frontend/components/ui/tabs.tsx` (tubo de `2px` bajo la pestaña activa).
- **Qué aporta Anime.js v4:**
  - En **`NeonWordmark`**: reemplazar la máquina de timers manuales por un `createTimeline()` determinista por escena (`breathe`, `sequential`, `last-o`, `random-beat`, `normal`) con `stagger(65)` para el encendido inicial y pausa/reanudación nativa con `timeline.pause()` / `timeline.revert()` cuando cambia `document.hidden`, el tema o `prefers-reduced-motion`. Queda el código a la mitad, sin re-renders de React por cada letra y respetando exactamente WCAG 2.3.1 (<= 3 destellos/s).
  - En **`Tabs` / `NavTabs`**: deslizar suavemente el tubo cobalto de `2px` desde la pestaña anterior a la nueva (`180 ms`, `outExpo`) en vez de aparecer de golpe, con un micro-encendido al llegar.

### C. Entrada escalonada de paneles y tarjetas en Inicio y CRM
- **Dónde:**
  - `frontend/components/overview/account-overview.tsx` (4 tarjetas "Ahora mismo" + 7 KPIs "Últimos 7 días" + gráfico y accesos rápidos).
  - `frontend/components/crm/opportunities-view.tsx` (columnas del embudo Kanban al cargar un pipeline).
  - `frontend/components/publications/media-library-view.tsx` (grilla de archivos al cargar).
- **Qué aporta Anime.js v4:**
  - Entrada sutil de una sola vez al montar (`opacity: [0, 1]`, `translateY: [8, 0]`, `duration: 280`, `delay: stagger(35, { from: 'first' })`, `ease: 'outExpo'`).
  - Cap estricto de `delay` máximo de `240 ms` para que listas grandes nunca se sientan lentas.
  - En **Inicio**: contador animado (`animate(obj, { val: target, round: 1, duration: 420 })`) solo en el primer render de los números de "Ahora mismo", manteniendo `tabular-nums` para cero salto de layout.

### D. Entrada y respuesta táctil de listas, modales y cajón móvil
- **Dónde:**
  - `frontend/components/shell/dashboard-shell.tsx:203-233` (cajón lateral móvil — hoy aparece de golpe sin transición).
  - Modales `<dialog>` (`appointment-dialog.tsx`, `opportunity-dialog.tsx`, `close-dialog.tsx`, `merge-dialog.tsx`, `publication-detail-dialog.tsx`) y el futuro `ConfirmDialog` compartido que reemplaza los 47 `window.confirm()`.
  - Popovers del topbar (`notification-bell.tsx`, `help-button.tsx`, `account-switcher.tsx`, `agent-menu.tsx`).
  - `frontend/components/conversations/conversation-list.tsx` (solo cuando entra un mensaje/conversación nueva en tiempo real por Cable: un destello breve de borde cobalto `360 ms` una sola vez, siguiendo *The Ignition Rule*).
- **Qué aporta Anime.js v4:**
  - Cajón móvil: slide desde la izquierda (`translateX: ['-100%', '0%']`, `220 ms`, `outExpo`) + fade del velo oscuro.
  - Modales y popovers: entrada sutil (`opacity: [0, 1]`, `scale: [0.97, 1]`, `translateY: [4, 0]`, `180 ms`, `outExpo`) usando `waapi.animate` (API liviana de Anime.js v4 sobre Web Animations API).

### E. Microinteracciones del Agente IA (naranja electrodo)
- **Dónde:** `frontend/components/agent/agent-chat-view.tsx` y `frontend/components/conversations/writing-assist.tsx`.
- **Qué aporta Anime.js v4:**
  - Entrada suave de cada burbuja nueva del chat y de `PendingActionCard` (`translateY: [6, 0]`, `opacity: [0, 1]`, `220 ms`).
  - Indicador de "Pensando…" con tres puntos escalonados (`stagger(120)`) en naranja electrodo (`--neon-electrode`) en lugar de un texto `animate-pulse` genérico.

---

## 4. Dónde **NO** usar Anime.js

- **Nunca** en cada tecla ni al scrollear listas de mensajes o tablas densas (Contactos, Reportes, Conversaciones viejas).
- **Nunca** en hovers cotidianos de botones, inputs o filas de tabla (CSS `transition` de `180–220 ms` es más simple y rápido).
- **Nunca** en bucles decorativos fuera de `NeonWordmark` y `NetworkOrbit` (que ya están explícitamente aprobados).
- **Nunca** en tema claro para brillos de neón (solo movimiento geométrico sutil si no hay `reduced-motion`).

---

## 5. Arquitectura propuesta (mínimo peso y 100 % testeable)

1. Instalar únicamente `animejs` (`^4.0.0`) en `frontend/package.json` (cero librerías de UI).
2. Crear un módulo pequeño `frontend/lib/motion/neon-motion.ts`:
   - Curvas estándar del sistema: `NEON_EASE = "cubicBezier(0.16, 1, 0.3, 1)"`, `NEON_IGNITE_MS = 360`, `NEON_ENTER_MS = 220`.
   - Hook `usePrefersReducedMotion()` y wrapper `useNeonScope(rootRef, setup, deps)` sobre `createScope()` de Anime.js v4 que:
     - desactiva automáticamente las animaciones si `prefers-reduced-motion: reduce`;
     - hace `scope.revert()` en el cleanup de React (cero leaks ni warnings en StrictMode / Vitest).
3. En Vitest (`jsdom`), `createScope` funciona limpio o se salta vía `matchMedia("(prefers-reduced-motion: reduce)")` en tests unitarios, garantizando que toda la suite existente siga en verde.
