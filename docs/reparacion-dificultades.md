# Dificultad de los bancos QDUOJ

La importación conserva `difficulty` si contiene `Low`, `Mid` o `High` y rechaza
otros valores explícitos. Sin ese campo, reconoce las etiquetas exactas
`Dificultad: Baja`, `Dificultad: Media` y `Dificultad: Alta`. Sin etiqueta reconocida
o con niveles contradictorios, utiliza `Mid`. La exportación incluye `difficulty`.
No cambia los problemas importados anteriormente de forma automática.

## Reparar el lote nuevo después del despliegue

Ejecutar desde `/app` en el contenedor **backend actualizado**, con el entorno
habitual de Django. Primero revisar la simulación:

```sh
python manage.py reparar_dificultades
```

Para aplicar los cambios revisados:

```sh
python manage.py reparar_dificultades --apply
```

El comando considera exclusivamente los 100 IDs exactos `BLZ2-046` a `BLZ2-145`,
ambos incluidos, fuera de concursos. Debe existir un único problema público por
ID y una única dificultad reconocida entre sus etiquetas. Las copias en concursos
no se modifican ni cuentan como duplicados públicos. Informa IDs ausentes,
duplicados públicos, etiquetas ausentes o contradictorias y problemas sin cambios.
Las etiquetas repetidas del mismo nivel no generan contradicción.

Con `--apply`, bloquea las filas seleccionadas y aplica todas las actualizaciones
en una única transacción; un error revierte todas. Solo escribe `difficulty`,
sin cambiar autoría, contenido, etiquetas, casos ni fechas. Se puede repetir sin
cambiar filas que ya tienen el nivel correcto. El lote anterior de 45 ejercicios
y cualquier otro ID quedan fuera del alcance: requieren revisión y edición
administrativa independiente. No se ejecutó esta reparación en producción.
