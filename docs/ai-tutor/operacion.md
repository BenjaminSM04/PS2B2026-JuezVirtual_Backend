# Operación del tutor

El despliegue se mantiene en el repositorio `OnlineJudge_Deploy`. Su guía
`docs/actualizacion-django52-pg17.md` es el procedimiento de actualización y
recuperación. Estas instrucciones no autorizan operar el servidor real.

La defensa dispone de `compose.defensa.yml` y un controlador de demostración con
datos exclusivamente ficticios, cuentas aleatorias, volúmenes propios y puerto
loopback. El modelo QLoRA experimental se monta mediante manifiesto técnico y
requiere dos flags del motor; la operación normal no lo acepta por defecto.
Ese perfil usa 20 s en el motor y 25 s en el backend: en dos CPU las tres pistas
del ensayo completo tardaron aproximadamente 10–12 s. No confundirlo con el
presupuesto normal 8/10 s ni con las mediciones preliminares en GPU.

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

Velocidad en CPU: el tiempo lo dominan el prefill y los tokens generados. El backend
recorta el enunciado, la entrada y la salida a 1200 caracteres cada uno y el código a
4000 (si es más largo conserva inicio y final), después de redactar datos privados; el
motor pide como máximo 120 tokens a llama.cpp y activa `cache_prompt`. Si la
generación se corta pero la cadena `content` ya se cerró, se aprovecha ese texto.

Sugerencias para el docente: `POST /suggest` del motor (red interna) genera un borrador
de conceptos y pistas a partir del enunciado. El backend lo expone en
`POST /api/admin/ai_tutor/config/suggest`, lo valida con el esquema de versiones y lo
devuelve sin guardar; el docente lo revisa y lo guarda como borrador con el flujo
habitual, por lo que nunca llega al estudiante sin revisión. Tiene plazos propios, distintos
de los de las observaciones: `SUGGEST_TIMEOUT_S` (servicio `oj-tutor`, defecto 90, rango
30-100) es el plazo total de hasta dos intentos del motor y `AI_TUTOR_SUGGEST_TIMEOUT`
(backend, defecto 100, rango 31-105) el del backend frente al motor; este **debe ser mayor**
que el del motor. Pide 260 tokens (200 en el reintento, que además solo se hace si quedan al
menos 20 s) para 2-3 conceptos y tres pistas breves: a 5-8 tokens/s en CPU son 45-70 s. Un
valor fuera de rango impide el arranque del backend o deja el motor sin readiness, igual que
`MODEL_TIMEOUT_S`. Cuota de 6 sugerencias por usuario y minuto; sin `AI_TUTOR_MODEL_ENABLED`
responde `tutor-suggest-unavailable`.

Cadena de plazos de una sugerencia (cada capa debe esperar más que la siguiente): llama.cpp
y motor 90 s, backend frente al motor 100 s, nginx del backend 110 s (ruta propia
`/api/admin/ai_tutor/config/suggest` en `deploy/nginx/nginx.conf`; el resto de `/api` sigue en
60 s), nginx del frontend 115 s y el navegador 120 s. Gunicorn (`--threads 4`, worker gthread)
no la corta: su `--timeout` solo vigila el bucle principal del worker, no cada petición. Si
se suben los plazos, subir también esos proxies; los rangos de arriba existen para que el
valor configurado nunca supere lo que los proxies toleran.

Concurrencia: el modelo es uno (`-np 1`) y atiende una petición a la vez. El motor admite una
sola sugerencia simultánea (otra recibe 429 `busy`) para que siga habiendo una ranura libre
para las observaciones. Mientras una sugerencia genera (hasta 90 s), la observación de un
estudiante espera en la cola de llama.cpp y puede agotar su plazo de 25-30 s: en ese caso el
backend usa el diagnóstico determinista (y abre el circuito 30 s). Es el comportamiento
aceptado; no se interrumpe la sugerencia en curso.

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
