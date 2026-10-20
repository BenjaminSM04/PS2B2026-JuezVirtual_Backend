# Origen de datos y exportación anonimizada (PB-05)

Estado: implementación técnica local terminada y probada con datos sintéticos.
La extracción contra datos reales **no se ha ejecutado** y sigue bloqueada hasta
disponer de una autorización institucional documentada.

## Propósito y alcance

Herramienta local, reproducible y de solo lectura para convertir entregas históricas
de la tabla `Submission` en registros candidatos para el dataset del tutor (contrato
1.0 de PB-04). El tutor en ejecución no cambia; este flujo es independiente de
`judge/` y no altera `Submission`, `Problem`, ni ningún modelo.

## Procedencia de cada campo del registro

| Campo del esquema PB-04 | Origen real |
|---|---|
| `example_id` | Pseudónimo aleatorio no reversible generado con `rand_str` (no deriva del ID interno) |
| `problem` | Campos públicos del problema: `title`, `description`, `input_description`, `output_description` (HTML a texto plano, límite 1900) |
| `language` | `Submission.language` (validado contra `judge/languages.py`) |
| `faulty_code` | `Submission.code` |
| `verdict` | `Submission.result` |
| `evidence` | Solo `statistic_info` (`time_cost`, `memory_cost`, `err_info`, `score`); **nunca** `Submission.info`, que puede contener casos privados o salidas esperadas |
| `category`, `uncertainty`, `explanation`, `concept`, `hints` | Etiquetado automático conservador por veredicto; ver la sección «Sesgo automático» |
| `provenance` | `kind=historical`, `authorization` y `reference` desde la autorización documentada |
| `review` | Borrador automático (`status=draft`); exige diagnóstico y revisión humanas (PB-07) |

## Requisitos de autorización

- `--authorization-file <ruta>`: JSON con `authorization` (no vacío) y `problems`
  (lista no vacía). Este archivo es la **documentación institucional estructurada**
  de la autorización; el comando comprueba estructura, no validez institucional,
  que sigue siendo jurisdicción humana.
- Los problemas solicitados deben estar todos cubiertos por `problems` del archivo.
- `--authorization <id>`: identificador suelto; **no** se considera autorización
  verificable. Solo permite `--dry-run`; una exportación real con él queda
  bloqueada y registrada en la constancia.
- Verificación disponible: estructura del JSON y cobertura de la lista de problemas.
  **Verificación faltante (para el cierre):** comprobación humana de que el
  identificador corresponde a un acta o acuerdo institucional real y vigente.
- Ante la falta de autorización o del conjunto explícito de problemas: aborta sin
  tocar la base de datos y escribe una constancia de no uso.

## Anonimización y limitaciones

Elimina de la salida: `user_id`, `username`, `ip`, el ID interno de la entrega, la
columna `info` y cualquier semilla de identidad. El detector de campos prohibidos
escanea el resultado serializado buscando:

- nombres de usuario y direcciones IP de las entregas observadas (hallazgo por
  coincidencia de palabra con límites; se excluye al `--actor` propio);
- correos electrónicos (patrón), direcciones IPv4 (patrón) y claves tipo
  `api_key/token/secret/password = ...`.

El detector se prueba con valores señuelo, pero **no garantiza anonimización
perfecta**: un nombre con variaciones no previstas, un identificador codificado
dentro del contenido o datos de terceros que no aparezcan como señuelo pueden
requerir revisión humana extra. Tras el escaneo, cada registro se valida contra
`TutorExampleSerializer`; si algo falla, se aborta **toda la exportación**, sin
archivos parciales (escritura atómica: archivo temporal más cambio de nombre, con
borrado del temporal ante cualquier fallo).

## Sesgo automático honesto

Debido a que un veredicto no basta para diagnosticar pedagógicamente el error
(guía PB-04), el etiquetado automático es conservador y todo queda sin aprobar:

| Veredicto | Categoría automática | Justificación |
|---|---|---|
| -2 | `compilation` | Causa factual directa |
| 4 | `runtime` | Causa factual directa |
| 1, 2, 3 | `unknown` (Complejidad / Fallo en ejecución, ≤ 0.5) | Un timeout o memoria excedida no prueba complejidad |
| -1, 8 | `unknown` (Lógica / Concepto / Formato, ≤ 0.5) | Un WA no identifica la causa |
| 5 | `unknown` (Fallo de infraestructura, ≤ 0.4) | Guía: no imputar al estudiante |

Esos registros esperan el etiquetado y la revisión humanas (PB-07); por eso su
`review.status` es `draft` con avisos.

