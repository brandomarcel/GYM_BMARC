# Diseño base y migración de GYM — etapa 1

Fecha de revisión: 2026-10-17.

Estado: inventario verificado y diseño propuesto para implementación gradual. Ningún DocType, dependencia o migración de este documento se ha instalado todavía. El usuario pidió soportar distintos escenarios mediante configuración; esto incluye variaciones de cobro, renovación y sedes, sin adelantar los módulos posteriores de clases y sesiones.

## 1. Inventario verificado del piloto

Consulta de solo lectura sobre `gym_bmarc`:

| Comprobación | Resultado |
| --- | --- |
| Apps instaladas | `frappe`, `gym_management`; Core y Lite no están instaladas. |
| Región | Ecuador, `es`, USD, America/Guayaquil; asistente completado. |
| Servicios | Redis cache y queue responden. Esto no verifica workers, scheduler ni Socket.IO. |
| DocTypes GYM | Los diez pertenecen a `Gym BMARC`; todos tienen cero registros. |
| Archivos adjuntos | Cero asociados a Company, Customer, memberships_register, Membership_Type, products o sales_products. No equivale a inventariar todos los archivos del sitio. |
| Rol `Admin_Gym` | No existe en el piloto; está referenciado en reportes/workspace del código. |

Los diez DocTypes revisados son Company, Customer, Medidas, Membership_Type, memberships_register, payment_method, Planes, Planes Contratados, products y sales_products. El estado vacío simplifica este piloto, pero debe comprobarse otra vez al ejecutar una migración. No inferir que otros sitios están vacíos.

### Dependencias reales y riesgos

| Componente | Evidencia en código | Consecuencia |
| --- | --- | --- |
| Negocio Core | `facturada_core/api/business.py` y DocType `FacturADA Business` | Reutilizar autorización; `tax_id` es obligatorio y su controlador exige 10 o 13 dígitos y controla duplicados. Company de GYM no tiene ese dato: no inventarlo al migrar. |
| Licencia | `facturada_core/api/license.py` | Existe feature `gym`; no hay aplicación efectiva de ella en la operación actual de GYM. |
| Roles | `facturada_core/api/business_permissions.py` | No hay permisos `gym.*` ni rol específico de recepción. Diseñar ampliación canónica; no asignar un rol de caja/facturación amplio solo para registrar asistencias. |
| Establecimientos | `FacturADA Establishment` | Entidad fiscal por negocio con código obligatorio. No cubre por sí sola una sede operativa sin facturación. |
| Terminales | `FacturADA POS Terminal` | Exigen establecimiento y punto de emisión; no son equivalentes a una sucursal ni a una asignación de recepción. |
| Cliente fiscal | `FacturADA Lite Customer` | Exige identificación fiscal. El Customer de GYM no la tiene; un socio y el pagador de su factura pueden ser personas distintas. |
| Nota POS | `facturada_lite/api/pos_sale.py` y controlador `FacturADA POS Sale Note` | Requiere terminal y pago completo al cobrar; no modela abonos de membresías por sí sola. |
| Abonos fiscales | `facturada_lite/api/collections.py` | Ya existen cuotas/abonos sobre factura a crédito numerada. No sirven para anticipos sin factura; consultan `FacturADA Restaurant Cash Opening`. Revisar permisos, concurrencia y caja antes de reutilizarlos. |
| Caja existente | `facturada_restaurante/api/frontend.py` | Aperturas/cierres agregan órdenes, notas POS, facturas y abonos fiscales. Una nueva fuente GYM no aparecerá automáticamente y podría duplicarse si se registra también como factura cobrada. |
| Instalación | `facturada_core/install.py`, `facturada_lite/install.py`, hooks | Hay tareas de índices y sincronización. Lite mantiene `required_apps` comentado: instalar en orden explícito y probar sitio limpio. |

`FacturADA Business.business_model` representa Facturación Simple/ERPNext; `pos_experience` representa General/Retail/Restaurante. Ninguno debe usarse para elegir modalidades de gimnasio.

## 2. Estructura propuesta

Los nombres siguientes son propuestas de DocTypes con prefijo para evitar colisiones, no esquemas existentes. Todos los documentos operativos principales tienen `business` obligatorio e indexado; cada Link debe validarse contra ese negocio en el servidor. Las tablas hijas heredan el ámbito del padre y no son accesibles como documentos independientes.

