# Sprint 1: entrenamiento persistente

Historias: PB-01 (5 SP), PB-02 (5 SP), PB-04 (3 SP).
Se conservan los responsables de las tarjetas: BenjaminSM04; BenjaminCalle1233 y SamuelVicente937; Auza056, respectivamente.
PB-04 requiere todavía revisión pedagógica humana distinta del autor.

## Integración y límites

La aplicación Django `ai_tutor` es independiente del juez. No se agregaron campos a Submission,
ni se altera su código, resultado, estadísticas o proceso de evaluación. No se llama a un proveedor de IA.
El panel de pistas y el motor del tutor quedan fuera de este sprint.
Una actividad sin configuración está deshabilitada. Solo un docente/administrador con los permisos
existentes sobre el problema puede cambiarla; cada cambio efectivo se registra en el logger audit tras confirmar la transacción.
Una escritura repetida con el mismo valor no cambia la fecha ni genera otro evento.

Para entrenar se exige cuenta autenticada y habilitada, problema visible, configuración activa y ausencia de concurso
en el problema y en la entrega. La interfaz oculta los controles en concursos; el servidor vuelve a comprobar la condición.
Ocultar el problema, deshabilitar entrenamiento o deshabilitar la cuenta revoca el acceso a lectura y escritura.
El identificador de problema en estas API es su `id` numérico interno, no el `_id` mostrado en la URL.

## API

Todas las respuestas mantienen `{error, data}`; los errores de dominio usan el formato existente (HTTP 200 y error no nulo).
Las escrituras conservan CSRF para sesiones de navegador y el mecanismo existente de autenticación por API key.
Los serializers de entrada rechazan campos desconocidos. No se admite user_id, contest_id, result ni help_level del cliente.

| Método y ruta | Entrada | Salida en data |
|---|---|---|
| GET /api/admin/ai_tutor/config | query problem_id | problem_id, enabled, created_by, updated_by, created_at, updated_at; ausente equivale a false |
| PUT /api/admin/ai_tutor/config | JSON problem_id, enabled | Configuración persistida; sin cambios no crea un evento |
| GET /api/ai_tutor/availability | query problem_id | problem_id, enabled, can_start; un visitante no puede iniciar |
| GET /api/ai_tutor/session | query problem_id | Sesión activa propia o null; no crea ni reconcilia |
| POST /api/ai_tutor/session | JSON problem_id | Crea o recupera la sesión y reconcilia entregas finalizadas |
| POST /api/ai_tutor/attempt | JSON session_id UUID, submission_id | Intento registrado o el mismo intento si ya existía |

Sesión: id UUID, problem_id, state (active/closed), highest_help_level, created_at, updated_at,
attempt_count y attempts. Intento: id, submission_id, language, result, help_level, created_at.
Nunca se devuelven código, IP, evidencia privada del juez ni otros usuarios.
Las instantáneas se conservan al repetir una petición, aunque cambie posteriormente la entrega.
El nivel inicial es cero. `advance_help_level` está reservado a servicios internos; nunca disminuye
el máximo ni permite valores fuera de 0–3. No existe un endpoint de pistas en esta versión.

Restricciones: una sesión active por usuario/problema, un intento por sesión/entrega, estado y niveles válidos.
Las escrituras bloquean primero el problema y después la sesión en una transacción; el veredicto se lee con bloqueo de la entrega.
Solo se aceptan entregas propias del mismo problema, sin concurso, posteriores o iguales al inicio
y con resultado final (-2, -1, 0, 1, 2, 3, 4, 5 u 8). Pendiente (6), evaluando (7) y códigos desconocidos se rechazan.
El historial protege la entrega frente a borrado. Si se intenta borrar el problema, la API informa
`protected-tutor-history` y recomienda ocultarlo; no destruye el historial ni devuelve un fallo genérico.

## Interfaz

Al editar un problema normal ya guardado, «Habilitar entrenamiento» consulta y guarda por separado del formulario.
No aparece durante la creación ni al editar problemas de concurso. Su fallo no modifica el formulario general.
En la vista pública se consulta disponibilidad y sesión propia. Solo una sesión existente se recupera automáticamente;
el primer inicio exige pulsar «Iniciar entrenamiento». «Recuperar y actualizar» reconcilia intentos finalizados,
incluidos los que terminaron mientras la página estaba cerrada o el registro falló.
El registro de un intento no bloquea el envío ni sustituye el veredicto. Al cambiar problema o usuario se descartan
respuestas tardías. Al navegar durante una entrega se libera el estado visual para poder enviar en el siguiente problema.

## Verificación reproducible

Se usaron PostgreSQL 10, Redis 7 y volúmenes temporales con el proyecto Compose `lizard-sprint1`,
sin usar datos, credenciales ni puertos del despliegue existente. El HTTP de prueba se limitó a 127.0.0.1:18080.
Ejecutar directamente `python manage.py check` y `python manage.py test --noinput`; no depender de run_test.py,
que no propaga correctamente todos los fallos. Las pruebas concurrentes requieren PostgreSQL.

- API, permisos, auditoría efectiva, exclusión de concursos y CSRF.
- Propiedad, entregas previas/pendientes/ajenas, idempotencia y dos escritores simultáneos.
- Restricciones de la base, nivel cero/monótono, snapshots y comparación de todas las columnas de Submission.
- Validación positiva y ambigua; rechazo de negativos, campos anidados desconocidos, revisión propia y confianza no finita.
- Migraciones de ai_tutor aplicadas, revertidas y reaplicadas en una base temporal distinta; columnas de Submission idénticas.
- Componentes Vue reales: `npm run test:tutor`, transporte HTTP simulado; incluye navegación mientras POST sigue pendiente.
- Lint específico del tutor, comparación del lint completo con la base, build del frontend y Dockerfile combinado.
- Navegador: switch con barra espaciadora, inicio con Enter, editor, envío real al juez, veredicto WA,
  intento con nivel cero, recuperación al recargar y vista móvil sin desbordamiento horizontal.
- Compose y actionlint sobre update-submodules.yml; comprobar healthcheck y migraciones del contenedor.

El frontend base contiene errores históricos de lint. Deben informarse por separado, sin presentar
el lint completo como limpio. Para construir con Webpack 3/UglifyES se desactivó únicamente collapse_vars,
la optimización que producía un TypeError interno en el bundle vendor; la minificación sigue activa.
La migración histórica submission.0007 ahora declara las dependencias de sus claves foráneas para instalar desde cero.
Las dos expectativas obsoletas de pruebas de registro/lenguaje se ajustaron al contrato ya vigente; no se cambió esa política.

## Publicación y aprobación

Publicar backend y frontend en sus main; después el workflow del deploy.
Ambos submódulos declaran branch=main. El workflow obtiene main explícitamente, serializa ejecuciones,
propaga fallos de actualización/commit/push y usa un mensaje automático en español.
Dispararlo con `gh workflow run update-submodules.yml -R BenjaminSM04/OnlineJudge_Deploy --ref main`.
Comprobar el resultado del run y comparar los dos gitlinks con los SHA publicados, no solo su estado verde.
Un run de sincronización exitoso acredita los punteros de deploy; no acredita la salud de un servidor de producción.
La aprobación humana de la guía y los ejemplos se registra con revisor distinto, fecha y enlace a la revisión real.
