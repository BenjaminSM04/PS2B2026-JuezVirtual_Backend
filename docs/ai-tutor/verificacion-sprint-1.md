# Evidencias del Sprint 1

Verificación final: 30 de septiembre de 2026, en una copia aislada, sin datos ni credenciales de producción.
Los responsables de PB-01, PB-02 y PB-04 se conservan en GitHub Projects.

| Comprobación | Resultado |
|---|---|
| Suite Django directa sobre PostgreSQL 10 y Redis 7 | 165 pruebas aprobadas, 31,029 segundos |
| Pruebas específicas de `ai_tutor` incluidas en la suite | 29, con concurrencia de sesiones e intentos |
| Componentes Vue y navegación durante envíos pendientes | 8 pruebas aprobadas |
| `python manage.py check` | Sin incidencias |
| `flake8 ai_tutor` | Sin incidencias |
| Lint de componentes nuevos y transporte del tutor | Sin errores |
| Comparación del lint general contra la base | Los mismos 198 errores y 4 advertencias; ninguna incidencia nueva |
| Build del frontend y Dockerfile combinado | Correctos; minificación activa |
| Arranque con migraciones y healthcheck | Backend y juez saludables |
| Migraciones en otra base temporal | Aplicadas, revertidas y reaplicadas; columnas de Submission idénticas |
| Ejemplos positivos y ambiguos | Seis válidos por archivo |
| Ejemplos negativos | Rechazados; salida del comando distinta de cero |
| Compose y `actionlint` | Correctos; Compose advierte únicamente sobre su campo histórico `version` |

## Flujo real por HTTP

Se comprobó, con cookies de sesión y CSRF, la configuración inicialmente deshabilitada,
su activación por el administrador, la lectura sin crear sesiones, el inicio explícito
y la recuperación del mismo UUID con nivel cero. Una entrega C enviada al juez real
obtuvo WA; se registró dos veces por HTTP y produjo un único intento. Recuperar la sesión
conservó ese intento y su nivel cero.

Las pruebas de Django cubren además bloqueo de concursos y problemas ocultos, cuentas
deshabilitadas, permisos administrativos, auditoría de cambios efectivos, entrega ajena,
otro problema, veredictos pendientes, entregas anteriores, campos desconocidos, CSRF,
restricciones de base de datos y conservación de las entregas.

## Interfaz y revisión

En la primera verificación de navegador se comprobó el interruptor mediante barra espaciadora,
el inicio mediante Enter, editor y envío real, recuperación al recargar, y ausencia de
desbordamiento horizontal en escritorio y móvil. Las capturas de esa verificación están
en [escritorio](evidencias/entrenamiento-escritorio.jpg) y [móvil](evidencias/entrenamiento-movil.jpg).
Después se simplificó el texto introductorio y se corrigió la navegación durante un envío,
con pruebas de regresión. La repetición final del navegador fue bloqueada por su política
de URL; las comprobaciones finales de componentes y HTTP sí se ejecutaron.

La revisión independiente de código detectó respuestas tardías al navegar, un error genérico
al borrar problemas con historial protegido y ejemplos ambiguos que mostraban causas demasiado
evidentes. Se corrigieron y la suite completa volvió a pasar.

## Límites de cierre

PB-01 y PB-02 pueden cerrarse después de integrar y verificar los punteros del deploy.
PB-04 permanece en revisión: falta revisión pedagógica humana por alguien distinto del autor,
incluyendo el acuerdo de etiquetado entre revisores. La validación automática no acredita
esa aprobación. No hay motor de IA ni panel de pistas en este sprint.

Una sincronización exitosa de submódulos acredita los SHA del repositorio de deploy;
no demuestra por sí misma un despliegue saludable en producción.
