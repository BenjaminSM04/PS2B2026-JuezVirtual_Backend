# Informe de implementación — PB-04 y PB-05 (LizardJudge)

Fecha de ejecución: 2026-10-18/19 (hora local del entorno). Ejecución exclusivamente local;
sin commits, push, merges ni publicaciones. Todos los comandos de verificación corrieron en
contenedores Docker efímeros con volúmenes temporales (patrón del Sprint 1), sin tocar la base
de datos del despliegue ni sus volúmenes.

## A. Resumen ejecutivo

- **PB-04 (Estado final: PARCIAL / implementation ready — cierre humano pendiente).**
  La guía, el esquema y el validador de Sprint 1 se verificaron operativos (52/52 pruebas,
  validador sobre positivos/ambiguos/negativos). Se creó la metodología reproducible del
  ejercicio de acuerdo entre dos revisores (`ejercicio-acuerdo.md`, con plantillas vacías) y
  se actualizaron las referencias mínimas en `guia-etiquetado.md`. El criterio «dos revisores
  etiquetan el mismo ejemplo» NO se puede dar por satisfecho: requiere dos personas reales.
- **PB-05 (Estado final: implementación técnica completa; extracción real pendiente de autorización).**
  Se implementaron `anonymize.py` (funciones puras + detector de campos prohibidos con señuelos),
  el comando `export_authorized_submissions` (autorización documentada obligatoria para exportar,
  identificador suelto solo para dry-run, constancia de no uso, escritura atómica, auditoría) y
  `docs/ai-tutor/origen-datos.md`. 23 pruebas nuevas, todas OK. **No se ejecutó ninguna
  exportación contra datos reales** (no existe autorización institucional documentada).
- Nada del código nuevo altera modelos, migraciones, settings, Docker, Compose ni el juez.

## B. Inventario de archivos

| Archivo | Acción | Descripción | Motivo |
|---|---|---|---|
| `OnlineJudge/docs/ai-tutor/ejercicio-acuerdo.md` | Creado | Metodología reproducible del ejercicio entre dos revisores: materiales, orden, criterios de comparación, plantilla de registro (vacía), flujo de desacuerdos, decisiones iniciales/pendientes, identificación de versión y checklist de cierre | PB-04: criterio del backlog «dos revisores etiquetan el mismo ejemplo sin inventar campos» y «lista de decisiones o desacuerdos» |
| `OnlineJudge/docs/ai-tutor/guia-etiquetado.md` | Modificado | 3 cambios mínimos: enlace al ejercicio (cabecera), referencia a PB-05 implementada en la sección de procedencia, enlace en «Lista para dos revisores» | PB-04: trazabilidad y link del procedimiento; contenido del contrato 1.0 intacto |
| `OnlineJudge/ai_tutor/dataset/anonymize.py` | Creado | Funciones puras de anonimización (pseudónimos con `rand_str`, contexto de problema desde campos públicos, evidencia solo desde `statistic_info` permitido, revisión `draft`) + detector de campos prohibidos (usuario/IP origen, correo, IPv4, credenciales) con errores que no exponen el contenido detectado | PB-05: anonimización, lista permitida y aborto ante campos prohibidos |
| `OnlineJudge/ai_tutor/management/commands/export_authorized_submissions.py` | Creado | Comando de gestión: `--authorization/-file`, `--problems/-file`, `--dry-run`, `--actor`, `--constancia`, `--output`, `--notes`; solo lectura; conteos por veredicto/lenguaje/código/problema; validación contra `TutorExampleSerializer`; constancia de no uso; `utils.audit` | PB-05: exportación segura, reproducible y auditable |
| `OnlineJudge/ai_tutor/tests/test_anonymization.py` | Creado | 23 pruebas: 10 unitarias `SimpleTestCase` (sin BD, sustitutos) y 13 del comando con BD efímera (sintéticas) | PB-05: pruebas con señuelos, abortos, dry-run, reproducción de conteos, sin mutaciones |
| `OnlineJudge/docs/ai-tutor/origen-datos.md` | Creado | Procedencia de campos, requisitos de autorización, reglas/limitaciones del detector, formato del manifiesto, uso del comando, constancia, auditoría y consumo por PB-07/PB-08 | PB-05: documentación de procedencia obligatoria |
| Ningún otro archivo | Sin cambios | — | Respetar convenciones y alcance |

