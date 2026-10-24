# Arranque y conservación de cuentas

El contenedor aplica las migraciones con reintentos y cancela el arranque si no
puede completar la inicialización. No crea ni restablece administradores por su
cuenta. Los usuarios existentes conservan sus contraseñas y permisos.

Para crear un administrador en una instalación nueva:

```sh
python manage.py inituser --username administrador --action create_super_admin
```

Use una terminal interactiva. El comando solicita y confirma una contraseña de
al menos 12 caracteres, además de los validadores Django. No se muestra ni se
incluye en la línea de procesos. Una cuenta existente se rechaza sin modificar
su contraseña ni su rol. `--action reset` es una operación independiente y
explícita; no forma parte del arranque.

La clave se genera únicamente si no existe. Se conserva su contenido al
actualizar y sus permisos se restringen al usuario del servicio. Gunicorn y
Dramatiq usan `server`, de modo que ambos puedan leer esa clave sin permitir
lectura global. El token del juez se lee del entorno sin interpolarlo en código.

`init_db.sh` es una ayuda local de desarrollo. Reutiliza los contenedores
existentes, usa volúmenes persistentes para instalaciones nuevas y no elimina
contenedores, bases, claves ni cuentas. No es un procedimiento de despliegue.

Estas correcciones no cambian el esquema ni actualizan la versión de Django.
Antes de aplicar futuras migraciones a datos reales, respalde base, archivos,
Redis y configuración, y ensaye la restauración en un entorno separado.

## Variables de entorno de configuración

Booleanos (`COOKIE_SECURE`, `TRUST_PROXY_HTTPS`, `AI_TUTOR_MODEL_ENABLED`; por
defecto apagados): aceptan `1/true/yes/on/si/sí` y `0/false/no/off/vacío`, sin
distinguir mayúsculas. Cualquier otro valor aborta el arranque con
`ImproperlyConfigured`; nunca se interpreta como apagado en silencio.

Listas separadas por comas: `ALLOWED_HOSTS` (alias `DJANGO_ALLOWED_HOSTS`) y
`CSRF_TRUSTED_ORIGINS` (alias `DJANGO_CSRF_TRUSTED_ORIGINS`). Se usa la
principal si tiene valor, si no el alias, si no el valor por defecto; una
variable vacía cuenta como no definida. Si ambas tienen valores distintos el
arranque falla por ambigüedad.

## Healthcheck HTTP

`GET /healthz` (también `/api/healthz`) responde `200 {"status": "ok"}` si la
base de datos (`SELECT 1`) y la caché Redis responden, o `503 {"status":
"unavailable"}` sin detalles (el error queda en el log). No requiere
autenticación, es de solo lectura y admite `GET`/`HEAD`; otros métodos dan 405.
El encabezado `Host` de la sonda debe estar en `ALLOWED_HOSTS` (p. ej.
`localhost`). Nginx lo expone en `/healthz`, incluso con `FORCE_HTTPS`. El
`HEALTHCHECK` de la imagen (supervisor) no cambia.
