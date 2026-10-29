# Integración conservando la instalación privada

La rama integra Django 5.2, tutor y práctica, casos privados editables como texto y
SMTP compatible con Resend. Conserva los comandos y permisos del backend privado,
la reparación de dificultades, los campos adicionales de exportación, el endpoint
de versión, Sentry opcional y el usuario 900:903.

Las dos historias de migraciones JSON confluyen mediante cinco migraciones vacías.
No se renombran registros históricos ni se usa `--fake`. El comando `migrate`
ejecuta las migraciones, reconcilia logros de forma idempotente y conserva la
configuración salvo el token del juez, que procede de `JUDGE_SERVER_TOKEN`.

## Comprobaciones del 25/10/2026

- 331 pruebas aprobadas; flake8, comprobación de Django y ausencia de cambios de
  modelos sin migración aprobados. Cobertura total medida: 79 %.
- Restauración local real de PostgreSQL 10 a 17: 20 tablas, 1.312 filas idénticas
  antes de aplicar migraciones.
- Después de migrar: ninguna fila histórica modificada o perdida y ninguna
  regresión de las 17 secuencias. Se añadieron diez tablas, cuarenta permisos,
  diez tipos de contenido y dieciocho registros de migración.
- Reconciliación ejecutada dos veces y lectura con el ORM privado anterior
  Django 3.2.25 aprobadas. Esto no acredita una reversión después de abrir escrituras.
- Las evidencias detalladas y los datos están fuera de Git.

## Puesta en servicio

No actualizar esta imagen sobre PostgreSQL 10. Coordinar el corte con el Compose
privado y un volumen PostgreSQL 17 restaurado y verificado. Conservar el volumen
antiguo y todos los montajes de archivos, especialmente `/data/config/secret.key`.
No arrancar trabajadores ni exponer una copia con datos reales para las pruebas.

La suite de navegador utiliza únicamente cuentas y problemas ficticios. Verifica
traducciones, cambio de idioma sin perder contenido, edición concurrente de casos,
privacidad frente a estudiantes, Resend sin enviar correo y resultados WA/AC.

Resend necesita un remitente de un dominio verificado y una API key privada en
la administración. El dominio web `lj.isilp.com` no acredita por sí solo el dominio
remitente. La prueba real de correo sigue pendiente de configuración del operador.

La ruta privada de versión acepta `/api/version` y `/api/version/`, con
regresión para conservar la compatibilidad del healthcheck y la CI.
