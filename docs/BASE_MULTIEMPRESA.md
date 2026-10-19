# Base multiempresa y multisucursal — etapa 2

Estado: base instalada y validada el 2026-10-17 en `gym_stage2_test.localhost`, sin ERPNext. Pasaron instalación limpia, migración, pruebas de integración y flujo de socio en Chromium. No se ha migrado `gym_bmarc` ni ningún sitio de producción.

## Alcance implementado en código

- Dependencia explícita de FacturADA Core.
- `GYM Branch`: sucursal de un negocio, código único por negocio, establecimiento fiscal opcional del mismo negocio.
- `GYM Branch User`: asignación única de usuario/sede/negocio, subordinada a una asignación activa de Core.
- `GYM Member`: socio por negocio, código único y sede de registro obligatoria en esta primera base. No incluye datos fiscales ni medidas corporales.
- Validación de pertenencia de Links, códigos, nombres, correo y nacimiento; el negocio de un documento guardado no puede cambiarse. Una asignación guardada tampoco puede cambiar de usuario/sede.
- Rol de negocio `Recepcionista` en Core y permisos `gym.*`. La disponibilidad de ese rol depende de la feature `gym`.
- Rol técnico `GYM User` para Desk, agregado mediante una asignación activa autorizada en Core. No es un rol de negocio y no concede acceso sin comprobar negocio, licencia, acción y sede en cada petición.
- Workspace `GYM`, formularios y búsquedas de Links limitadas al negocio autorizado.
- Restricciones en listas, documentos y archivos privados; las descargas privadas comprueban el documento padre. No se permiten adjuntos públicos ni compartir documentos GYM para saltarse las asignaciones.
- La API heredada `get_company_and_plans(user)` rechaza consultar como otro usuario y comprueba permiso de lectura de Company.

Los enlaces hacia Core utilizan búsquedas autorizadas de GYM. La validación visual genérica de esos enlaces se omite porque recepción no tiene lectura genérica de los modelos Core; los controladores validan pertenencia, licencia y permisos en el servidor al guardar. La lista predeterminada no incorpora joins al nombre del negocio que requieran ampliar ese acceso.

Matriz de la base:

| Rol de negocio | Sucursales | Personal asignado | Socios |
| --- | --- | --- | --- |
| Administrador | Lee y administra todas las del negocio | Administra asignaciones | Lee y administra todas las sedes de su negocio |
| Gerente | Lee las asignadas | Solo consulta su asignación | Lee y administra socios de sus sedes asignadas |
| Recepcionista | Lee las asignadas | Solo consulta su asignación | Lee y administra socios de sus sedes asignadas |
| Otros roles | Sin permisos GYM en esta entrega | Sin permisos GYM | Sin permisos GYM |

El administrador técnico de Frappe sigue siendo un usuario de confianza global. No asignar `System Manager` a empleados de gimnasios. Para desactivar una sede o una asignación se conserva el historial mediante `Inactivo`; las restricciones se comprueban en vivo aunque el usuario conserve el rol técnico.

La etapa 3 añade consulta mínima de identidad para asistencia multisede sin exponer todo el perfil. Ver [MEMBRESIAS_Y_COBROS.md](MEMBRESIAS_Y_COBROS.md).

## Instalación y pruebas

El sitio de pruebas creado es `gym_stage2_test.localhost`. Para reproducir en un entorno donde ese sitio todavía no exista, su creación requiere acceso administrativo local de MariaDB:

```bash
cd ~/frappe-bench
bench new-site gym_stage2_test.localhost
```

Introducir las contraseñas en los prompts de la terminal, no en documentación ni chat. No usar `--set-default`, no reemplazar sitios existentes ni ejecutar `reinstall`.

Después de comprobar que es un sitio nuevo destinado a pruebas:

```bash
bench --site gym_stage2_test.localhost install-app facturada_core
bench --site gym_stage2_test.localhost install-app gym_management
bench --site gym_stage2_test.localhost set-config allow_tests 1 --parse
bench --site gym_stage2_test.localhost run-tests --module facturada_core.api.test_gym_permissions
bench --site gym_stage2_test.localhost run-tests --module gym_management.tests.test_business_isolation --skip-test-records
```