Archivos eliminados: **ninguno**.
Revisiones de documentos PB-04 existentes (`esquema-ejemplo.json`, `schema.py`,
`validate_tutor_examples.py`, `ejemplos-*.json`): **sin cambios**.

## C. Detalle técnico

- **Anonimización (`anonymize.py`)**
  - `build_record(submission, problem, authorization, generated_at, actor)` produce un registro
    completo válido para `TutorExampleSerializer`. `example_id = hist-<24 chars aleatorios>`
    (`utils.shortcuts.rand_str`, no derivado del ID interno).
  - `problem_context`: HTML → texto plano (`title`, `description`, `input_description`,
    `output_description`), límite 1900 caracteres.
  - `build_evidence`: solo `statistic_info` (`time_cost`, `memory_cost`, `err_info`, `score`),
    con recorte a 1900 en `err_info`; `Submission.info` nunca se lee (puede contener casos
    privados o salidas esperadas).
  - Etiquetado automático conservador: `-2→compilation`, `4→runtime`; `1/2/3`, `-1/8` y `5` →
    `unknown` con alternativas y confianza ≤ 0.5 (regla del esquema); `review.status=draft`.
  - `scan_record` + `detect_forbidden_fields`: escaneo por campo (correo, IPv4, credenciales
    tipo `api_key/token/secret/password`, identidad = nombre de usuario/IP de las entregas
    observadas, excluyendo al `--actor`); `ForbiddenFieldsError` enumera ubicaciones
    (`Registro N: correo en faulty_code`) sin exponer el contenido.
- **Comando `export_authorized_submissions`**
  - Autorización: `--authorization-file` (JSON con `authorization` + `problems`; única vía de
    exportación real; el archivo es la documentación estructurada — el comando valida
    estructura y cobertura, no validez institucional, que es humana) o `--authorization`
    (identificador suelto, no verificable: bloquea exportación real, solo `--dry-run`).
    Sin autorización o sin conjunto explícito de problemas: aborto sin leer la base de datos.
  - Selección: problemas solicitados ∩ existentes, visibles y sin `contest_id` (coherente con
    PB-25); entregas sin concurso con veredicto ∈ `[-2, -1, 1, 2, 3, 4, 5, 8]`; rechazos
    contados por veredicto, lenguaje, código vacío y tipo de problema.
  - Validación: cada registro pasa por `TutorExampleSerializer`;
    `is_valid()==False` en cualquiera aborta todo sin escribir archivos.
  - Salida: `{"manifest": {...}, "records": [...]}` con `schema_version`, `generated_at`,
    `authorization`, `authorization_verification`, `problems`, `actor`, `counts`, `notes`.
    Escritura atómica (temporal + `os.replace`, borrado en `finally`).
  - `--dry-run`: valida y muestra el resumen JSON en stdout; **no escribe archivo alguno**.
  - Constancia de no uso: anexa (`append`) fecha, actor, motivo y problemas solicitados;
    se escribe para cada intento bloqueado, incluso `--dry-run` bloqueados.
  - Auditoría: `utils.audit.audit_log` con acciones `tutor_export_blocked`,
    `tutor_export_dry_run`, `tutor_export_completed`; `actor` en `extra` (el logger del
    proyecto imprime `actor=anonymous` en comandos sin usuario de petición; se documenta).
- **Decisiones de diseño**
  - Identificador suelto ≠ autorización verificable (conforme a la restricción del prompt);
    la verificación institucional real queda documentada como paso humano.
  - La exportación con 0 registros permitida (conteos explican el motivo); el manifiesto de
    PB-08 puede versionar el archivo intacto.
  - El archivo de exportación (manifiesto+registros) no consume `validate_tutor_examples`
    tal cual (ese validador espera lista pura); se documenta el modo de validación por registro.
