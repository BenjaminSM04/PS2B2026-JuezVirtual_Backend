# LizardJudge — historial del servicio

Las notas de administración se leen de este archivo del repositorio instalado.
Una entrada no confirma que la versión haya sido desplegada.

## [2.2.2] - 2026-11-05

### Tutor
- «Proponer con IA» deja de responder `tutor-suggest-unavailable` con enunciados como «Censo entre cuatro bordes»: el modelo devolvía los conceptos como lista de cadenas, con claves distintas o con el JSON cortado, y el motor lo descartaba sin dejar rastro.
- El motor pide la propuesta con un esquema JSON, así que siempre llega con conceptos (nombre y explicación) y las tres pistas, y la saneada en lugar de rechazarla: descarta solo el concepto o la pista inválidos, recorta los textos largos en límite de frase y sustituye una pista que falte por un texto genérico que el docente revisa. Los bloques de código y las soluciones siguen rechazándose.
- El reintento pide solo los tokens que caben en el tiempo restante, reutiliza el prompt en la caché del modelo y cada petición usa una semilla nueva.
- Cada propuesta rechazada queda en `docker logs` del motor con el motivo y un recorte de la salida (`TUTOR_LOG_LEVEL=INFO` añade las saneadas).

## [2.2.1] - 2026-11-05

### Tutor
- «Proponer con IA» tiene su propio límite de tiempo (90 s en el motor, 100 s en el backend) en lugar del de las observaciones: en el servidor sin GPU el borrador tardaba más que ese límite y nunca llegaba al docente.
- Los borradores piden salidas más cortas (2 o 3 conceptos, explicaciones y pistas de una frase) y el motor atiende una sola sugerencia a la vez para no dejar sin ranura las observaciones a estudiantes.
- La ruta de la sugerencia espera hasta 110 s en el proxy del backend; el resto de la API mantiene 60 s.

## [2.2.0] - 2026-11-05

### Tutor
- Sugerencias con IA para el docente: borradores de conceptos y pistas a partir del enunciado, que se revisan y guardan como borrador sin llegar al estudiante.
- Respuestas del tutor más rápidas: enunciado y código acotados antes de consultar al motor, con menos texto generado.

### Concursos
- Un concurso sin envíos puede borrarse junto con sus problemas, anuncios y clasificaciones.
- Si el concurso tiene envíos solo puede ocultarse, para conservar el historial.

## [2.1.0] - 2026-11-05

### Tutor
- Diagnósticos accionables según veredicto, lenguaje, mensaje del compilador y señal de ejecución.
- Motor generativo aprobado como complemento de las explicaciones, con filtro de calidad y respaldo determinista.
- Pistas y conceptos siguen siendo los configurados por el docente.

## [2.0.0] - 2026-10-25

### Administración
- Casos de prueba privados editables como texto, con límites y control de permisos.
- SMTP y Resend configurables desde administración, sin exponer la clave guardada.
- Prueba de correo con errores comprensibles y protección de credenciales.

### Plataforma
- Django 5.2 y migraciones compatibles con el historial privado del juez.
- Tutor, sesiones de práctica, logros y controles de acceso.
- Historial de cambios del repositorio y versión instalada consultables desde la aplicación.
