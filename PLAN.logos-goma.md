# PLAN — Logos de goma para estirar

Pedido del dueño (2026-11-21): en las pantallas con espacio libre a los costados
(primero **Contactos**: la lista mide `max-w-4xl` y en pantallas anchas quedan
dos franjas vacías), poner logos de redes en 3D que el usuario puede **estirar
como goma**: mantiene el clic sobre el logo y arrastra, la zona agarrada se
estira siguiendo el puntero, y al soltar el logo vuelve a su forma **temblando
como gelatina**. La idea es desestresar y rellenar huecos, sin molestar.

Rama `feat/logos-goma`, worktree `C:\Users\Zeek\Desktop\AloStudio-logos`, sale de
`develop`. Lo hace un agente (Neon, en Antigravity) y lo revisa Claude contra
este documento.

## Lo que ya existe (partí de acá)

- `design/3d/build_logos.py`: script de Blender que lee los contornos de
  `frontend/components/ui/brand-icons.tsx` (Simple Icons, CC0), modela cada logo
  como un sólido gomoso y escribe `frontend/public/brand/3d/<nombre>.glb`,
  `design/3d/logos.blend` y `design/3d/preview.png`.
- Blender está en
  `C:\Users\Zeek\Apps\Blender\blender-5.4.0-alpha+main.f6d489196b75-windows.amd64-release\blender.exe`
  (no está en el PATH). Se corre sin ventana:
  `"<ruta>\blender.exe" -b -P design/3d/build_logos.py`.
- `frontend/components/brand/floating-logos.tsx` (`FloatingLogos`): carga three.js
  aparte (`import("three")`, `GLTFLoader`, `RoomEnvironment`), muestra esos GLB
  flotando y rebotando en el login, la Bandeja vacía y las páginas 404. Copiá su
  forma de cargar three, de iluminar y de liberar recursos; **no lo cambies**.
- `three` ya está en `package.json`.

## Reglas para el agente

- Trabajá **solo** en `C:\Users\Zeek\Desktop\AloStudio-logos`. No leas ni toques
  otros worktrees de AloStudio.
- **Solo frontend y `design/3d/`.** Nada de backend, `git push`, `ssh`, `.env*`,
  bases ni contenedores.
- **Sin librerías nuevas** de npm: three.js y CSS/React alcanzan. Si algo no se
  puede sin una librería, anotalo en **Estado** y no lo hagas.
- Commits chicos en `feat/logos-goma`, en español con el estilo del repo
  (`feat(ui): ...`, `feat(diseño): ...`), cada uno con todo el cambio que describe
  su mensaje, terminado en `Co-Authored-By: Antigravity <noreply@google.com>`.
- Sin modificadores de opacidad sobre colores del tema (`bg-primary/60`…):
  Tailwind 3 no los genera con nuestros colores. Usá los tokens CSS.
- Al final completá **Estado** con la salida real y completa de
  `npm run typecheck`, `npm run lint` y `npm test` en `frontend/`.

## 1. Los modelos en Blender

- Extendé `build_logos.py` (o un script hermano `build_rubber_logos.py`) para
  generar una **versión para estirar** de cada logo en
  `frontend/public/brand/3d/rubber/<nombre>.glb`: la misma forma y colores, pero
  con malla **más densa y pareja** en la cara frontal y los bordes (subdividida o
  remallada), para que se deforme suave sin quebrarse. Cuidá el peso: **menos de
  ~250 KB por archivo** (Draco no: no hay decodificador sin librería nueva).
- Empezá por **Facebook (la «f»)**, **Instagram** y **WhatsApp**. Si salen bien,
  sumá TikTok y Telegram.
- Renderizá `design/3d/rubber-preview.png` con los logos nuevos.
- Los `.blend` generados no se suben (ya están fuera del repo); sí el script, los
  GLB y el preview.

## 2. El componente `RubberLogos`

`components/brand/rubber-logos.tsx`, cargado con `next/dynamic` (`ssr: false`)
o con los `import()` de three como `FloatingLogos`.

- **Estirar:** `pointerdown` sobre un logo (raycast) toma el punto agarrado;
  mientras se arrastra, los vértices cerca de ese punto se desplazan hacia el
  puntero con caída suave (gaussiana según distancia al punto agarrado) y el
  resto del logo acompaña poco. Límite de estiramiento (~1,5 veces el tamaño del
  logo) con resistencia creciente, para que nunca se rompa ni se dé vuelta.
  `setPointerCapture` para no perder el arrastre al salir del canvas. Mouse y
  touch.
- **Soltar:** cada vértice vuelve a su posición con un **resorte amortiguado**
  (tiembla 2–4 veces y para en ~0,8–1,2 s), como gelatina. Un leve squash del
  logo entero al soltar suma.
- **Física aparte y probada:** la cuenta del resorte y de la caída en funciones
  puras (`lib/rubber-physics.ts` o similar) con pruebas en vitest.
- **Costo:** un solo canvas WebGL por franja (no uno por logo). El loop de
  render **solo corre mientras se arrastra o tiembla**; quieto, no dibuja. Pausar
  si la pestaña está oculta. Liberar geometrías, materiales y renderer al
  desmontar.
- Quietos, los logos pueden flotar apenas (un balanceo lento con CSS o un frame
  cada tanto), pero sin gastar CPU de forma continua.
- Cursor `grab` / `grabbing` sobre los logos.
- `aria-hidden`, sin foco, fuera del orden de tabulación. Es decoración.
- `prefers-reduced-motion: reduce`: logos quietos, sin temblor (se pueden
  estirar y vuelven al instante, o no se monta).

## 3. Dónde van

- **Contactos** (`components/contacts/contacts-view.tsx`): una franja a cada
  lado de la lista, **solo cuando sobra lugar** (por ejemplo, desde `2xl`, o
  midiendo con `ResizeObserver` que cada franja tenga ≥ 180 px). En pantallas
  chicas no aparece ni carga three.
- Nunca encima de la lista, los filtros ni los botones; no corre el contenido
  de lugar.
- Dejá el componente reutilizable (recibe qué logos mostrar) y anotá en
  **Estado** otras pantallas con huecos parecidos donde se podría usar, sin
  ponerlo ahí todavía.

## 4. Cómo lo vas a probar

- `npm run dev` en `frontend/` y abrir Contactos con una ventana ancha
  (≥ 1600 px): estirar cada logo, soltar, ver el temblor; achicar la ventana y
  ver que desaparecen.
- Dejá en **Estado** una captura (`design/3d/rubber-demo.png`) con un logo
  estirado.

## Estado

(Lo completa el agente.)