- **Dependencias reutilizadas**: `TutorExampleSerializer`/`StrictSerializer` (PB-04, sin cambios),
  `JudgeStatus` y `Submission` (solo lectura), `Problem` (solo lectura), `judge.languages`,
  `utils.shortcuts.rand_str`, `utils.audit.audit_log`. Sin dependencias externas nuevas.

## D. Pruebas y verificaciones

Entorno: `oj-backend:local` (imagen del propio proyecto, Python 3.12.15 / Django 3.2.25) +
PostgreSQL 10 + Redis 7 en contenedores efímeros de red/tiempo de vida dedicados a las pruebas.

| Comando o prueba | Resultado | Evidencia | Observaciones |
|---|---|---|---|
| `python manage.py check` | Aprobado | "System check identified no issues (0 silenced)", exit 0 | Secret key generada solo en el volumen temporal del contenedor |
| `python manage.py test ai_tutor --noinput` (52) | Aprobado | "Ran 52 tests … OK" | Incluye las 152 pruebas históricas del tutor + las 23 nuevas: total 52 del paquete `ai_tutor` |
| `python manage.py test ai_tutor.tests.test_anonymization --noinput` (23) | Aprobado | "Ran 23 tests … OK" | 10 `SimpleTestCase` + 13 con BD efímera |
| `flake8` (5 archivos objetivo + contrato) | Aprobado | 0 incidencias en los archivos nuevos | `.flake8` del proyecto (max 180, comillas dobles) |
| `validate_tutor_examples ejemplos-positivos.json` | Aprobado | "6 ejemplos válidos…" | PB-04 |
| `validate_tutor_examples ejemplos-ambiguos.json` | Aprobado | "6 ejemplos válidos…" | PB-04 |
| `validate_tutor_examples ejemplos-negativos.json` | Aprobado (debe fallar) | `CommandError` × 6 registros con veredicto 6 | PB-04 |
| Export real contra producción | No ejecutado (bloqueado a propósito) | — | Requiere autorización institucional documentada; fuera de alcance |
| Pruebas de frontend (npm) y de despliegue | No ejecutadas | — | Sin cambios de frontend ni infraestructura; no aplica |

Casos cubiertos por las 23 pruebas: validación con el contrato, `unknown` con alternativas y
confianza ≤ 0.5 para WA, categorías factuales -2/4, pseudónimo aleatorio no derivado del
origen, contexto sin HTML y recortado, registros sin `username`/`ip`/`user_id`, detección
(correo, IP, credencial, identidad) y no exposición del contenido detectado, registro limpio
aceptado, revisión `draft`, parseo de problemas, autorización ausente/inválida/no cobertura/
no verificable, export exitoso anonimizado y de solo lectura (snapshot de `Submission`
comparado), aborto por campos prohibidos sin archivos parciales ni temporales, dry-run sin
escritura con conteos reproducibles, entrega de concurso excluida, problema de concurso
rechazado con conteo.

## E. Seguridad y datos

- Acceso a datos reales: **no**. Las pruebas usan datos sintéticos creados en la BD de prueba
  temporal (`test_onlinejudge`) del contenedor Postgres efímero, destruida al terminar.
- Exportaciones generadas: **ninguna** en el host; las salidas de las pruebas se crearon en
  directorios temporales del contenedor y se destruyeron con él.
- Base de datos real: **sin cambios**. Sin migraciones nuevas; sin `docker-compose.yml` ni
  `Dockerfile` modificados; los volúmenes del despliegue nunca se montaron en las pruebas.
- Privacidad verificada por pruebas: ningún registro exportado contiene `user_id`,
  `username`, `ip`, ID interno de entrega ni `info` completo; el detector aborta sin escribir
  y sin exponer secretos; los mensajes de error de autorización/escritura no incluyen datos.
