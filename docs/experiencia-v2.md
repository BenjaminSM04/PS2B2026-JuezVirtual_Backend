# Servicios para la experiencia 2.0

`VERSION` identifica la versión del servicio. `/api/admin/versions` obtiene sus
notas de `CHANGELOG.md` del repositorio instalado y vincula su revisión a GitHub.
No consulta servicios externos ni lee el antiguo `docs/data.json`. El historial
es texto, tiene tamaño y cantidad de entradas limitados y excluye borradores sin
versión. La imagen incluye ambos archivos.

SMTP conserva su contrato previo y añade `sender_name` opcional. Todo se configura
mediante la API administrativa existente, con acceso de superadministrador y CSRF.
El nombre se usa en los correos del sistema y cae al nombre corto del sitio si se
deja vacío. Se rechazan saltos de línea en ese campo; el GET nunca devuelve la clave
y una actualización sin clave conserva la existente.

La prueba de SMTP devuelve errores comprensibles de autenticación, remitente,
destinatario o conexión, sin reproducir respuestas del proveedor que puedan
contener credenciales. Las pruebas usan transporte simulado: no envían correo.

No cambia el esquema ni modifica datos de usuarios, problemas, entregas o archivos.
La rama se apoya en `integracion/produccion-lizardjudge` y no debe desplegarse sobre
el PostgreSQL 10 actual. No se fusiona ni se opera Coolify durante la revisión visual.
