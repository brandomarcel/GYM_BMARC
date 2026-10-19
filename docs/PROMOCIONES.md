# Promociones de GYM

## Descuentos individuales implementados

`GYM Promotion` configura una campaña por negocio y plan: nombre, estado,
fechas de compra, tipo Porcentaje o Importe fijo y valor positivo. No altera el
catálogo ni la duración del plan. Se aplica a las sedes permitidas por el plan;
esta primera versión no restringe la campaña a una sucursal adicional.

En Frappe: **GYM → Promociones**, o `/app/gym-promotion`. Al crear una membresía,
seleccionar el plan y la promoción. El servidor calcula precio normal, descuento
y total. Ejemplo: precio USD 30, campaña 20 %, descuento USD 6, total USD 24.
Un porcentaje 100 % admite un contrato gratuito, sin crear un recibo ficticio.
Los cálculos redondean a centavos y el total nunca es negativo.

Sin promoción se conserva el descuento individual manual con permiso
`gym.memberships.discount` y motivo obligatorio. Con promoción no se añade un
segundo descuento. Un importe de descuento remitido por el cliente solo puede
ser cero o el propio importe calculado; no puede aumentar el beneficio.

Administración/gerencia configuran las campañas usando sus permisos de planes.
Recepción puede consultar/aplicar campañas vigentes de su negocio sin obtener
permiso para fijar descuentos manuales. Negocio, plan, acceso a la sede y fechas
se validan en servidor, también por la API y al confirmar el contrato. Las fechas
corresponden a la compra, no a la fecha futura de inicio del servicio.

El contrato conserva `promotion`, descuento, motivo y `promotion_snapshot`,
con las condiciones aplicadas, precio, total, responsable y fecha. Un borrador
se recalcula al guardar. Si la campaña cambió después de guardarlo, confirmar
falla y exige recargar, guardar y revisar antes de confirmar. Los contratos
confirmados no se recalculan al editar/desactivar la campaña o el plan.

Las renovaciones no heredan automáticamente la campaña anterior: deben elegir
una campaña vigente. Los hashes de reintento de solicitudes anteriores sin
promoción conservan su formato; solicitudes con promoción incluyen su identidad.

APIs autenticadas:

- `gym_management.api.promotions.list_promotions(business, plan, origin_branch)`:
  hasta 100 campañas vigentes, ordenadas por fin de vigencia y nombre.
- `gym_management.api.promotions.quote_price(business, plan, origin_branch,
  promotion=None, discount=0, discount_reason=None)`: devuelve precio, descuento,
  motivo, total y condiciones; no crea contratos ni cobra.
- `gym_management.api.memberships.create_membership`: admite `promotion` como
  selección adicional. Vuelve a validar y calcular; una cotización no reserva
  precio ni garantiza vigencia posterior.

Cobros y acceso toman el total del contrato. Lite calcula el borrador fiscal
con el precio y descuento pactados, sin duplicar recibos ni ingresos.

## Ampliaciones pendientes: tiempo y grupos

El diseño siguiente conserva el requisito de promociones como 2×1. No están
implementados los beneficios por tiempo, grupos, sesiones, cupones, cupos,
acumulación, elegibilidad por historial o campañas para varios planes a la vez.
No simularlos mediante socios fusionados o cobros duplicados.

## Separar plan y promoción

El plan define el servicio habitual: precio, duración, sedes y políticas. La
promoción define un beneficio temporal aplicable a uno o varios planes de un
negocio. No editar el precio del plan cada vez que aparece una campaña.

Las promociones se configuran en Frappe; Angular solicitará una cotización y mostrará
sus resultados. El servidor valida disponibilidad, elegibilidad, importes,
beneficiarios y permisos al confirmar, aunque ya haya existido una cotización.

Proponer tipos explícitos y acotados, sin un motor genérico de reglas:

| Tipo | Ejemplo | Consecuencia |
| --- | --- | --- |
| Descuento | Porcentaje o importe fijo | Cambia el precio pactado dentro de límites. |
| Beneficio por tiempo | Dos meses por el precio de uno | Un socio; cambia la vigencia pactada. |
| Beneficio por grupo | Dos personas por el precio de una | Dos socios y contratos individuales vinculados a una contratación promocional. |
| Beneficio por sesiones | Sesiones adicionales | Depende de implementar primero el modelo de sesiones. |

Un 2×1 no implica automáticamente dos personas: el tipo debe expresarse y
validarse. La campaña necesita negocio, fechas de venta, planes/sedes elegibles,
beneficio, límites y estado. Diferenciar vigencia para comprar de duración del
servicio. Condiciones como nuevos socios, renovación, cupón, cupo, acumulación
de descuentos o uso por persona requieren decisiones explícitas; no asumirlas.