- Limitaciones documentadas (en `anonymize.py` y `origen-datos.md`): el detector no garantiza
  anonimización perfecta (variaciones de nombres, identificadores codificados, datos de
  terceros no presentes como señuelo); `audit_log` imprint "anonymous" en contexto de comando.
- La autorización se modeló en dos niveles: identificador suelto (no verificable) y archivo
  documentado (estructura verificada); la validez institucional queda como paso humano y así
  se documenta en `origen-datos.md` («verificación faltante»).

## F. Estado de Git y alcance local

Estado inicial (registrado al comenzar):
- Working tree del submódulo `OnlineJudge` limpio (los commits en HEAD eran previos:
  `f717bb6`, `6d6ace1`, `35963fa`).
- Padre `OnlineJudge_Deploy`: `M OnlineJudge` (puntero de submódulo preexistente), sin
  seguimiento: `AGENTS.md`, `TASKS.md`, `package-lock.json` (archivos del propio usuario,
  no creados ni modificados en esta ejecución).
- Los contenedores del despliegue (`onlinejudge_deploy-*`) ya estaban detenidos antes de
  empezar; no se iniciaron, detuvieron ni eliminaron.

Estado final (tras la ejecución), dentro del submódulo `OnlineJudge`:

```
 M docs/ai-tutor/guia-etiquetado.md
?? ai_tutor/dataset/anonymize.py
?? ai_tutor/management/commands/export_authorized_submissions.py
?? ai_tutor/tests/test_anonymization.py
?? docs/ai-tutor/ejercicio-acuerdo.md
?? docs/ai-tutor/origen-datos.md
```

- No se realizaron commits, pushes, merges, tags ni publicaciones de ningún tipo.
- No se revirtieron ni sobrescribieron cambios preexistentes.
- No se realizó ninguna operación remota; todo permanece en el entorno local.
- No se atribuyen a esta ejecución los estados preexistentes del padre ni los archivos sin
  seguimiento anteriores.

## G. Pendientes y pasos humanos

1. **PB-04**: ejecutar el ejercicio real con dos revisores según `ejercicio-acuerdo.md`
   (fijar commit de versión, ambas hojas de etiquetado, comparación, registro de
   desacuerdos); enlazar el resultado de la revisión en la guía o acta. Sin ese paso, PB-04
   no se debe cerrar.
2. **PB-05**: obtener la autorización institucional documentada y crear el archivo JSON de
   autorización desde esa documentación; aprobación explícita del responsable de datos;
   recién entonces ejecutar la exportación real (primero `--dry-run`, luego exportación) y
   registrar la constancia/evidencia correspondiente.
3. **PB-07/PB-08**: los registros exportados llegan con `review.status=draft` y categorías
   automáticas conservadoras (`unknown` en la mayoría) — requieren etiquetado humano dual y
   luego el versionado/hashes de PB-08.
4. Riesgo conocido: el detector de campos prohibidos puede producir falsos positivos (por
   ejemplo, constantes tipo IP dentro del código); en ese caso se revisa y se reescribe el
   fragmento antes de reintentar (política documentada de aborto total).

## H. Matriz de criterios de aceptación

### PB-04

| Criterio | Estado | Evidencia |
|---|---|---|
| Categorías con definición/inclusión/exclusión/ejemplo | CUMPLIDO | `guia-etiquetado.md` (tabla de 6 categorías), sin cambios necesarios |
| Tres niveles con progresión; nivel 3 sin solución | CUMPLIDO | Guía §«Tres pistas progresivas» + `HintsSerializer` (contenido distinto) |
| Casos ambiguos admiten probable/desconocida | CUMPLIDO | `unknown` en esquema (`schema.py`) con alternativas y confianza ≤ 0.5; `ejemplos-ambiguos.json` pasa el validador |
| Esquema y validador coherentes con la guía | CUMPLIDO | `manage.py check` + validador sobre positivos/ambiguos/negativos OK |
| Guía enlazada y versionada localmente | CUMPLIDO | `guia-etiquetado.md` modificado (referencias); versionado local pendiente de commit por el usuario (no hacemos commits) |
| Procedimiento reproducible de dos revisores | PARCIAL | Metodología y plantilla creadas (`ejercicio-acuerdo.md`); **PENDIENTE ejecución con dos revisores reales** |
| Coincidencias/desacuerdos registrados | PENDIENTE | Plantilla vacía esperada; sin resultados inventados |
| Revisión humana distinta del autor | PENDIENTE | Sprint 1 ya documentaba «falta revisión pedagógica humana» |