| Entidad propuesta | Campos y relaciones mínimos | Reglas |
| --- | --- | --- |
| `GYM Business Settings` | `business` único, valores predeterminados de cobro/renovación/acceso | Un registro por negocio, no un Single global. No replica licencias ni datos fiscales. |
| `GYM Branch` | `business`, `branch_code`, `branch_name`, `status`, dirección, `establishment` opcional | Código único por negocio. El establecimiento enlazado pertenece al mismo negocio. No exigir configuración fiscal para registrar asistencia. |
| `GYM Branch User` | `business`, `branch`, `user`, `status` | Asignación única negocio/sede/usuario; requiere asignación activa al negocio en Core. No otorga funciones por sí misma. |
| `GYM Member` | `business`, `member_code`, nombres, contacto, nacimiento opcional, `status`, `home_branch` opcional | Código único por negocio; socio independiente de `User`. El mismo correo o teléfono no se considera identidad global única. |
| `GYM Member Measurement` (hija) | Fecha, medidas y unidades explícitas | Acceso sensible separado de recepción; conservar valores históricos originales durante migración. |
| `GYM Membership Plan` | `business`, código, nombre, estado, duración/unidad, precio, `currency`, políticas, `lite_item` opcional | Catálogo por negocio; servicio Lite sin stock cuando se integre. No es un plan SaaS. |
| `GYM Membership` | `business`, `member`, `plan`, `origin_branch`, fechas, estado contractual, condiciones copiadas, `previous_membership`, identificador de reintento | Contratación histórica independiente del catálogo. Socio, plan y sedes deben pertenecer al negocio. Renovar crea otra contratación enlazada. |
| `GYM Membership Branch` (hija) | `branch` | Lista explícita de sedes habilitadas; permite una, varias o todas según política. |
| `GYM Attendance` | `business`, `branch`, `member`, `membership`, instante, resultado, motivo, responsable, clave de reintento | La sede es donde ocurre el acceso. Registrar decisiones permitidas y denegadas para auditoría, con retención definida. |
| `GYM Member Payer` (hija) | `lite_customer`, indicador predeterminado | Pagadores fiscales opcionales del mismo negocio. Una factura puede pagar la membresía de un menor o dependiente. No copiar medidas al cliente fiscal. |

La fase base implementará negocio, sedes, asignaciones y socios primero. Políticas, contratos, cobros y asistencias se agregan después; no crear todos los DocTypes sin sus validaciones.

### Separar estados

- Contrato: Borrador, Confirmada, Cancelada. Vigencia y elegibilidad se calculan por fecha y política; no confiar en un `Activo` manual permanente.
- Cobro: Sin pago, Parcial, Pagado, con deuda vencida calculada por fechas. Derivado de movimientos confirmados y reversos, no editable por el navegador.
- Acceso: Permitido/Denegado con motivo (sede, vigencia, deuda, suspensión, falta de membresía). Una factura pendiente SRI no implica por sí sola que el socio no pagó.
- Documento fiscal: estados de Lite, sin redefinirlos en GYM.

Suspensión o congelamiento debe ser un evento fechado y auditado; no eliminar historial ni extender fechas silenciosamente. Su interfaz puede incorporarse después del flujo mínimo.

## 3. Políticas configurables solicitadas

El negocio define valores predeterminados; el plan puede elegir otros y el contrato conserva una copia de los valores aplicados. Los cambios de condiciones requieren permiso específico, motivo y trazabilidad. No permitir expresiones ejecutables ni reglas Python proporcionadas por clientes.

