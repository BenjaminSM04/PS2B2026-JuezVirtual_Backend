# LizardJudge — historial del servicio

Las notas de administración se leen de este archivo del repositorio instalado.
Una entrada no confirma que la versión haya sido desplegada.

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
