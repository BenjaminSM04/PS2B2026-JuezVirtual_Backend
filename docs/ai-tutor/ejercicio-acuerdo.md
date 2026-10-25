# Ejercicio de acuerdo entre revisores (PB-04)

Objetivo, alcance y plantilla del ejercicio que completa los criterios de aceptación
pendientes de PB-04: «dos revisores pueden etiquetar el mismo ejemplo usando el
documento sin inventar campos» y «lista de decisiones o desacuerdos».

IMPORTANTE: este ejercicio no se ha ejecutado todavía con dos revisores reales.
Hasta que eso ocurra y se registren los resultados, PB-04 sigue abierta y ninguna
etiqueta queda aprobada. No se simularán coincidencias ni aprobaciones.

## Objetivo y alcance

- Comprobar que `docs/ai-tutor/guia-etiquetado.md` permite a dos personas etiquetar
  el mismo ejemplo de forma independiente y obtener resultados comparables.
- Detectar ambigüedades de la taxonomía (compilation, runtime, logic, complexity,
  concept, unknown) y de los tres niveles de pistas antes de apoyar PB-06, PB-07 y PB-09.
- Este ejercicio es un control de coherencia pedagógica; no sustituye al validador
  automático ni otorga estados de revisión a los archivos JSON.

## Requisitos previos y materiales

- Guía vigente: `docs/ai-tutor/guia-etiquetado.md` (contrato 1.0).
- Esquema ejecutable: `ai_tutor/dataset/schema.py`; enunciado de referencia:
  `docs/ai-tutor/esquema-ejemplo.json`.
- Validador: `python manage.py validate_tutor_examples docs/ai-tutor/ejemplos-positivos.json`
  (igual con `ejemplos-ambiguos.json`; los negativos deben fallar).
- Ejemplos: `docs/ai-tutor/ejemplos-positivos.json`, `ejemplos-ambiguos.json`,
  `ejemplos-negativos.json`.
- Dos revisores humanos distintos del autor de la guía y de los ejemplos.
- Un lugar único para registrar resultados: la plantilla de la sección «Plantilla de
  registro» de este documento.

## Instrucciones para los dos revisores

1. Cada revisor trabaja solo, sin ver la hoja del otro, y sin discutir previamente
   los criterios más allá de leer el mismo material de la lista previa.
2. Para cada ejemplo asignado, el revisor registra, usando solo campos existentes
   del contrato: category, concept, explanation, las tres pistas (concept,
   location, strategy) y uncertainty.confidence con su razón.
3. Está prohibido inventar campos, añadir categorías o subcategorías, y modificar
   los archivos JSON de ejemplos durante el ejercicio.
4. Si un ejemplo es imposible de etiquetar, se registra `unknown` con alternativas
   y confianza ≤ 0.5, que es la salida definida por la guía y el esquema.
5. No se marca ningún ejemplo como aprobado en el ejercicio: la aprobación es parte
   de PB-07 con autor, revisor y evidencia propios.

## Procedimiento reproducible y orden

1. Fijar la versión de guía y ejemplos (sección «Identificación de versión»).
2. Cada revisor lee por su cuenta la guía completa y el esquema de referencia.
3. Copiar la plantilla de la sección «Plantilla de registro» en un solo documento
   compartido; una fila por ejemplo y columna por revisor.
4. Etiquetar los ejemplos en este orden: 1) ejemplos-positivos (por orden de
   aparición), 2) ejemplos-ambiguos, 3) un volcado propio de ejemplos-negativos
   confirmando que falla el validador.
5. Ejecutar el validador con el conjunto completo de ejemplos positivos;
   registrar el resultado en la fila de control de la plantilla.
6. Solo después de que ambos revisores terminen, comparar hojas y abrir cada
   columna de coincidencia y desacuerdo.

## Reglas para no inventar campos ni desviar etiquetas

- Solo se escriben valores que el esquema acepta; el validador sirve de límite.
- Si se necesita un valor nuevo o un campo nuevo, se registra como desacuerdo o
  propuesta (no como validación), y se tramita en la guía, no en este ejercicio.
- Las etiquetas registradas son hipótesis de trabajo: ninguna queda aprobada sin
  el flujo de revisión de PB-07.

## Criterios de comparación (según el esquema real)

- **Coincidencia fuerte:** misma category, misma idea de concept (se tolera
  redacción distinta), pistas en progresión similar y confidence con diferencia
  ≤ 0.2 entre revisores.
- **Coincidencia parcial:** misma category pero distinto nivel de tercer pista o
  confidence con más diferencia; se registra y no bloquea.