| Política | Escenarios previstos | Validación |
| --- | --- | --- |
| Condición de pago | Pago completo, abonos, crédito autorizado | Cobrar parcialmente no equivale a dar acceso automáticamente. |
| Umbral de acceso | Total pagado; mínimo fijo o porcentual; crédito aprobado | Umbral válido entre cero y el total. Crédito explícito con autorizador, vencimiento y motivo; no activarlo por omisión. |
| Deuda | Acceso bloqueado al vencer o gracia limitada | Días de gracia no negativos, copia al contrato. Permitir cobrar deuda aunque el acceso esté bloqueado. |
| Renovación | Continua desde el vencimiento; desde la fecha de regreso; fecha futura elegida | Validar intervalos, evitar solapamientos involuntarios y mantener vínculo a la contratación anterior. |
| Acceso por sede | Una sede; lista de sedes; todas las sedes activas del negocio | Una lista es una fotografía del contrato; el modo todas puede incluir nuevas sedes y debe expresarlo al contratar. Nunca incluye otro negocio. |
| Duración | Días o meses de calendario | Definir semántica de fin, fin de mes y año bisiesto; no sustituir un mes por 30 días. |
| Descuentos | Importe o porcentaje | Servidor valida límites, permiso y motivo; historial conserva precio y descuento aplicado. |

Propuesta técnica de fechas: fechas de inicio/fin inclusivas. Para N días, fin = inicio + N días − 1; para N meses, fin = suma de meses de calendario − 1 día usando utilidades Frappe y ajuste de fin de mes. Renovación continua inicia al día siguiente del vencimiento anterior; desde regreso usa la fecha explícita del retorno. Probar 28/29/30/31 y no convertir contratos históricos automáticamente a esta nueva semántica.

No activar crédito ni mínimos cero de forma implícita. Para alta del primer negocio, presentar las políticas para elección antes de confirmar la primera membresía. Los valores regionales no autorizan a asumir tasas tributarias: impuestos y redondeo fiscal se resuelven mediante Lite.

Clases con cupos, paquetes de sesiones, entrenadores y reservas siguen en etapa 5. El modelo por tiempo no debe simular sesiones con días ni clases con sucursales.

## 4. Cobros, caja y facturación: decisión de integración

La decisión de diseño es separar la obligación comercial y el pago del resultado fiscal. No habrá una segunda emisión SRI ni un segundo saldo manual en GYM.

Antes de implementar cobros, completar una revisión específica y elegir el mecanismo compartido de registro operativo:

1. Facturas a crédito: reutilizar `FacturADA Lite Invoice Collection` para abonos fiscales donde sus precondiciones se cumplan. El saldo de esa factura se deriva de Lite.
2. Anticipos o cobros sin factura: el módulo actual no los representa. Proponer una extensión compartida de cobros en Lite con origen operativo, aplicaciones de importes, reversos e idempotencia, con impacto evaluado en su `AGENTS.md`. No crear una caja GYM paralela ni exigir una factura ficticia para registrar un abono.
3. Cada movimiento de dinero tendrá una sola identidad y será contado una vez. Enlazar o aplicar un anticipo a una factura no genera otro ingreso de caja. Un contrato puede tener varios pagos, y un pago puede distribuirse solo mediante aplicaciones explícitas cuya suma no exceda lo recibido.
4. El puente a caja debe aceptar el nuevo origen sin sumar de nuevo pagos fiscales, y respetar negocio/sede/terminal/caja abierta. El refactor compartido de caja necesita diseño y pruebas de regresión de POS/Restaurante; no instalar Restaurante como dependencia oculta solo para que una consulta no falle.
5. Factura y socio se relacionan mediante origen y pagador; no imponer una factura por asistencia ni una factura por abono. Definir la agrupación al implementar el puente fiscal, sin alterar comprobantes autorizados.

Este es un trabajo previo de la etapa 3, con reutilización de código de Lite y pruebas de concurrencia. Hasta completarlo, no ofrecer abonos, anticipos ni cierres de caja como funciones implementadas.

## 5. Autorización y aislamiento

Una operación requiere negocio autorizado, módulo contratado, permiso de acción y alcance de sede cuando corresponda. El negocio recibido es un parámetro no confiable; comprobar también el negocio de cada documento referenciado.

