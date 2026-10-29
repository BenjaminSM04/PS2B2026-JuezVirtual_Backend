# Riesgos y estado de aceptación

| Riesgo | Control y pendiente |
| --- | --- |
| Pérdida de datos en actualización | Restaurar PostgreSQL 10 a 17 en volumen separado; comparar todas las columnas originales, secuencias, objetos grandes, /data y Redis. Ensayado localmente con datos sintéticos. Falta ensayo autorizado con copia real. |
| Cambio de credenciales/sesiones | Conservar secret.key, credenciales privadas y Redis. No crear administrador por defecto. Prueba de sesión histórica tras restaurar Redis y migrar. |
| Solución completa/alucinación | Contexto acotado, guard, nivel validado, fuente/incertidumbre y valoración. Sigue siendo posible evadir heurísticas; modelo deshabilitado sin revisión real. |
| Datos privados en prompts | Lista positiva y redacción; no se consultan casos ocultos/soluciones/SPJ/entregas ajenas. No sustituye la anonimización y autorización de datasets. |
| Concurrencia/duplicados | Bloqueos PostgreSQL, restricciones e idempotencia; ensayos simultáneos de sesiones, intentos, feedback y logros. |
| Denegación de servicio | Tamaño, cuotas, presupuesto total de lectura/circuito, límites de contenedor. Medición de carga del hardware objetivo pendiente. |
| Dependencias Vue 2 | Avisos conocidos inventariados y backports acotados con caducidad; no equivale a escáner limpio. Revisar antes de piloto. |
| Aislamiento del juez | Protocolo y lenguajes probados con imagen inmutable. Java usa política upstream sin seccomp de lenguaje; no se declara aislamiento equivalente a una VM. Endurecimiento y amenazas del host requieren revisión antes de aceptar código no confiable en producción. |
| Datos pedagógicos escasos | 54 variantes de tres problemas son borradores. No permiten afirmar cobertura de categorías, acuerdo humano, desempeño real ni generalización. |
| Modelo/hardware/piloto | Sin selección humana, entrenamiento, evaluación en hardware objetivo ni participantes consentidos. PB-29 no ejecutada. |

No se debe declarar el sistema apto para el piloto a partir de pruebas automatizadas.
PB-28 requiere aceptación humana del informe y ausencia de defectos críticos abiertos.
