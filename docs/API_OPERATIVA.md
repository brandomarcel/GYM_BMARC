# API operativa para Angular GYM

El frontend será un proyecto Angular independiente. Frappe conserva cálculos,
permisos y persistencia. Estas APIs autenticadas de lectura sirven al panel de
recepción y al historial de asistencias; no crean cobros, contratos ni ingresos.

Se mantiene la sesión por cookie Frappe y la protección CSRF existente para POST.
No introducir JWT, claves API ocultas, `allow_guest` ni autorización basada solo
en filtros del cliente. Configurar el proxy/origen al preparar Angular; no asumir
CORS abierto. Las respuestas RPC usan el envoltorio estándar `message` de Frappe.

## Contexto

`gym_management.api.context.get_context` devuelve negocios y sucursales visibles.
El cliente elige entre ellos y envía `business`/`branch`; el servidor vuelve a
comprobar acceso. No asumir que el primer negocio es siempre el correcto ni
conservar datos del negocio anterior al cambiar selección o cerrar sesión.

## Panel

`gym_management.api.operations.get_reception_panel`

Parámetros: `business` obligatorio; `branch` opcional; `horizon_days` entre 1 y 90,
por defecto 7. Admite GET y POST autenticados. Requiere `gym.memberships.read`,
`gym.payments.read`, `gym.attendance.read` y feature GYM activa.

Devuelve:

- `business`, `branch`, `today`, `until`, `horizon_days`, `currency` (USD).
- `cards`: `active_contracts`, `expiring_contracts`, `expired_contracts`,
  `contracts_with_balance`, `outstanding`, `entries_today`, `denials_today`.
- `lists`: `expiring`, `expired`, `with_balance`, `recent_attendance`;
  como máximo `list_limit = 10` filas por lista.
- `payments_available`: indica si Lite está instalada.

Los contadores de membresías cuentan **contratos confirmados**, no personas
únicas ni derechos de acceso. Vigencia significa inicio <= hoy <= fin; un
contrato vigente puede tener acceso denegado por deuda o sede. Vencidos incluye
historial confirmado anterior a hoy, incluso si existe una renovación: no
etiquetar ese contador como «socios sin renovar». Por vencer incluye fin entre
hoy y el horizonte, ambos inclusive.

La sucursal de un contrato es su sede de origen; una asistencia pertenece a la
sede donde ocurrió. No atribuir toda la deuda de un contrato multisede a cada
sede de visita. Sin sucursal, se consolidan solo las sedes autorizadas. Los
saldos se calculan a partir de recibos confirmados de ese contrato; no de pagos
fiscales ni aplicaciones duplicadas. Sin Lite, no hay recibos disponibles y el
panel informa esa condición. Se excluyen recibos cancelados y borradores.

## Historial de asistencias

`gym_management.api.operations.list_attendance`

Parámetros: `business`, `from_date` y `to_date` obligatorios; `branch` opcional;
`result` vacío, `Permitido` o `Denegado`; `page` de 1 a 10000; `page_size`
25/50/100/200 (por defecto 50). Período máximo de 366 días, extremos inclusivos.
Admite GET y POST autenticados; requiere `gym.attendance.read` y GYM activa.

Devuelve `data`, `totals`, `pagination`, `filters`. `totals` contiene `records`,
`allowed`, `denied` de todo el resultado filtrado. `pagination` contiene `page`,
`page_size`, `total`, `has_next`. Orden: fecha/hora descendente y nombre como
segundo criterio para empates. Las páginas no constituyen un snapshot congelado;
una nueva asistencia puede desplazar filas al refrescar.

Cada fila incluye `name`, `branch`, `member`, `member_name`, `membership`,
`recorded_at`, `result`, `reason`, `recorded_by`. Los intentos denegados se
conservan. Las fechas usan la zona horaria del sitio Frappe; no usar UTC del
navegador para cambiar los límites del día.

El permiso del registro de asistencia no abre automáticamente el perfil del
visitante. `member_name` es null si el operador no puede leer su sede de origen;
los identificadores de socio/contrato pertenecen al historial de la visita y no
conceden acceso a esos documentos. Angular debe respetar esa ausencia y manejar
403 al abrir enlaces, sin recuperar perfiles por otra ruta.

## Administración

Ver [CONFIGURACION_RAPIDA.md](CONFIGURACION_RAPIDA.md). El checklist
`gym_management.api.setup.get_setup_checklist` y el selector
`get_setup_businesses` están reservados al administrador técnico System Manager
con acceso Core al negocio. No consumirlos como atajo de autorización desde la
recepción Angular. Solo consultan; los cambios usan los formularios/controladores
existentes y sus validaciones.

## Validación de esta entrega

En `gym_stage2_test.localhost` pasaron **97 pruebas GYM**, incluidas 11 de
operación/configuración. Cubren permisos, visitas desde otra sede sin exponer
el perfil, revocación, GYM deshabilitado, paginación, fechas, contratos
vencidos/futuros/cancelados, recibos cancelados y operación sin Lite. Se repitió
además el caso del checklist sin suscripción propia, aun si existiera una
licencia global habilitada.

Chromium verificó la página administrativa con un usuario técnico sintético,
el selector de negocio, los cinco pasos, los accesos a formularios, la creación
de un plan sin guardar con negocio preseleccionado y ambas APIs autenticadas.
No hubo errores JavaScript ni HTTP en esos flujos; se excluye el Socket.IO no
iniciado del servidor temporal. No se creó una interfaz Angular ni se evaluó
su integración de cookies/proxy; esa validación corresponde a la siguiente
entrega. Se retiran las cuentas/documentos sintéticos y el servidor al terminar.

Python: Ruff 0.8.1; JavaScript administrativo: ESLint 8.44 y Prettier 2.7.1.
No se modificaron apps vecinas, se migró únicamente el sitio de pruebas y no
se migró `gym_bmarc`.