- **Desacuerdo:** distinta category, o una de las pistas entrega una solución
  completa o contiene la corrección exacta (prohibición del nivel 3), o un
  revisor deseó campos inexistentes.

## Plantilla de registro

Copiar esta tabla (no rellenar aquí: usar el documento compartido del ejercicio).

| # | Archivo | example_id | Revisor | category | concept (resumen) | Pista 1/2/3 en progresión | confidence | ¿Deseó campos inexistentes? | Acuerdo | Nota / motivo |
|---|---------|-----------|---------|----------|--------------------|---------------------------|------------|-----------------------------|---------|----------------|
| 1 | ejemplos-positivos.json | ___ | Revisor A | | | | | | | |
| 1 | ejemplos-positivos.json | ___ | Revisor B | | | | | | | |
| 2 | … | ___ | A / B | | | | | | | |

Fila de control del validador:

| Revisor | Comando ejecutado | Resultado esperado | Resultado observado |
|---------|-------------------|--------------------|---------------------|
| A | validate_tutor_examples ejemplos-positivos.json | X ejemplos válidos | |
| A | validate_tutor_examples ejemplos-negativos.json | error intencional | |
| B | (repetir las dos líneas) | | |

## Registro de desacuerdos, resolución y justificación

Un desacuerdo se anota con:

1. example_id y campo en conflicto.
2. Etiqueta y razón de cada revisor (una línea cada uno).
3. Estado final según la tabla de decisiones iniciales o pendientes.
4. Evidencia que resuelve el desacuerdo (contraejemplo, diagnóstico sintético o
   medición): no se resuelve por jerarquía ni por antíguedad.
5. Enlace a la conversación, acta o commit que contiene la decisión real.

Mientras el desacuerdo siga abierto, el ejemplo permanece con `unknown` o en
estado `review`; nunca se aprueba.

## Decisiones iniciales (del autor de la guía)

Son las decisiones tomadas al escribir el contrato 1.0, aún sin desacuerdos
reales registrados:

- `unknown` es una categoría genuina, no un cajón de mala praxis.
- No todo `WA` se convierte automáticamente en `logic`.
- El límite entre memoria por crecimiento (`complexity`) y memoria por acceso
  inválido (`runtime`) se decide por evidencia de escala frente a evidencia de dirección.
- El validador automático comprueba presencia y coherencia; no certifica correctitud
  pedagógica ni ausencia de solución en la pista 3.

## Decisiones pendientes de revisión humana

Estas preguntas deben responderse durante el ejercicio; cada respuesta se genera
con evidencia y puede alterar la guía:

- El límite exacto entre `concept` y `logic` cuando el modelo era correcto pero
  la implementación introduce además un descuido local: ¿ambas etiquetas o una sola?
- Si el nivel 2 (`location`) puede nombrar la Variable concreta cuando la pista 1
  ya mencionó el concepto con otras palabras.
- El umbral de `confidence` aceptable para un ejemplo sin reproducción real en el juez.
- Si `unknown` con más de tres alternativas pierde utilidad pedagógica o debe
  fragmentarse en subcasos observables (contrato: no se inventan subcategorías).

## Identificación de versión de guía y ejemplos

Registrar antes de empezar y repetir en la evidencia final:

- Identificador de commit del repo que contiene:
  - `docs/ai-tutor/guia-etiquetado.md` en su versión ___
  - `docs/ai-tutor/esquema-ejemplo.json` en su versión ___
  - `ai_tutor/dataset/schema.py` en su versión ___
  - `docs/ai-tutor/ejemplos-*.json` en su versión ___
- Fecha del ejercicio: ___  · Revisor A: ___ · Revisor B: ___

## Resultado esperado

- Ambos revisores generan etiquetas para los mismos ejemplos usando solo la guía.
- Las coincidencias fuertes dominan; los desacuerdos quedan listados con su evidencia.
- Ningún archivo de ejemplos queda modificado durante el ejercicio.
- Ningún ejemplo queda marcado como aprobado sin la revisión real de PB-07.

## Lista de verificación del cierre del ejercicio

- [ ] Se fijó y registró la versión de guía, esquema y ejemplos (commit).
- [ ] Dos revisores distintos del autor etiquetaron el mismo conjunto con plantilla.
- [ ] Se compararon hojas: coinciden las etiquetas o existen desacuerdos listados.
- [ ] Cada desacuerdo tiene resolución con evidencia o permanece abierto como `unknown`.
- [ ] El validador se ejecutó en positivo/ambiguo/negativo por ambos revisores.
- [ ] No se inventaron campos ni estados aprobatorios (diff limpio de los JSON).
- [ ] La evidencia del ejercicio apunta a este registro desde la guía o el informe correspondiente.
