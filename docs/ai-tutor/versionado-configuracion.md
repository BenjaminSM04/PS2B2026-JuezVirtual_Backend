# Versionado de configuración pedagógica

Implementación verificada el 13 de octubre de 2026. La configuración de acceso de
PB-01 (`TutorProblemConfig.enabled`) sigue siendo independiente del contenido pedagógico.

Cada `TutorProblemConfigVersion` guarda problema, número consecutivo, autor, fecha,
`schema_version`, conceptos y política de pistas. El contenido es inmutable desde
su creación: una corrección crea otro borrador. Las únicas transiciones son
`draft → active → retired`. Activar otra vez la versión activa es idempotente;
para recuperar contenido retirado se crea un nuevo borrador con ese contenido.

La activación y la creación de sesiones bloquean la misma fila de problema dentro
de una transacción. Una restricción parcial garantiza una sola versión activa.
Las versiones retiradas y las sesiones que las utilizaron se conservan. PROTECT
impide eliminar problemas o autores mientras tengan versiones asociadas. Los triggers
de PostgreSQL impiden modificar contenido o reasignar una sesión incluso con SQL
directo, y prohíben borrar versiones que hayan sido activadas.

## Contrato PB-04

`ConfigContentSerializer` reutiliza `HintsSerializer` del contrato PB-04.
No se exige un ejemplo de diagnóstico completo para configurar un problema:
lenguaje, código erróneo y veredicto pertenecen al dataset, no a esta configuración.

- `schema_version`: `"1.0"`.
- `concepts`: entre 1 y 30 textos no vacíos de hasta 300 caracteres, sin duplicados.
- `hint_policy.max_help_level`: entero JSON entre 1 y 3. El nivel inicial de sesión es 0.
- `hint_policy.hints`: los tres textos distintos `concept`, `location`, `strategy`;
  son respectivamente los niveles 1, 2 y 3, con hasta 1200 caracteres cada uno.
- Se rechazan campos desconocidos, también anidados, esquemas desconocidos,
  configuraciones incompletas, niveles fuera del rango y niveles booleanos o decimales.

El límite de ayuda se consulta en la versión original de la sesión, aunque exista
una versión activa posterior con una política distinta. Los niveles superiores al
máximo configurado no pueden concederse; los tres textos siguen siendo obligatorios.

## API administrativa

Todas las rutas requieren una cuenta habilitada con permiso sobre el problema.
Se conservan los permisos de propietario/docente y gestor global y la protección CSRF.
Los problemas de concurso no admiten estas operaciones. Las respuestas usan el
sobre habitual del proyecto: `{"error": null, "data": ...}`.

| Método | Ruta bajo /api | Datos | Resultado |
|---|---|---|---|
| POST | /admin/ai_tutor/config/versions | problem_id y contenido PB-04 | Nuevo borrador; autor y número asignados por el servidor |
| GET | /admin/ai_tutor/config/versions | problem_id | Lista de versiones ordenada por número |
| GET | /admin/ai_tutor/config/versions | problem_id, version_id | Una versión, incluida la retirada |
| GET | /admin/ai_tutor/config/active | problem_id | Versión activa o null |
| POST | /admin/ai_tutor/config/activate | problem_id, version_id | Activa el borrador y retira la anterior atómicamente |

PUT/PATCH/DELETE no están disponibles para versiones. La ruta previa
`PUT /admin/ai_tutor/config` conserva su función de habilitar/deshabilitar acceso;
activar contenido no habilita automáticamente el tutor.

## Ejemplo de dos versiones

[configuracion-inicial.json](configuracion-inicial.json) contiene dos contenidos
para «Sumar dos enteros», basados en el ejemplo y las pistas de la guía PB-04.
El primer contenido aborda sintaxis; el segundo incorpora el elemento neutro de
la suma. Los metadatos `problem`, `source` y `review` son documentación:
solo un elemento de `versions`, junto con `problem_id`, se envía al POST.

Ejecutar en una base de desarrollo, sustituyendo los identificadores por un
administrador autorizado y el problema cuyo enunciado se haya comprobado:

```python
import json
from pathlib import Path
from account.models import User
from problem.models import Problem
from ai_tutor.models import TutorProblemConfigVersion
from ai_tutor.services.problem_config import create_draft, activate_version

author = User.objects.get(username="administrador")
problem = Problem.objects.get(_id="identificador-del-problema")
contents = json.loads(Path("docs/ai-tutor/configuracion-inicial.json").read_text())["versions"]

v1 = create_draft(author, problem.id, **contents[0])
activate_version(author, problem.id, v1.id)
# Iniciar una sesión aquí la vincula a v1.
v2 = create_draft(author, problem.id, **contents[1])
activate_version(author, problem.id, v2.id)
print(list(TutorProblemConfigVersion.objects.filter(problem=problem).values("version", "status")))
# [{"version": 1, "status": "retired"}, {"version": 2, "status": "active"}]
print(TutorProblemConfigVersion.objects.get(problem=problem, status="active").id == v2.id)
# True
```

La prueba `test_create_read_activate_two_versions_and_keep_original_session`
ejecuta este flujo por API, inicia una sesión con v1, verifica la lectura de v2
activa, recupera la sesión con v1 y comprueba que una nueva sesión utiliza v2.

## Migración y compatibilidad

`0003_versiones_configuracion` crea la tabla de versiones, añade
`TutorSession.config_version` con PROTECT y establece restricciones y triggers.
No inventa configuraciones ni cambia las sesiones previas: NULL documenta que su
versión pedagógica histórica es desconocida. Esas sesiones se recuperan sin
reasignarlas aunque luego se active una configuración.

Las nuevas sesiones requieren una versión activa del mismo problema. La disponibilidad
no ofrece iniciar una sesión nueva hasta que exista esa versión. El acceso habilitado,
la visibilidad y el bloqueo de concursos siguen aplicándose a las sesiones existentes.

La migración se aplica con `python manage.py migrate` durante el despliegue habitual.
La reversión elimina la estructura de versiones: solo debe usarse en una base de
prueba o con un respaldo apropiado. La prueba de migración verifica ida, vuelta,
reaplicación y conservación de sesiones heredadas en una base temporal.

## Verificación reproducible y cierre

En Windows, con Docker disponible y la imagen del backend construida:

```powershell
powershell -NoProfile -File OnlineJudge/scripts/verify_tutor_config.ps1
powershell -NoProfile -File OnlineJudge/scripts/verify_tutor_config.ps1 -FullSuite
```

El script monta el código en solo lectura y crea PostgreSQL 10, Redis 7 y una red
temporales. Los datos y archivos del backend temporal están en tmpfs; no utiliza
las bases ni los servicios del deploy. Ejecuta flake8 del tutor, check de Django,
detección de migraciones faltantes de ai_tutor y pruebas. Elimina sus contenedores y red al terminar.

La suite cubre validación PB-04, permisos, CSRF, dos versiones y lectura de la
activa, inmutabilidad, historial de sesiones, política original, auditoría,
rollback completo, numeración concurrente, activaciones simultáneas, activación
idempotente, carrera con inicio de sesión y migración reversible.

Resultados obtenidos en el entorno aislado:

| Comprobación | Resultado |
|---|---|
| Suite completa del backend | 182 pruebas aprobadas en 26,501 s |
| Última ejecución del tutor, tras proteger también el ID de versión | 46 pruebas aprobadas en 9,213 s |
| flake8 ai_tutor | Sin incidencias |
| check de Django | Sin incidencias |
| makemigrations ai_tutor --check --dry-run | Sin cambios faltantes |
| Migración 0003, reversión y reaplicación | Aprobadas por prueba de migración |
| Concurrencia de versiones y sesiones | Aprobada sobre PostgreSQL 10 |

Los [extractos de salida](evidencias/versionado-configuracion.txt) registran los
comandos, la imagen utilizada y los resultados. El chequeo global de migraciones
detectó diferencias previas en campos JSON de account, contest, options, problem
y submission; el verificador limita esa comprobación a ai_tutor. No se generaron
migraciones para esos otros módulos.

**Pendiente de cierre:** revisión pedagógica humana independiente de la configuración
inicial y evidencia enlazada en `review.notes`. PB-04 también registra esa revisión
como pendiente. La validación automática no la sustituye. Estos cambios locales
todavía deben integrarse en el submódulo backend y actualizar su puntero en deploy.
