# Botón Enviar fuera del cuadro e íconos de Inicio más grandes

Pedido del dueño (2026-11-09), con capturas de CTC.

## 1. Bandeja: botón Enviar fuera del cuadro de texto

Hoy el botón redondo con el avión de papel está DENTRO del cuadro de texto
(`absolute right-2 top-1/2 -translate-y-1/2 rounded-full`), y el cuadro crece
con el texto. Al crecer se ve mal (botón flotando en el medio, scroll al lado).

El dueño quiere:
- El cuadro de texto ocupa todo el ancho, sin botón adentro (sacar el `pr-12`).
- El botón Enviar va FUERA del cuadro, abajo a la derecha, en la misma fila
  que los botones "Nota privada", "Respuestas rápidas" y el clip de adjuntar
  (esos quedan a la izquierda; Enviar a la derecha de esa fila).
- Se mantiene redondo (`rounded-full`), con solo el ícono del avión de papel,
  mismo color, `aria-label="Enviar"` y `title="Enviar"`, y el mismo
  comportamiento (deshabilitado sin texto ni adjuntos, estilo de nota privada
  cuando `isPrivate`).
- El cuadro sigue creciendo solo hasta ~6 líneas (efecto con
  `MAX_TEXTAREA_HEIGHT_PX`) y solo muestra scroll si el texto supera ese alto.
  Revisar que con Shift+Enter (líneas vacías) no aparezca scroll antes de tiempo.
- Con el botón fuera, el cuadro puede volver al padding normal del Textarea
  (quitar `py-[13px]`) si queda mejor; que una línea se vea prolija.

Archivos:
- `frontend/components/conversations/message-composer.tsx`
- `frontend/components/conversations/email-composer.tsx`: mismo criterio,
  botón Enviar fuera del cuadro, abajo a la derecha.

## 2. Inicio: íconos de "Ahora mismo" más grandes

En `frontend/components/overview/account-overview.tsx`, las tarjetas de
"Ahora mismo" (Abiertas, Sin atender, Sin asignar, Pendientes) tienen el ícono
en `h-5 w-5` junto a un número `text-2xl`. Se ven chicos: agrandarlos para que
acompañen al número (por ejemplo `h-7 w-7` u `h-8 w-8`, lo que quede mejor),
alineados verticalmente con el bloque número + etiqueta. Mismo estilo de línea
(`neon-nav`), sin cambiar colores. Solo esas tarjetas, no la lista de acciones.

## Reglas

- Respetar `frontend/DESIGN-SYSTEM.md`. No usar clases de opacidad tipo
  `bg-x/NN` sobre colores del tema (no generan CSS).
- No tocar backend ni otras pantallas.
- Actualizar los tests que fijen la posición o clases del botón si hace falta.
- Correr `npm run typecheck`, `npm run lint` y `npm test` en `frontend/` y que pasen.
- Commits en español, uno por punto:
  `fix(diseño): botón Enviar fuera del cuadro de texto, abajo a la derecha` y
  `fix(diseño): íconos de Ahora mismo más grandes en Inicio`.
- Al terminar, anotar al final de este archivo qué cambió y las salidas de las pruebas.