## Aplicación e historial

Registrar una aplicación de promoción con su origen, responsable, beneficiarios,
condiciones y desglose confirmado. Mantener las membresías individuales con su
identidad, fechas y sedes. El pagador puede ser distinto del beneficiario; no
fusionar dos socios en un único registro ni compartir su control de acceso.

Copiar las condiciones efectivamente aplicadas al confirmar. Editar o desactivar
la campaña después no cambia contratos existentes. La elegibilidad de una
promoción publicada no es lo mismo que el permiso para conceder un descuento
manual: recepción podrá aplicar solo promociones autorizadas según las reglas
que se implementen, sin recibir permisos generales de descuento.

## Dinero, acceso y correcciones

En un 2×1 de dos personas, un total de USD 30 debe producir un ingreso total de
USD 30. No registrar USD 30 en cada contrato ni activar al segundo beneficiario
como si hubiera pagado automáticamente. La política debe definir cómo se
distribuyen precio, pagos parciales y derecho de acceso entre beneficiarios.
Decisión del usuario: el gimnasio decide el reparto al configurar su campaña;
no fijar un criterio global para todos los clientes. Prever estas opciones:

- **Reparto igual:** USD 15 por membresía cuando el total del grupo sea USD 30.
  Definir reparto determinista del centavo restante si el total no es divisible.
- **Titular y beneficiario bonificado:** USD 30 en una membresía y USD 0 en la
  otra; identificar explícitamente al titular y al beneficiario.

La campaña también debe declarar cómo se activa el acceso: según saldo/política
de cada membresía o tras el pago completo del grupo. Una membresía bonificada
no debe adquirir acceso por una regla implícita: la elección debe ser visible y
conservarse en la contratación. No asignar valores por defecto que decidan estas
reglas comerciales sin que el gimnasio las elija.

Ambas configuraciones están previstas para el flujo grupal pendiente. No están
disponibles todavía en el formulario de promociones individuales. Cambiar el
modo de una campaña futura no debe recalcular contrataciones ya confirmadas.

Los recibos actuales se originan en una membresía individual. Un cobro común
para varios contratos necesita revisar ese origen y su distribución explícita;
no se resuelve copiando un recibo ni aplicándolo por fuera de su obligación.
Reutilizar el libro compartido de Lite y conservar un solo registro del dinero
recibido. El modelo de solicitud fiscal actual también factura un contrato;
la agrupación de beneficiarios requiere una ampliación vinculada y probada.

Definir antes de habilitar: importe a pagar, mínimo de activación individual o
grupal, fechas de inicio de cada beneficiario, renovación, desistimiento de uno
de ellos, devolución y efecto de una nota de crédito. No descontar el precio
normal de forma retroactiva ni anular al otro socio por una regla implícita.

## Entrega propuesta

1. Implementar las opciones de reparto y activación por campaña/negocio; el
   usuario delegó esa elección en cada gimnasio, sin una regla global fija.
2. Configuración de campaña y cotización/confirmación en servidor; preservar
   separación de responsabilidades entre configuración, elegibilidad y aplicación.
3. Para grupos, contratación vinculada, distribución de saldo/acceso y cobros
   compartidos; diseñar esa relación antes de modificar contratos o facturación.
4. Pruebas de dos negocios, sedes, campaña vencida, límites/cupos concurrentes,
   reintentos sin duplicados, abonos, cambios de campaña e historial/correcciones.
5. Administración desde Frappe y, posteriormente, consumo desde Angular.

Mientras no exista el flujo grupal, no presentar una campaña individual ni los
planes demo como soporte completo de promociones 2×1 entre varias personas.

## Validación y piloto

Pasaron **111 pruebas GYM**, incluidas 14 de promociones, en
`gym_stage2_test.localhost`. Se verificó además el abono de USD 12 sobre un
contrato promocional de USD 24 con mínimo del 50 %, acceso permitido y borrador
fiscal por USD 24. No se emitieron documentos fiscales.

Chromium comprobó como recepción retirar/reaplicar una campaña y guardar la
membresía con precio normal USD 30, descuento USD 6 y total USD 24. Se retiraron
sus datos sintéticos y se detuvo el servidor temporal del sitio aislado.
Ruff, ESLint, Prettier y comprobación de metadatos/diff completadas.

El piloto local `gym_bmarc` se respaldó antes de sincronizar los nuevos campos.
Contiene la campaña **DEMO 10% mensual**, asociada al plan `MENSUAL-COMPLETO`,
vigente durante 30 días desde su creación: precio normal USD 30, descuento
USD 3, total USD 27. Su cotización se verificó con la cuenta de recepción.
No se crearon socios, contratos, recibos o facturas en el piloto para esta
entrega. Los otros planes demo y sus precios habituales se conservaron.