## Restricciones de selección

- Solo problemas: solicitados explícitamente, visibles (`visible=True`) y **sin
  concurso** (`contest` vacío; coherente con PB-25).
- Solo entregas: sin concurso, con veredicto final de la lista de errores
  `[-2, -1, 1, 2, 3, 4, 5, 8]` (se rechazan `0`, `6` y `7` con recuento),
  lenguaje soportado en `judge/languages.py` y código no vacío.
- Resumen de rechazos en el manifiesto: por veredicto, por lenguaje, código vacío
  y tipo de problema (inexistente / no-visible / de-concurso).

## Formato del archivo de salida

`{"manifest": {...}, "records": [...]}` — el manifiesto incluye `schema_version`,
`generated_at`, `authorization` (identificador no secreto),
`authorization_verification` (`archivo-documentado` siempre en exportación real),
`problems` (IDs solicitados válidos), `actor`, `counts` (total_evaluado, exportado,
exportado_por_lenguaje, rechazado_por_veredicto, rechazado_por_lenguaje,
rechazado_por_codigo_vacio, rechazado_por_problema) y `notes` libre (≤ 300).

Cada `record` pasa la validación individual de `TutorExampleSerializer`; el archivo
completo no valida como lista con `validate_tutor_examples` (que espera un JSON de
lista pura). Para validar una salida:

```bash
python manage.py shell -c "import json
from ai_tutor.dataset.schema import TutorExampleSerializer
data = json.load(open('docs/ai-tutor/export.json', encoding='utf-8'))
for i, record in enumerate(data['records'], 1):
    assert TutorExampleSerializer(data=record).is_valid(), (i, TutorExampleSerializer(data=record).errors)
print(len(data['records']), 'registros válidos')"
```

## Uso seguro del comando

```bash
# Simulación (no escribe archivos):
python manage.py export_authorized_submissions --problems 1,2,3 --dry-run --actor docente

# Exportación real (exige archivo de autorización documentado):
python manage.py export_authorized_submissions --problems 1,2,3 \
    --authorization-file docs/ai-tutor/auth-acta-2026-001.json \
    --output docs/ai-tutor/export.json --actor docente --notes "exportación inicial"
```

- Parámetros: `--problems` o `--problems-file` (un identificador por línea, admite
  comentarios `#`), `--authorization` o `--authorization-file` (excluyentes),
  `--output`, `--constancia`, `--dry-run`, `--actor`, `--notes`.
- Solo lectura: aparte de la constancia y de `--output` (ninguno de los dos se
  escribe si el flujo falla antes) no se escribe archivo alguno y la base de datos
  no sufre cambios.

## Constancia de no uso

Cuando el intento se bloquea (sin autorización, archivo inválido o ilegible,
conjunto de problemas ausente o incompleto, autorización no verificable, fallo de
escritura, detección de campos prohibidos o error de validación), el comando
**no exporta datos** y anexa en el archivo de constancia (por defecto
`docs/ai-tutor/constancia-no-uso.txt`) una entrada con solo: fecha, actor, motivo
y problemas solicitados; nunca contenido de la base de datos.

## Auditoría

Cada intento (bloqueado, dry-run, completado) se registra con `utils.audit` en el
logger `audit`, con metadatos de `actor` sin secretos ni datos personales. Nota:
la función `audit_log` escribe `actor=anonymous` cuando no hay usuario de petición;
la responsabilidad humana del comando queda trazada en `extra.actor` y en `--actor`.

## Cómo consumen esta salida PB-07 y PB-08

- PB-07 obtiene los registros candidatos con `review.status=draft`, completa su
  `category`/concepto/pistas con revisión dual y guarda los aprobados en
  `ai_tutor/dataset/records/`; el `counts.exportado` del manifiesto es su frontera
  de consistencia.
- PB-08 calcula el hash del archivo de exportación intacto y construye el manifiesto
  de versión con ese archivo como fuente; el campo libre `notes` permite enlazar el
  acta de autorización sin incluir secreto alguno.

## Restricción de ejecución con datos reales

Este flujo se probó con datos sintéticos en pruebas automatizadas.
Ejecutar contra la base de producción exige, en orden:

1. Autorización institucional documentada (acta o acuerdo referenciado).
2. Archivo de autorización creado desde esa documentación.
3. Aprobación explícita del responsable de datos para el día de la extracción.
4. Revisión posterior de la salida por el etiquetador de PB-07.

Hasta que esos requisitos existan, la política es: `--dry-run` y constancia de no uso.
