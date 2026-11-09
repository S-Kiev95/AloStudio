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