- Usar `resolve_business`, `require_business_permission` y feature `gym`; ampliar `business_permissions.py` con permisos `gym.*` al implementar. Evaluar un rol Recepcionista en la matriz y selección de roles de Core para no conceder facturación o configuración por accidente.
- Administrador del negocio: todas sus sedes. Otros roles: sedes asignadas; Gerente con acceso global solo mediante alcance explícito, no por asumir que gestiona todas las sedes.
- Un recepcionista necesita una vista mínima del socio para comprobar membresía multisede; no debe recibir medidas corporales, historial de cobros completo ni datos fiscales por ese motivo.
- Proponer permisos separados para socios, medidas, planes, membresías, crédito, cobros, asistencia, reportes y gestión de sedes. Documentar una matriz concreta al implementar cada flujo; el wildcard de Administrador se conserva.
- Aplicar filtros de listas y permisos de documentos en Desk y REST genérica de Frappe, además de los métodos propios. Los hooks de permisos actualmente comentados no protegen los nuevos esquemas.
- Tablas hijas y archivos privados comprueban acceso al padre. Auditar imágenes y QR existentes: un archivo público o datos personales enviados al servicio QR no quedan aislados por agregar un campo `business`.
- El QR no debe contener datos sensibles ni funcionar como autorización por sí solo. Diseñar token opaco revocable; validar membresía y sede en servidor y no registrar el token completo en logs.
- Índices únicos compuestos por negocio para códigos y claves de reintento; validar también la carga original al repetir una clave. Bloquear la obligación durante aplicaciones de cobro concurrentes.

No se verificó en esta etapa el aislamiento completo de Core/Lite; se revisaron puntos de integración. La existencia de helpers de autorización no sustituye pruebas de todos los canales usados por GYM.

## 6. Inventario de cambios y migración

| Origen actual | Destino o tratamiento propuesto | Consumidores afectados |
| --- | --- | --- |
| Company | Mapeo explícito a `FacturADA Business`; nombre/logo reutilizables, identificación faltante requiere dato válido | `company.js`, API `public/apiRest.py`, User Permission, Links y filtros de reportes. |
| Customer | `GYM Member`, con claves origen/destino y medidas hijas; cliente fiscal opcional separado | `customer.py/js`, `memberships_register`, reportes SQL, QR y adjuntos. |
| Membership_Type | `GYM Membership Plan` por negocio | JS de planes/membresías y Links; `company` pasa por mapeo. |
| memberships_register | `GYM Membership`, preservando fechas y condiciones originales | JS de recibo/descuento/fechas, enlaces a clientes, pagos y reportes. |
| Medidas | Medidas del nuevo socio, conservando fecha y valores crudos | No convertir cadenas a números ni corregir nombres como `espada` perdiendo datos. |
| payment_method | Evidencia histórica a reconciliar con el registro de cobros | Las filas sin fecha/estado/identidad no prueban por sí solas un ingreso confirmado. No inventar caja ni movimientos bancarios. |
| Planes / Planes Contratados | Historia de contratación del software; no convertir en membresías de socios | API y Company JS. Crear licencia Core solo con mapeo comercial explícito. |
| products / sales_products | Mapeo a artículos Lite y fuentes históricas, tras revisar significado y datos | No crear facturas ni movimientos de inventario retroactivos solo por migrar. |
| Workspaces / reportes / page/prueba | Nuevas rutas GYM y reportes por negocio/sede | Actualizar nombres y filtros; `prueba` referencia un reporte ausente. Mantener o retirar referencias solo con justificación. |

### Orden propuesto

1. Preflight de solo lectura repetible: apps/versiones, propiedad de DocTypes, cantidades, relaciones huérfanas, compañías vacías, cruces de compañía, adjuntos y usuarios. No registrar valores personales en el informe versionado.
2. Respaldar el sitio y archivos antes de cambios; ensayar restauración en el entorno apropiado. Registrar versiones y resguardar configuraciones/secretos fuera del repositorio.
3. En un sitio de prueba limpio instalar Core, después GYM con sus esquemas nuevos; incorporar Lite cuando su integración y dependencias estén verificadas. Core será dependencia explícita de la nueva base. Lite será dependencia explícita del flujo fiscal, no una importación implícita.
4. Crear esquemas con prefijo `GYM`, sin renombrar/eliminar los DocTypes heredados. Conservarlos temporalmente para compatibilidad, pero impedir su uso como un canal multiempresa sin controles durante la transición.
5. Crear mapeos explícitos y repetibles por origen/destino, primero negocios/sedes, después socios/planes/contratos, medidas, cobros reconciliados y archivos. Si hay datos y falta RUC, sede o asignación, detener ese mapeo y reportar; no elegir por nombre, primer registro o usuario dueño.
6. Para el piloto vacío no se crean negocios, sucursales, licencias activas ni clientes fiscales ficticios. Preparar datos sintéticos únicamente en el sitio de pruebas; dar de alta el negocio real con sus datos cuando corresponda.
7. Migrar API/JS/reportes de manera coordinada. La ruta legacy `get_company_and_plans(user)` debe rechazar suplantación y validar acceso mientras siga expuesta; conservar contrato compatible o documentar sustitución, nunca mapear al primer negocio.
8. Comparar cantidades por entidad/negocio, relaciones, condiciones originales, cobros conciliados y adjuntos; ejecutar dos veces y comprobar que no duplica datos ni efectos.
9. Habilitar nuevos flujos después de pasar validaciones. Retirar modelos históricos en una migración futura explícita; no eliminarlos al terminar la primera instalación.

