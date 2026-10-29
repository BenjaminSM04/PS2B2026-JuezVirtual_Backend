# Guía pedagógica del tutor — contrato 1.0 (PB-04)

Responsable de la tarjeta: Auza056. Autor de esta propuesta: BenjaminSM04.
Estado: pendiente de revisión humana por otro integrante. Ningún ejemplo adjunto está aprobado.
El procedimiento reproducible del ejercicio entre dos revisores está en
`docs/ai-tutor/ejercicio-acuerdo.md`; sus resultados se registran allí, no en esta guía.

## Contrato y uso

La fuente ejecutable del contrato es `ai_tutor/dataset/schema.py`, construida con los serializers DRF del proyecto.
`esquema-ejemplo.json` muestra un registro completo; los archivos de ejemplos contienen listas.
Ejecutar `python manage.py validate_tutor_examples docs/ai-tutor/ejemplos-positivos.json`.
El comando no escribe datos y termina con error ante campos desconocidos (también anidados), duplicados o incoherencias.
Los ejemplos negativos deben fallar: sirven para comprobar el rechazo, no para entrenamiento.
No se recolectaron entregas reales. Los ejemplos son fragmentos sintéticos de diagnóstico, no soluciones completas ni resultados ejecutados por el juez.
La reproducción de variantes corresponde a PB-06; la aprobación del dataset corresponde a PB-07.

Campos obligatorios: schema_version, example_id, problem (enunciado/contexto autosuficiente), language,
faulty_code (fragmento erróneo), verdict (código final del juez), category, evidence (hechos y su origen),
concept, explanation, uncertainty, hints, provenance y review. No se incluyen usuarios estudiantiles, IP ni credenciales.
Los seis lenguajes se toman de `judge/languages.py`: C, C++, Java, Python3, Golang y JavaScript.
Los veredictos son -2 compilación, -1 respuesta incorrecta, 1/2 tiempo, 3 memoria, 4 ejecución,
5 error del sistema y 8 aceptación parcial. Una entrega aceptada, pendiente o en evaluación no es ejemplo erróneo.
El error del sistema se clasifica unknown, nunca como error demostrado del estudiante.

## Categorías

| Categoría | Definición e inclusión | Exclusión | Ejemplo orientativo |
|---|---|---|---|
| compilation | El compilador o comprobador sintáctico no puede producir un programa ejecutable: sintaxis, tipos, símbolos. Exige veredicto -2. | Excepciones durante ejecución o salida incorrecta. | C: declaración sin punto y coma; revisar el diagnóstico sintético antes de asegurar la línea. |
| runtime | El programa inicia y falla por una operación o recurso inválido; veredicto 4 o 3 con evidencia de ejecución. | Lentitud por escala o una respuesta incorrecta sin excepción. | C++: acceso fuera de un vector mediante at(), que puede lanzar excepción. |
| logic | La implementación no cumple una condición concreta del enunciado; -1 u 8 y contraejemplo identificable. | Afirmar que todo WA es lógico: puede ser concepto, formato o falta de evidencia. | Java: acumulador empieza en 1 al sumar dos entradas. |
| complexity | El costo de tiempo o memoria crece incompatible con los límites; 1, 2 o 3 y evidencia de tamaño/costo. | Inferir O(n²) exclusivamente de un timeout. | Python3: dos recorridos de n elementos con n=100000. |
| concept | El modelo matemático o semántico utilizado no corresponde a lo pedido; -1 u 8 con evidencia conceptual. | Un descuido local en un modelo que sí es correcto. | Golang: división entera para una media real. |
| unknown | La evidencia no distingue causas. Se describen alternativas y confianza <=0.5. | Inventar una causa o culpabilizar al estudiante por un error de infraestructura. | JavaScript: WA sin entrada ni salida observada; formato o cálculo siguen siendo posibles. |

No se inventan subcategorías. En memoria, distinguir fallo de acceso (runtime) de crecimiento de almacenamiento (complexity).
Para un mismo WA, concept exige evidencia de una comprensión incorrecta; logic exige un fallo local demostrable.
Los casos ambiguos se conservan como unknown hasta aportar un contraejemplo, diagnóstico o medición.
Confianza es una valoración editorial entre 0 y 1, no una probabilidad calibrada. Toda valoración incluye razón.

## Tres pistas progresivas

1. **concept:** recordar el concepto relevante mediante una pregunta o invariante, sin indicar una corrección completa.
2. **location:** acotar la expresión, bloque o fase que conviene inspeccionar, apoyándose en evidencia.
3. **strategy:** proponer una prueba o un procedimiento de razonamiento para corregirlo; no proporcionar código solucionador.

Ejemplo: «¿Qué elemento neutro tiene una suma?» → «Revisa el valor inicial del acumulador» →
«Traza un caso con entradas cero y compara el estado antes y después de cada suma».
La tercera pista no dicta la implementación, ni incluye una solución lista para enviar.
La validación automática comprueba presencia y contenido distinto, pero no puede certificar por sí sola progresión,
corrección pedagógica o ausencia de una solución. Esos puntos requieren lectura humana de cada pista y del contexto.

## Procedencia y revisión

`provenance.kind` distingue synthetic de historical. reference identifica el origen sin datos personales.
historical exige authorization como referencia verificable a una autorización; el comando no verifica su validez institucional.
synthetic exige authorization=null. La recolección autorizada se implementó en PB-05 con
`ai_tutor/dataset/anonymize.py` y el comando `export_authorized_submissions`
(exportación real solo con `--authorization-file`; sin autorización, constancia de no uso; detalles en `docs/ai-tutor/origen-datos.md`).

`review` contiene author, authored_at, reviewer, reviewed_at, approved_at, status y notes.
Estados: draft (escrito), review (listo para revisar), approved (decisión humana favorable), rejected (decisión desfavorable).
Revisor y fecha aparecen juntos; revisor distinto del autor sin distinguir mayúsculas. La revisión no precede a la autoría.
approved exige revisión, fecha de aprobación no anterior y observaciones; los demás estados no admiten approved_at.
Estos metadatos son declaraciones: la herramienta no autentica al revisor ni reemplaza la evidencia de su revisión.
Registrar la revisión real con un enlace a PR/comentario o acta en notes, jamás simular aprobación.

## Lista para dos revisores y desacuerdos

El paso a paso de este trabajo, incluyendo la plantilla de coincidencias y el registro
de desacuerdos, está en `docs/ai-tutor/ejercicio-acuerdo.md`. Los criterios siguientes
resumen lo mínimo exigido:

- Leer enunciado, fragmento y evidencia; separar lo observado de lo supuesto.
- Asignar categoría siguiendo inclusiones/exclusiones, concepto y confianza.
- Verificar que las tres pistas progresan y no revelan solución ni casos privados.
- Ejecutar el validador y dejar observaciones identificadas y fechadas.
- Ante desacuerdo, registrar ambas etiquetas y razones en notes; mantener review o unknown.
- Aprobar solo tras resolver el desacuerdo con evidencia y un revisor distinto.

Decisiones iniciales: incluir unknown; no convertir todo WA en logic; distinguir memoria de ejecución y de escala;
no confundir validación del contrato con aprobación pedagógica. No hay desacuerdos resueltos por revisión humana todavía.
