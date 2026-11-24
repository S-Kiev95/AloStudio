# PLAN — Selector de idioma y desplegables con el estilo de la página

Pedido del dueño (2026-11-24): en el login, el selector de idioma abre una lista
nativa del sistema (fondo blanco, resaltado celeste de Windows) que no acompaña
el estilo oscuro y de neón de la página.

Rama `feat/selector-idioma`, worktree `C:\Users\Zeek\Desktop\AloStudio-idioma`,
sale de `develop`. Lo hace Neon (Antigravity) y lo revisa Claude contra este
documento.

## Qué hay hoy

- `frontend/components/shell/language-switcher.tsx`: un `<select>` nativo dentro
  de un `<label>` con estilo de vidrio; se usa en `app/(auth)/layout.tsx` (login,
  recuperar contraseña). Las `<option>` tienen `bg-surface-2 text-fg`, pero
  Windows y Chrome dibujan la lista con sus propios colores.
- `frontend/components/settings/profile/language-card.tsx`: el mismo elegido en
  Ajustes → Mi perfil.
- `frontend/components/ui/select.tsx`: el `<Select>` base (nativo) que usan ~40
  pantallas. `globals.css` ya pone `color-scheme: light` / `dark` por tema.
- Guías de diseño: `frontend/DESIGN-SYSTEM.md` y `docs/design-neon/DESIGN.md`.

## Qué hacer

1. **Componente nuevo `components/ui/listbox.tsx`** (sin librerías nuevas): un
   desplegable propio con el estilo de la página (vidrio, borde `border-glass`,
   fondo de superficie, opción activa y con foco resaltadas con los tokens de
   neón, sombra y esquinas como los menús que ya existen). Patrón de accesibilidad
   WAI-ARIA «select-only combobox»: botón con `role="combobox"`,
   `aria-expanded`, `aria-controls`, `aria-activedescendant`; lista con
   `role="listbox"` y opciones `role="option"` con `aria-selected`.
   - Teclado: Enter/Espacio/↓ abre, ↑/↓/Inicio/Fin mueven, Enter elige, Esc
     cierra y devuelve el foco, escribir letras salta a la opción, Tab cierra.
   - Mouse y touch; cierra al hacer clic afuera.
   - Se posiciona debajo (o arriba si no entra) sin salirse de la pantalla y por
     encima de todo (portal o `z-index` correcto; ojo con `view-transition-name`
     que crea contexto de apilamiento, ver `.vt-page-over-bar` en `globals.css`).
   - Cada opción puede llevar `lang` (para los nombres de idioma).
   - Claro y oscuro con los tokens del tema; `prefers-reduced-motion` sin
     animación de apertura.
2. **Usarlo en `language-switcher.tsx` y en `language-card.tsx`**, con el mismo
   comportamiento de hoy (cambiar la cookie en el login; guardar en el perfil en
   Ajustes).
3. **Arreglo general para los `<select>` nativos** que quedan: que la lista que
   abre el sistema siga el tema. Asegurar `color-scheme` correcto en el
   `<select>` (y en `option`/`optgroup` fondo y texto con los tokens del tema)
   para que en modo oscuro no salga blanca. No reemplaces los ~40 `<Select>` por
   el listbox: solo anotá en **Estado** cuáles convendría migrar después.
4. **Pruebas** en vitest del listbox (abrir, teclado, elegir, Esc, clic afuera,
   atributos ARIA) y que el selector de idioma cambie el idioma.

## Reglas

- Trabajá **solo** en `C:\Users\Zeek\Desktop\AloStudio-idioma`. Solo frontend.
- Nada de `git push`, `ssh`, `.env*`, bases ni contenedores. Sin librerías nuevas.
- Sin modificadores de opacidad sobre colores del tema (`bg-primary/60`…): usá
  los tokens CSS.
- Textos nuevos (si hay) en los 7 idiomas (`frontend/lib/i18n/messages/*`).
- Commits chicos en español (`feat(ui): ...`, `fix(ui): ...`), terminados en
  `Co-Authored-By: Antigravity <noreply@google.com>`.
- Revisalo en el navegador (`npm run dev` en `frontend/`, el login no necesita
  backend) en claro y en oscuro, y dejá capturas en `docs/selector-idioma/`.
- Al final completá **Estado** con la salida real de `npm run typecheck`,
  `npm run lint` y `npm test` en `frontend/`.

## Estado

(Lo completa el agente.)
