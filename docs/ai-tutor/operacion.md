# Operación del tutor

El despliegue se mantiene en el repositorio `OnlineJudge_Deploy`. Su guía
`docs/actualizacion-django52-pg17.md` es el procedimiento de actualización y
recuperación. Estas instrucciones no autorizan operar el servidor real.

Variables: `AI_TUTOR_MODEL_ENABLED=0` por defecto; URL interna
`AI_TUTOR_ENGINE_URL=http://oj-tutor:8080`.

Plazos (segundos): `MODEL_TIMEOUT_S` (servicio `oj-tutor`, defecto 8, rango 1-30)
es el presupuesto total del motor frente a llama.cpp, que no emite cabeceras hasta
terminar de generar; `AI_TUTOR_ENGINE_TIMEOUT` (backend, defecto 10, rango 1-30)
es el presupuesto total del backend frente al motor y **debe ser mayor** que
`MODEL_TIMEOUT_S`, o el backend corta antes de que el motor responda y cae al
respaldo. Un valor fuera de rango o no numérico impide arrancar el backend
(`ImproperlyConfigured`) y deja el motor sin readiness. Una petición del tutor
ocupa un worker del backend hasta ese tiempo; por eso el tope es 30 s y existen
cuotas por usuario y solo 2 ranuras en el motor. Medir el p95 del modelo
(RTX 2060: p50 0,6 s, p95 2,5 s; en CPU es mayor) antes de subir los valores.
Con `compose.tutor.yml` y perfil `tutor`, motor y llama comparten una red privada
sin puertos publicados. El backend es el único puente. El motor usa usuario sin
privilegios, raíz de solo lectura, límites CPU/memoria/PID y volúmenes de modelos
de solo lectura. Sin artefactos compatibles su health devuelve 503.

El directorio de modelos contiene `model.gguf`, clasificador y `manifest.json`.
El manifiesto requiere decisión `integrate`, revisor distinto de `trained_by`,
fecha `reviewed_at`, licencia, revisión de modelo y `dataset_version`; entradas
`generator` y `classifier` contienen `file` y `sha256`. El generador debe ser
exactamente `model.gguf` en la raíz, la misma ruta que carga llama. No usar rutas
alternativas, enlaces ni un archivo que no sea el evaluado. Verificar manualmente
la aprobación real y procedencia: los campos JSON no son una firma institucional.
Preparar un directorio nuevo por versión; verificar hashes antes del arranque.

Actualizar primero con el motor apagado, montar el artefacto revisado, comprobar
readiness y ensayar en problemas sintéticos. Encender únicamente después de la
revisión PB-16/PB-28 correspondiente. Ante timeout, salida inválida, modelo caído
o circuito abierto se usa respaldo; el circuito se abre 30 segundos. El guard es
una defensa heurística con reconocimiento de sintaxis, **no una garantía semántica**
contra cualquier solución completa. Su revisión humana sigue siendo obligatoria.

`python manage.py report_tutor_metrics --days 30` exporta agregados del periodo:
categoría, nivel, fuente, resultado, versión, cantidad, latencia media/p50/p95 y
valoraciones. No contiene código, prompts, usuarios, IP o correos. Las tablas de
feedback sí están asociadas a la sesión privada: no publicar dumps ni extraerlas
como si fueran agregadas. Permisos operativos de base de datos siguen aplicando.

`purge_tutor_metrics --days 90` muestra el alcance sin borrar; solo `--apply`
elimina métricas vencidas. No elimina entregas ni respuestas. Acordar retención
institucional independiente para sesiones/feedback, registros de auditoría y
respaldos; el comando de métricas no representa una purga integral de PII.

`reconcile_mascot` recupera logros de AC normales históricos; también se ejecuta
antes de servir tras migrar. Idempotente, recorre un resultado por usuario/problema,
sin cargar el código de cada entrega. Medir su duración con el volumen histórico
real durante un ensayo autorizado antes de establecer la ventana de mantenimiento.
