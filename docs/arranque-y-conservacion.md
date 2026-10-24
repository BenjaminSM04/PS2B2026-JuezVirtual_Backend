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