Las migraciones de esquema en MariaDB pueden hacer commits implícitos. Un rollback SQL no garantiza deshacer DDL; el retorno se basa en restauración ensayada y código compatible. Una migración nunca emite facturas, envía WhatsApp, consulta datos fiscales en producción ni cobra dinero.

### Portabilidad a sitio exclusivo

El manifiesto de extracción incluirá negocio y dependencias, sedes, miembros, contratos, aplicaciones y movimientos financieros, adjuntos, configuración, permisos, documentos fiscales y trabajos pendientes. Tablas hijas se trasladan con sus padres. No extraer usuarios/sesiones/roles globales indiscriminadamente; reconstruir asignaciones y resolver usuarios ya existentes en destino. Las credenciales se transfieren o rotan de forma segura.

Una prueba posterior debe trasladar A desde un sitio A+B y demostrar que no lleva datos de B, conserva integridad y no deja dos emisores activos para el mismo origen fiscal. No se promete extracción automática antes de ese ensayo.

## 7. Entregables de implementación y validación

Primera entrega de código propuesta (etapa 2): dependencia Core verificada en sitio limpio; `GYM Branch`, `GYM Branch User`, `GYM Member`; permiso de negocio y sede; pruebas con A/B y usuarios sin privilegios de sistema. Agregar hooks de permisos y pruebas de API/Desk antes de habilitar creación operativa. Los contratos/cobros no se adelantan para compensar una base sin aislamiento.

Archivos previstos al ejecutar esa entrega:

- GYM: `hooks.py`, nuevos controladores/esquemas/tests bajo `gym_bmarc/doctype/gym_*`, helpers bajo `api/`, registro de patches solo si hay transformaciones de datos, guía y documentación.
- Core: `api/business_permissions.py` y tests; esquemas/selección de roles e interfaces que los consumen únicamente si se introduce el rol de recepción. Revisar su `AGENTS.md` y no modificar permisos existentes de otros módulos sin pruebas de regresión.
- Lite/Restaurante: sin cambios para la primera base. Su integración se aborda con una revisión propia antes de implementar cobros o caja.

Pruebas mínimas por entrega:

| Área | Casos necesarios |
| --- | --- |
| Instalación | Sitio limpio sin ERPNext; dependencias presentes; actualización del piloto vacío. |
| Seguridad | Usuario A no accede a B por listas, IDs, escritura, reportes, hija ni archivo; usuario multisede solo opera en su alcance; usuario multinegocio cambia contexto explícitamente. |
| Licencia | GYM deshabilitado deniega operación; rol permitido no sustituye licencia ni sede. |
| Contratos | Pago total, mínimo de abono, crédito aprobado, deuda/gracia; retorno, continuidad y fecha futura; fin de mes y año bisiesto. |
| Concurrencia | Repetición de clave con misma y distinta carga; dos cobros simultáneos; una asistencia repetida no consume dos veces un derecho futuro. |
| Fiscal | Proveedor simulado; factura pendiente no se duplica; un abono aplicado no se cuenta dos veces; reversos y notas de crédito conservan historia. |
| Migración | Cero registros, datos válidos, huérfanos, mezcla de compañías y reejecución; no inventar identificación, pagos ni facturas. |

La auditoría actual no ejecutó pruebas de aplicación porque todavía no cambió comportamiento. La etapa 1 deja el diseño de base y el inventario listos; la revisión de cobros compartidos queda como requisito explícito antes de la etapa 3, no como funcionalidad ya resuelta.
