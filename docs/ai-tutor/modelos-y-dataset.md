# Datos, selección y ajuste reproducible

Estado vigente: hay dataset, clasificador y ajuste QLoRA reales en modo técnico
sintético para defensa; ver `defensa/README.md`. No existe dataset de producción
aprobado ni resultado pedagógico de campo. El flujo normal descrito debajo conserva
sus puertas de revisión; `--technical-demo` es una vía explícita y separada que
mantiene borradores, rechaza historia real y no fabrica identidades o aprobaciones.
Las identidades ficticias que aparecen en tests solo verifican validaciones.

Se ejecutaron 54 variantes sintéticas: tres problemas originales, seis lenguajes y
tres mutaciones por lenguaje/problema. `variantes/observaciones.json` conserva
digest de imagen, hash del código, comando y resultado observado. Son borradores,
no aprobaciones. El compilador aislado de estas variantes y el juez del deploy
son artefactos diferentes. No atribuir una medición de uno al otro.

1. Revisar `guia-etiquetado.md`, `ejercicio-acuerdo.md` y `origen-datos.md`.
   Solo exportar historia con autorización institucional documentada y conjunto
   explícito; el comando no autoriza el uso por sí mismo.
2. Validar borradores con `python manage.py validate_tutor_examples ARCHIVO`.
   `review_tutor_example --help` permite registrar una decisión humana explícita
   en un archivo nuevo; autor y revisor deben ser distintos. No ejecutar una
   aprobación para desbloquear artificialmente las fases siguientes.
   Para revisar muchos borradores, `export_tutor_review_sheet ORIGEN.json PLANILLA.csv`
   genera una planilla (CSV UTF-8 con BOM, una fila por ejemplo no cerrado) y
   `apply_tutor_review_sheet ORIGEN.json PLANILLA.csv SALIDA.json --reviewer USUARIO`
   aplica solo las filas con `decision`. Una planilla corresponde a un revisor
   identificado, con las mismas reglas que el comando individual (revisor distinto
   del autor, notas obligatorias, decisiones cerradas intactas), y se rechaza completa
   si una fila falla. La planilla no altera contenido pedagógico: las correcciones se
   hacen en el JSON de origen y se vuelve a exportar. Guía para el equipo en `kit-revision.md`.
3. `tutor_dataset build ejemplos-aprobados.json artefactos/dataset-v1` rechaza
   cualquier registro no aprobado. Agrupa variantes por problema normalizado,
   divide por semilla 2026 y verifica IDs, grupos y código sin contaminación.
   El manifiesto contiene checksums del origen, pipeline y cada partición.
4. `tutor_dataset train artefactos/dataset-v1 artefactos/classifier.json` entrena
   el clasificador NB. Selecciona el umbral en validation; `tutor_dataset evaluate
   artefactos/dataset-v1 artefactos/evaluacion.json --model artefactos/classifier.json`
   usa test separado y produce macro F1, precisión/recall/soporte por categoría,
   confusión, desglose por lenguaje y comparación con la clase mayoritaria.
5. Comparar al menos dos candidatos reales con `scripts/benchmark_tutor_models.py`
   sobre la misma muestra aprobada. Registrar modelo, revisión inmutable, licencia,
   cuantización, latencia, fallos, rúbrica y revisión de respuestas. Medir memoria
   en el hardware objetivo por separado: el benchmark no inventa esa medición.
6. Una selección requiere `model_id`, `revision` (commit de 40 hex), `license`,
   `decision=selected`, `reviewer`, `benchmark_file`, `benchmark_sha256` y
   `rubric_version`. El entrenamiento comprueba el archivo, su hash, dos candidatos
   y la revisión de las respuestas seleccionadas antes de importar librerías grandes.
   Si el candidato es GGUF, sus pesos no sirven para Transformers: añadir en
   la selección y en `candidate` del benchmark el mismo objeto `training_model`
   con `model_id` del repositorio safetensors, `revision` propia de 40 hex,
   `license` y `provenance` (referencia documental revisada que vincula ambos
   artefactos). No asumir que los commits de dos repositorios son iguales.
   El entrenador rechaza la relación ausente o cambiada y carga tokenizer/pesos
   exclusivamente desde esa fuente fijada. Guarda la identidad en su resultado.
   Ejemplo de estructura, sin autorizar una selección real:

   ```json
   {"training_model": {"model_id": "organizacion/modelo-base", "revision": "COMMIT_REAL_DE_40_HEXADECIMALES", "license": "LICENCIA_VERIFICADA", "provenance": "REFERENCIA_REVISADA_DE_LA_CONVERSION_GGUF"}}
   ```

   El benchmark preliminar publicado no contiene esta aprobación: volver a
   medir/revisar con la muestra aprobada antes de producir la selección final.
7. Ejecutar `train_tutor_model --help` y el notebook `notebooks/tutor_lora.ipynb`.
   El notebook no tiene celdas ejecutadas ni resultados fingidos. Dependencias
   específicas en `deploy/requirements-training.txt`, separadas del backend.
   QLoRA requiere CUDA; LoRA en CPU es explícito. Se fijan semillas y revisión,
   se usan safetensors sin código remoto y se rechazan ejemplos demasiado largos.
   Reanudar exige dataset/selección idénticos y checkpoint real.

El ajuste guarda adaptador, tokenizer, métricas reales, hardware, versiones y
checksums únicamente después de ejecutarse. La conversión posterior a GGUF y
su evaluación no se consideran completadas por crear el notebook. Para integrar
se requiere revisión distinta del entrenador, licencia y manifiesto compatible;
el motor permanece deshabilitado mientras falten esas evidencias.
