# PB-28: verificación técnica y límites

Estado: implementación bajo revisión, **sin aprobación para piloto**. Responsables
originales: BenjaminSM04 y BenjaminCalle1233. Los resultados actualizados de CI y
el deploy se publican en sus ramas/PR; no corresponden al servidor real.

Evidencia disponible en el repositorio de integración:

- `scripts/verify_upgrade.py`: backend histórico Django 3.2/PG10, 21 tablas de
  aplicación comparadas en sus columnas originales, secuencias/objetos grandes,
  migración PG17 y reversión anterior a abrir escrituras. Datos sintéticos.
- `scripts/verify_ui.py`: Chromium real, API real, explicación, pistas 1–3 con
  nuevas entregas, concepto, valoración, versiones docentes, mascota, preferencias,
  teclado, modo oscuro, movimiento reducido y anchos 320/375/1280. Veredictos
  sembrados expresamente; no sustituye la prueba del juez.
- `scripts/verify_judge.py`: juez real por digest, token y seis lenguajes. Pruebas
  directas del protocolo distintas del flujo navegador/cola; no inferir un E2E
  de envío en navegador a partir de juntar ambas evidencias.
- `scripts/test_tutor_engine.py`: regresiones de programa inline y artefacto GGUF
  distinto del cargado. Sin descargar ni fingir aprobación de un modelo.
- Suite Django completa sobre PostgreSQL 17; fuentes en tests, no identidad o
  código de estudiantes. Permisos, concursos, CSRF, idempotencia, cuotas, ZIP,
  sanitización, contexto, versiones, guard, fallback, retención y concurrencia.

Defectos encontrados durante revisión: filtro de código inline incompleto,
GGUF verificado en ruta diferente, falta de historia Git en CI, nivel del intento
calculado al registrar en vez de enviar y lectura lenta sin presupuesto total.
Se añadieron regresiones antes de corregir los casos funcionales. La matriz de
integración debe indicar la última suite que pasa y los SHA exactos publicados.

Presupuestos propuestos para medición/aceptación, todavía no resultados del modelo:
respuesta del tutor p95 ≤ 5 s, error técnico < 1% bajo carga acordada, ninguna fuga
crítica y recuperación a fallback en una petición tras fallo. Separar modelo,
fallback y juez. Registrar CPU/RAM/GPU, concurrencia, versión, número de muestras,
p50/p95, máximos y consumo en reposo/carga; repetir con fallos y recuperación.
Una medición en Docker Desktop no certifica el hardware del servidor.

Pendientes externos concretos: dataset aprobado, rúbrica/acuerdo humano,
selección de modelo y memoria medida, entrenamiento y evaluación reales,
hardware objetivo, revisión independiente del aislamiento, aceptación PB-28.
Resultados del piloto: no existen; ver `piloto/resultados.md`.
