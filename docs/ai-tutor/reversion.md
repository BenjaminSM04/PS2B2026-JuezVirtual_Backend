# Reversión

Guía vigente: `docs/actualizacion-django52-pg17.md` en el repositorio de integración.
Antes de abrir escrituras se puede volver a la aplicación anterior sobre PG10
original preservado con sus archivos, clave y Redis. El ensayo local verifica
ese punto y conserva los volúmenes. Después de nuevas escrituras no existe una
reversión automática sin pérdida hacia la copia antigua: detener actividad y
conciliar o restaurar de forma aprobada.

Una salida insegura requiere apagar `AI_TUTOR_MODEL_ENABLED` de inmediato; el
juez continúa usando su veredicto y el tutor puede servir respaldo seguro. Para
volver a un modelo anterior conservar directorio y hashes aprobados, parar motor,
remontar el directorio correcto y verificar readiness antes de habilitarlo.
No renombrar un modelo distinto para hacerlo coincidir con el manifiesto.

Configuraciones pedagógicas son inmutables. Crear otro borrador y activarlo para
sesiones nuevas; sesiones existentes siguen con su versión original. No modificar
historia ni nivel del alumno mediante SQL para efectuar una reversión.