Las pruebas de aislamiento usan usuarios y negocios sintéticos, simulan llamadas a las funciones de la API genérica de Frappe y consultan MariaDB real; no emiten comprobantes ni llaman a proveedores. Comprueban listas, IDs conocidos, creación/escritura/borrado, vínculos cruzados, cambio de negocio, asignaciones múltiples, revocación, licencia, archivos, descarga privada y suplantación de usuario en la API heredada.

### Resultados verificados

| Validación | Resultado |
| --- | --- |
| Instalación limpia Core → GYM | Correcta, sin ERPNext. |
| Migración posterior / hooks de índices | Correcta, sin duplicados. |
| `gym_management.tests.test_business_isolation` | 13 pruebas aprobadas. |
| `facturada_core.api.test_gym_permissions` | 2 pruebas aprobadas. |
| Usuarios de negocio Core | 8 pruebas aprobadas. Se explicitó la licencia POS en el test que crea un Cajero; antes dependía del estado previo del sitio. |
| Suscripciones Core | 6 pruebas aprobadas. |
| HTTP real como recepción | Login y Desk 200; socio propio 200; socio de otro negocio/sede y archivo privado ajeno 403; contexto con solo el negocio autorizado. |
| Chromium | Login, apertura de formulario, guardado de socio y listas limitadas a la sede; sin excepciones JavaScript al finalizar. |
| Ruff / sintaxis / diff | Correctos en el alcance modificado. |

Las fixtures de navegador y sus cuentas se retiraron, y se eliminó el archivo temporal de credenciales. La suite de aislamiento revierte sus datos. El sitio queda reservado para pruebas, con `allow_tests` habilitado; no usarlo como sitio de clientes. El servidor temporal del puerto 10101 se detuvo al finalizar la validación web.

Antes de migrar el piloto, comprobar que sigue vacío, respaldarlo y validar la instalación limpia y las pruebas. Las hooks de instalación/migración crean el rol técnico, índices compuestos y sincronizan el rol para asignaciones activas existentes. No crean negocios, licencias, sucursales ni socios ficticios.

## Validación manual después de las pruebas

1. En un entorno de desarrollo identificado, crear un negocio con datos válidos y habilitar su licencia `gym` mediante el mecanismo de Core. Crear un usuario Administrador del negocio; conservar Administrator de Frappe solo para soporte técnico.
2. Desde el contexto de ese administrador crear dos sucursales en `/app/gym-branch` y asignar un Recepcionista de Core a una sola sede en `/app/gym-branch-user`.
3. Entrar como recepcionista, abrir `/app/gym-member` y crear un socio en la sede asignada. Comprobar que no puede escoger otra sede ni crear sucursales o asignaciones.
4. Repetir con un negocio B. Probar lectura por ID, escritura y descargas de B con usuario A: deben denegarse.
5. Desactivar asignación, licencia o negocio y comprobar denegación inmediata en las rutas nuevas.

## Límites y riesgos

- El override `GymAwareFile` conserva el comportamiento original de File para otras apps y añade controles de descargas y validación temprana para GYM. Revisar compatibilidad antes de instalar otra app que también sobrescriba File.
- Las operaciones administrativas de Core y la autorización de las apps vecinas no fueron auditadas completamente por esta entrega. No ampliar permisos genéricos sobre esos modelos para facilitar los formularios GYM; usar los contratos de Core.
- No hay migración automática de Company/Customer heredados. Se conservan sus esquemas y datos; los usuarios nuevos no reciben sus roles antiguos.
- Esta entrega describe la etapa 2. La etapa 3 posterior añade membresías, cobros y asistencia; sesiones y emisión fiscal siguen pendientes.
- La base está validada en el sitio aislado. Adoptarla en el piloto requiere respaldo, verificación de datos y migración; esa adopción y los datos reales del primer negocio no forman parte de esta validación.
