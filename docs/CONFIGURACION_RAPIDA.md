# Configuración rápida de un gimnasio en Frappe

Frappe conserva la administración y las reglas de negocio. El frontend operativo
se construirá como un **proyecto Angular independiente**, con sesión Frappe y
permisos comprobados en servidor. No se incorporará al Angular de Facturada.

## Dónde entrar

Como administrador técnico de la plataforma (`Administrator` o un usuario con
`System Manager` y acceso Core al negocio), abrir `/app/gym-setup`, también
accesible desde **GYM → Configuración de GYM**. Crear el negocio o seleccionarlo
y seguir los accesos **Abrir / Crear**. Pulsar **Actualizar** después de volver
de un formulario.

La pantalla consulta registros básicos; no crea licencias, usuarios ni planes
por su cuenta y no acredita que todos los permisos estén configurados. No dar
`System Manager` al personal de recepción ni a los dueños de cada gimnasio
para resolver accesos. El Administrador del negocio de Core es un rol distinto
al administrador técnico de Frappe.

## Orden de configuración

1. **Negocio — `/app/facturada-business`.** Crear un `FacturADA Business`
   activo con los datos reales del gimnasio. Un negocio puede tener varias
   sucursales. No crear una `Company` heredada ni una empresa por sucursal.
2. **Suscripción al software — `/app/facturada-business-subscription`.**
   Vincular el negocio, código/nombre del plan comercial y fechas. Para un
   servicio por vigencia seleccionar `Por Tiempo` y configurar su fin; habilitar
   `GYM` (`enable_gym`). Definir los límites según lo contratado. No activar
   API, restaurante, inventario o facturación solo para que funcione GYM.
   En `Por Comprobantes`, Core elimina la fecha de fin: no usar esa modalidad
   esperando una suspensión por fecha.
3. **Sucursales — `/app/gym-branch`.** Crear las sedes del mismo negocio con
   códigos distintos, nombre y estado activo. El establecimiento fiscal es una
   relación opcional para facturar; no es requisito para registrar socios.
4. **Usuarios — `/app/user` y `/app/facturada-business-user`.** Crear cuentas
   habilitadas de tipo System User sin enviar credenciales por el chat. Vincular
   cada cuenta al negocio: Administrador para su dueño y Recepcionista para
   recepción. Una cuenta puede tener asignaciones a varios negocios.
5. **Personal por sucursal — `/app/gym-branch-user`.** Asignar explícitamente
   sucursales al recepcionista/gerente y dejar la asignación activa. El
   Administrador del negocio tiene alcance sobre sus sedes; recepción necesita
   la asignación. Desactivar una asignación retira acceso a esa sede.
6. **Planes de los socios — `/app/gym-membership-plan`.** Configurar negocio,
   código, nombre, duración en días/meses, precio y USD. Elegir acceso a una,
   varias o todas las sedes, renovación y condición de pago: Completo, Abonos
   o Credito. Para Abonos definir el porcentaje mínimo; para deuda definir
   días de gracia. El crédito necesita aprobación autorizada en el contrato.
   El plan comercial del software del paso 2 no es este plan de membresía.
7. **Prueba del circuito.** Crear un socio en `/app/gym-member`, contratar y
   confirmar una membresía en `/app/gym-membership`. Si requiere pago, registrar
   el recibo; comprobar ingreso permitido/denegado en el control existente
   `/app/gym-access` y verificar asistencias. Probar con la cuenta de recepción,
   incluyendo un intento de abrir otra sede/negocio. Los contratos conservan
   sus condiciones: editar el catálogo no modifica membresías confirmadas.

El usuario autorizó mejorar el Desk para su uso actual. Ver el recorrido guiado
en [USO_DEL_DESK.md](USO_DEL_DESK.md), con inicio, socios, membresías, cobros,
control de acceso y caja. La experiencia Angular independiente sigue pendiente.

## Cobros y caja

Los recibos internos requieren Lite instalado. No requieren activar emisión
electrónica, configurar certificado ni emitir una factura. Transferencia/tarjeta
requieren referencia; el efectivo utiliza la caja compartida de Restaurante y
una apertura/terminal autorizadas. No registrar efectivo sin preparar esa caja.
La pantalla informa disponibilidad de las apps, sin certificar la configuración
de caja ni sustituir las validaciones del cobro.

La configuración fiscal y las correcciones vinculadas se describen por separado
en [EMISION_FISCAL.md](EMISION_FISCAL.md). No afectan el orden básico de alta
operativa del gimnasio.

## Entorno y validación

La implementación se validó primero en `gym_stage2_test.localhost`. Después,
por solicitud del usuario, se respaldó y preparó el piloto local `gym_bmarc` con
un gimnasio de demostración. Ver [PILOTO_LOCAL.md](PILOTO_LOCAL.md) para los
accesos, cuentas, planes, apps y validación real del puerto 10100.

Español, Ecuador, USD y America/Guayaquil son la configuración inicial. Idioma
por usuario y ajustes regionales del sitio se administran con Frappe; los ajustes
globales afectan a todos los negocios que comparten el sitio.

La pantalla y el acceso a un formulario de plan con negocio preseleccionado
se comprobaron en Chromium con un administrador técnico sintético. Pasaron 97
pruebas GYM; la consulta del checklist no crea registros y recepción no puede
invocarla. El piloto local ya tiene configuración de demostración; los datos reales de un
cliente y su preparación de producción permanecen pendientes.

## Promociones individuales opcionales

Después de crear los planes, abrir **GYM → Promociones** (`/app/gym-promotion`).
Crear una campaña para un plan, con fechas y descuento de porcentaje o importe
fijo. Se selecciona al contratar; no modifica el precio habitual del catálogo.
Ver [PROMOCIONES.md](PROMOCIONES.md) para permisos, condiciones y límites.
