# Instalación y actualización

El artefacto ejecutable combina este backend con el frontend Vue 2 en el repositorio
`BenjaminSM04/OnlineJudge_Deploy`. Consultar allí
`docs/actualizacion-django52-pg17.md` para instalación, variables, migraciones,
respaldo, restauración y validación. El Compose exige un volumen PG17 externo
verificado; no actualizar una instalación PG10 sin el procedimiento previo.

La imagen del backend de este repositorio conserva el frontend upstream de su
Dockerfile histórico; la entrega LizardJudge completa es la imagen combinada del
repositorio de integración. No intercambiarlas sin verificar qué frontend incluyen.
CI de integración publica por SHA en GHCR después de las pruebas; no despliega
Coolify ni otro alojamiento. El operador elige cuándo actualizar.

Para instalación nueva se conserva el arranque sin administrador predecible.
Crear explícitamente con `manage.py inituser --username administrador --action
create_super_admin` y contraseña interactiva. No ejecutar reset sobre cuentas
existentes para “completar” una instalación. Modelos apagados por defecto.