### PB-05

| Criterio | Estado | Evidencia |
|---|---|---|
| Exportación exige autorización verificable + problemas explícitos | CUMPLIDO | `load_authorization` + prueba `test_missing_authorization_blocked_with_constancia`, `test_unverified_identifier_blocks_real_export`, `test_authorization_must_cover_requested_problems` |
| Identificador suelto no se trata como autorización válida | CUMPLIDO | Bloqueo de export real + constancia; `--dry-run` permitido y probado |
| Archivo de autorización vacío/inválido/ilegible rechazado | CUMPLIDO | `test_invalid_authorization_file_blocked` |
| Detección de campos prohibidos con aborto total y sin parciales | CUMPLIDO | `test_forbidden_fields_abort_without_partial_files` (+ detectores unitarios) |
| Sin nombres/correos/IP/tokens/IDs internos en la salida | CUMPLIDO | `test_successful_export_is_anonymized_valid_and_read_only` + `test_record_discards_username_ip_and_internal_submission_id` |
| Cada registro conserva problema/lenguaje/código/veredicto/evidencia | CUMPLIDO | Campos del esquema llenados desde `Problem`/`Submission`; evidencia desde `statistic_info` permitido |
| Veredictos 0/6/7 rechazados; problemas de concurso excluidos | CUMPLIDO | Pruebas de rechazo por veredicto, entrega de concurso y problema de concurso; coherente con `EXPORTABLE_RESULTS` del contrato PB-04 |
| Proceso reproducible y de solo lectura | CUMPLIDO | Conteos reproducibles probados; snapshot de `Submission` igual antes/después (`test_successful_export...`; sin transacciones, ninguna escritura) |
| `--dry-run` disponible y sin archivos | CUMPLIDO | `test_dry_run_writes_nothing_and_counts_are_reproducible` |
| Manejo seguro de escritura atómica / sin parciales | CUMPLIDO | `atomic_write_json` (tmp + `os.replace` + limpieza en `finally`) probado vía tests sin `.tmp` sobrantes |
| Padrón de rechazos y conteos en el manifiesto | CUMPLIDO | Prueba de export exitosa (veredicto/lenguaje/problema/código) |
| Auditoría registrada | CUMPLIDO | `utils.audit` con acciones `tutor_export_blocked/dry_run/completed` (visible en logs de las pruebas); limitación `anonymous` documentada |
| Constancia de no uso | CUMPLIDO | Prueba `test_missing_authorization_blocked_with_constancia` |
| Documentación de procedencia | CUMPLIDO | `docs/ai-tutor/origen-datos.md` |
| Pruebas automatizadas con señuelos | CUMPLIDO | 23 pruebas OK |
| Validación contra el esquema real | CUMPLIDO | Cada registro con `TutorExampleSerializer` |
| Extracción contra datos reales | BLOQUEADO | Depende de autorización institucional documentada + decisión humana; fuera de esta ejecución |
| Cierre formal de PB-05 | PARCIAL | Implementación técnica completada; cierre requiere la extracción real (o constancia) y revisión del equipo |

## Nota final honesta

No se declara PB-04 ni PB-05 como completamente terminadas: el trabajo técnico y de
documentación está implementado y verificado localmente, y los criterios restantes (
revisión humana dual en PB-04; autorización institucional y extracción real en PB-05)
requieren participantes humanos y no fueron simulados.
