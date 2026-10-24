# Kit de revisión de borradores del tutor (PB-04 / PB-07)

Guía paso a paso para revisar los borradores con una planilla en lugar de un comando por ejemplo.
Estado: las herramientas existen; **ninguna revisión se ha hecho**. Las herramientas solo registran
lo que una persona decide: no revisan, no aprueban y no sustituyen la lectura pedagógica.

Desde el 24/10/2026 se incluyen `uncertainty`, `provenance` y `content_sha256`.
Debe reexportarse la planilla antigua antes de empezar: se rechaza si le faltan
columnas o si el JSON cambió después de exportarla, incluso en campos que no
aparecían en la primera versión. El hash vincula el contenido completo y el autor;
no firma ni autentica la identidad de una persona. Revise también la incertidumbre.
Al abrir el CSV, importe sus columnas como texto para que Excel no interprete
fragmentos de código como fórmulas.

## Quién revisa

- Según `docs/estado-sprints.md` del deploy, PB-04 es de Auza056 y PB-07 de SamuelVicente937 y Auza056.
  Esas personas deben hacer la revisión o coordinarla con otros integrantes.
- El revisor debe ser distinto del autor de cada ejemplo (los 54 borradores constan como
  `generacion-sintetica`; si el autor es otro, se aplica la misma regla, sin distinguir mayúsculas).
- Cada revisor usa **su propio usuario** en la columna `reviewer` y en `--reviewer`. Una planilla = un revisor.
  No se comparte una cuenta ni se escribe el nombre de otra persona.
- El ejercicio de acuerdo entre dos revisores (`ejercicio-acuerdo.md`) es parte de PB-07: debe hacerse
  con dos personas reales antes de dar por buena cualquier aprobación.

## 1. Qué revisar en cada ejemplo

Según `guia-etiquetado.md`, leer enunciado, fragmento y evidencia, separando lo observado de lo supuesto, y comprobar:

1. **category y verdict** coinciden con las definiciones e inclusiones/exclusiones de la guía
   (compilation -2; runtime 3 o 4; logic/concept -1 u 8; complexity 1, 2 o 3; unknown con alternativas y confianza <= 0.5).
   No todo WA es logic; un error del sistema es unknown.
2. **evidence** respalda la categoría; no se infiere una causa que los hechos no demuestran.
3. **concept y explanation** son correctos y no culpabilizan al estudiante sin evidencia.
4. **Tres pistas progresivas:** concept (recuerda el concepto, sin corrección), location (acota dónde mirar),
   strategy (propone una prueba o razonamiento). La tercera no dicta la implementación ni es código listo para enviar.
5. **Procedencia:** sintético sin autorización simulada; sin datos personales ni de estudiantes.
6. El validador no certifica nada de lo anterior: esas lecturas son humanas.

Decisión por fila (columna `decision`):

- `approved`: el contenido es correcto y las pistas son adecuadas.
- `rejected`: no es corregible tal cual o no debe usarse.
- `review`: necesita cambios o hay dudas; se explica en `notes`.

`notes` es obligatoria en toda fila con decisión: qué se comprobó y por qué. No usar «OK» ni notas inventadas.

## 2. Exportar la planilla

```
python manage.py export_tutor_review_sheet docs/ai-tutor/variantes/ejemplos-borrador.json planilla.csv
```

Genera un CSV UTF-8 con BOM con los ejemplos no cerrados (no sobrescribe un archivo existente). Si su Excel
en español abre todo en una sola columna, exporte con `--delimiter ";"`. Cada persona puede exportar su copia.
Para el equipo hay una planilla ya generada con los 54 borradores en
`respaldos/planilla-revision-borradores.csv` del deploy (carpeta fuera de git).

## 3. Llenar en Excel o LibreOffice

- Abrir con Datos > Desde texto/CSV (Excel) o Archivo > Abrir (LibreOffice) eligiendo codificación UTF-8
  y separador coma (o punto y coma si se exportó con `--delimiter ";"`).
- Llenar solo `decision`, `reviewer` (su usuario) y `notes`. Dejar vacía la decisión de las filas que no revise: se ignoran.
- **No editar las demás columnas.** Si una fila con decisión tiene contenido distinto del origen se rechaza toda
  la planilla. Para corregir contenido, edite el JSON de origen (con su revisión) y vuelva a exportar.
- Guardar como CSV UTF-8 (Excel: «CSV UTF-8 (delimitado por comas)»; LibreOffice: juego de caracteres Unicode UTF-8).
  Excel en español puede guardar con `;`; también se acepta.

## 4. Aplicar

```
python manage.py apply_tutor_review_sheet ORIGEN.json planilla.csv ORIGEN-revisado.json --reviewer SU_USUARIO
```

- Escribe un archivo nuevo (no sobrescribe) y conserva el origen; imprime el conteo approved/rejected/review.
- Todo o nada: si una fila falla (revisor distinto del --reviewer o igual al autor, notas vacías, id duplicado
  o inexistente, decisión ya cerrada, contenido alterado, contrato inválido) no se crea salida y el mensaje
  indica cada fila.
- Las decisiones cerradas (approved/rejected) no se modifican; cambiarlas requiere una nueva revisión versionada.

## 5. Validar y construir el dataset

```
python manage.py validate_tutor_examples ORIGEN-revisado.json
```

Después, solo con el conjunto realmente aprobado por humanos:

```
python manage.py tutor_dataset build ejemplos-aprobados.json artefactos/dataset-v1
```

`tutor_dataset build` rechaza cualquier registro que no esté approved. No se aprueba ni se edita un JSON
a mano para desbloquear esta fase.

## 6. Ejercicio de acuerdo entre dos revisores

1. Dos revisores distintos exportan la misma planilla y trabajan por separado, sin ver la hoja del otro
   (procedimiento y plantilla en `ejercicio-acuerdo.md`).
2. Cada uno registra en `notes` su etiqueta y razón; los desacuerdos se resuelven con evidencia y se dejan
   en `review` o `unknown` mientras estén abiertos.
3. Las decisiones cerradas no se cambian, así que solo se aplica la decisión final acordada, con la planilla de un
   revisor identificado y distinto del autor. Conserve las planillas de ambos revisores como evidencia del ejercicio
   (con enlace a acta o PR en `notes`) sin aplicar la del segundo sobre decisiones ya cerradas.
4. Registre los resultados en `ejercicio-acuerdo.md`. Sin este ejercicio con personas reales PB-07 sigue abierta.
