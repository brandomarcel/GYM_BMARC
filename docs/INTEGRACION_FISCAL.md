# Integración fiscal de GYM: decisión y plan de implementación

Revisión del código: 2026-10-17. La etapa 4.1 está implementada y validada en sitio aislado: ver [BORRADOR_FISCAL.md](BORRADOR_FISCAL.md). La etapa 4.2 aplica recibos y concilia saldos: ver [APLICACIONES_DE_RECIBOS.md](APLICACIONES_DE_RECIBOS.md). Emisión y seguimiento (4.3) implementados con proveedor simulado: ver [EMISION_FISCAL.md](EMISION_FISCAL.md). Corrección fiscal y devolución vinculada pendientes. Esta decisión no autoriza cambios de producción.

## Camino elegido

Dentro de un mismo sitio Frappe, GYM usará los servicios Python de `facturada_lite`, con la sesión y permisos reales del operador. `facturada_core` conserva negocio, licencia, configuración tributaria y proveedor. `facturada_api` se reserva para un sistema que llama desde fuera del sitio.

```text
GYM en el mismo sitio → servicios Lite → Core/proveedor → SRI
Sistema externo → facturada_api → servicios Lite → Core/proveedor → SRI
```

La API externa y Lite no son motores alternativos. La API autentica al integrador y llama al mismo motor Lite. Añadir HTTP, API keys y otra autenticación dentro del mismo sitio añade configuración y fallos sin resolver la conciliación de pagos.

Si un gimnasio se traslada a un sitio exclusivo que también contiene Core y Lite, conserva la integración local. Solo si se decide separar operación GYM y facturación entre sitios/servidores se necesita un conector remoto con la API externa. Ese conector requiere mapeo de identidades, reintentos durables y conciliación entre bases; no se implementará anticipadamente.

## Evidencia del repositorio

| Código revisado | Comportamiento y consecuencia |
| --- | --- |
| `facturada_api/api/rest.py::_create_invoice` | Exige feature `api`, mapea el payload y llama `build_invoice_doc`, `assign_electronic_identity` y `submit_lite_invoice`. Usa contexto Administrator después de autenticar al cliente externo; no trasladar ese contexto al flujo de recepción GYM. |
| `facturada_lite/api/invoice.py::build_invoice_doc` | Resuelve negocio y exige `billing.create`; admite `source_doctype`/`source_name`, cliente, servicio, terminal, establecimiento y punto de emisión. Al emitir comprueba feature `billing`, cuota y configuración. |
| `facturada_lite/api/invoice.py::create_invoice` / `create_and_emit` | Ya separan borrador y emisión. Las funciones existentes contienen sus elevaciones internas; GYM no debe copiar esos atajos ni desactivar las comprobaciones de autorización. |
| `facturada_lite/api/invoice.py::refresh_emission_status` | Delega la consulta al servicio compartido de estado; GYM no necesita otra implementación de consulta o polling. |
| `facturada_lite/api/collections.py` | Los abonos actuales exigen factura numerada a crédito y crean un ingreso independiente; no sirven directamente para volver a registrar recibos GYM ya cobrados. |
| `facturada_restaurante/api/frontend.py::get_cash_payment_totals` | Suma por separado recibos y abonos fiscales. Excluye facturas con origen del conjunto de facturas directas. Duplicar un recibo como abono fiscal sumaría dos veces. |
| `gym_management/payments.py` / `facturada_lite/api/receipts.py` | Ya existe fuente de verdad para dinero recibido contra contratos y autorización por negocio/sede. Preservarla. |

Los campos de origen de una factura por sí solos no acreditan permisos sobre la membresía ni garantizan unicidad. El puente debe verificar origen, pertenencia, condiciones y exclusión de solicitudes concurrentes en servidor.

## Separación de responsabilidades

- GYM prepara la solicitud fiscal desde un contrato confirmado, valida acceso al socio/contrato y conserva la relación con el documento de origen.
- Lite valida cliente, servicio, impuestos, importes y formas de pago; crea y administra la factura, notas de crédito, documentos y estado electrónico.
- Core autoriza negocio/acción/features, resuelve ubicación fiscal y administra configuración y proveedor.
- El recibo compartido representa dinero recibido. Su aplicación a una factura solo asigna ese importe: no vuelve a cobrar ni crea otro ingreso de caja.

Recepción conserva sus permisos operativos actuales. No recibirá `billing.create/manage` automáticamente. La primera versión fiscal usará un operador con permisos fiscales y alcance GYM sobre la sede correspondiente, por ejemplo Administrador o Gerente asignado. Tener solo rol Facturacion tampoco debe permitir consultar todos los socios sin autorización GYM. Un permiso fiscal limitado a recepción sería una ampliación posterior de Core, con pruebas, no una API key oculta.

## Diseño de cobros y aplicaciones

Se necesita una aplicación compartida en Lite entre `FacturADA Payment Receipt` y factura, con negocio, importe y estado auditable. Su nombre/esquema final se concretará al implementarla; no es otro registro de cobro.

1. Validar que recibo, factura y origen pertenecen al mismo negocio y a la obligación autorizada. Solo aplicar recibos confirmados y facturas aptas para el escenario; no aplicar a comprobantes anulados/reemplazados por omisión.
2. Bloquear en orden consistente: socio → contrato → factura → recibo/aplicaciones y caja cuando corresponda. Verificar también el orden de cancelación y los locks ya adquiridos por Frappe. Usar lecturas actuales para no aceptar saldos de una instantánea anterior.
3. La suma de aplicaciones activas no supera el importe disponible del recibo ni el saldo aplicable de la factura. Reintentar una clave con los mismos datos devuelve la misma aplicación; con otros datos falla.
4. El saldo del contrato sigue derivándose de los recibos. El saldo fiscal debe incorporar las aplicaciones sin sumar otra vez los pagos de contado ya representados. No parchear `paid_amount` de forma aislada: `validate_payments` y `recalculate_invoice_collection` actualmente lo recalculan y deben participar en el cambio.
5. Un recibo aplicado no puede anularse dejando su aplicación activa. Reversar/asignar con trazabilidad y respetar caja cerrada. Una nota de crédito no prueba devolución de dinero.
6. La caja sigue contando el recibo una sola vez. No invocar `create_invoice_collection` para replicar ese ingreso ni usar `initial_collection` con un abono ya recibido.

Las filas fiscales `payments` describen la forma de pago de la factura y su suma debe cubrir el total según la validación Lite, incluso a crédito. No copiarlas como si fueran prueba de dinero cobrado. Para deuda pendiente, forma/plazo fiscal y condición comercial se deben configurar explícitamente; no inventar efectivo recibido por el saldo.

## Datos y configuración necesarios

- Relación explícita del socio/contrato con el cliente fiscal del mismo negocio. El pagador puede ser una persona distinta del socio. No crear ni actualizar un cliente fiscal usando únicamente nombre o teléfono del socio.
- Servicio Lite activo del negocio, sin control de inventario, relacionado con el plan. No convertir una membresía en un producto con existencias.
- Definir si el precio comercial incluye impuestos y cómo se representa su descuento. GYM actual opera con un total comercial sin desglose fiscal; no asumir tarifa cero, sumar un impuesto sobre el precio acordado ni recalcular contratos históricos al cambiar el catálogo.
- Lite debe recalcular la propuesta y compararla con el importe comercial que se pretende facturar. Ante diferencia, detener y mostrarla antes de reservar numeración o llamar al proveedor. El mapeo debe admitir las reglas de redondeo existentes.
- Ubicación fiscal y terminal autorizadas del mismo negocio, compatibles con la sede operativa. No elegir el primer establecimiento disponible ni tratar una sucursal como establecimiento automáticamente.
- Ambiente desde la configuración tributaria correspondiente. No permitir cambiarlo desde un parámetro arbitrario. Las pruebas usan proveedor simulado, sin llamadas fiscales reales.

Estos son requisitos de configuración y validación del software, no una determinación del tratamiento tributario aplicable a cada gimnasio. La integración no fijará tasas ni momento fiscal por su cuenta.

## Entregas concretas de la etapa 4

### 4.1 Preparación y borrador

Estado: implementada la preparación explícita por contrato, con snapshot, autorización y borrador inmutable. Mapeos predeterminados por plan/socio y facturación parcial/agrupada no se implementaron. Ver [BORRADOR_FISCAL.md](BORRADOR_FISCAL.md).

Agregar una prevalidación GYM que compruebe contrato, permisos, Lite instalado, cliente fiscal, servicio, ubicación y configuración de precio/impuestos. Mostrar los datos faltantes de forma controlada. Preparar un borrador Lite vinculado a una solicitud fiscal auditable e idempotente; sin reservar secuencia, emitir, registrar nuevos pagos ni alterar acceso del socio.

La primera propuesta es facturar el servicio contratado mediante solicitud explícita del operador. No generar automáticamente una factura por abono ni por asistencia. La agrupación, facturación parcial y momento de emisión requieren su regla comercial/fiscal definida antes de habilitarlos; no imponer una factura por contrato como restricción permanente del modelo. Una solicitud no puede repetir importes ya facturados; reemplazos y notas de crédito mantienen historial y relación con la solicitud original.

Archivos previstos: `gym_management/api/invoicing.py`, esquemas GYM para configuración/mapeos y solicitud fiscal, su controlador/permisos, `public/js/membership_forms.js`, tests específicos y hooks de índices/roles si son necesarios. La ubicación exacta de cada configuración se decidirá tras revisar su impacto sobre snapshots históricos.

### 4.2 Aplicación de recibos y saldos

Estado: implementada con autorización por origen, límites, idempotencia, lectura actual, proyección de saldos y reversos. No se crean nuevos cobros ni abonos tradicionales. Ver [APLICACIONES_DE_RECIBOS.md](APLICACIONES_DE_RECIBOS.md) para alcance y caja cerrada.

Implementar el modelo/servicio de aplicaciones en Lite, integrarlo en el cálculo fiscal de saldos y en los controles de anulación. Revisar `api/collections.py`, controlador de factura, `api/receipts.py`, sus permisos, reportes y caja. Cubrir efectivo y transferencias, recibos anteriores/posteriores a la factura y varios abonos, sin duplicar dinero.

### 4.3 Emisión y seguimiento

Estado: emisión/consulta implementadas y verificadas con proveedor simulado; correcciones vinculadas pendientes. Ver [EMISION_FISCAL.md](EMISION_FISCAL.md) para el límite de transacción, condiciones fiscales y alcance.

Con los pasos anteriores validados, emitir mediante Lite y conservar el vínculo incluso ante timeout o respuesta pendiente. Consultar estados mediante su servicio existente. GYM no regenera claves ni reemite automáticamente; los reintentos solo consultan. Los reemplazos y notas de crédito GYM permanecen bloqueados hasta implementar la corrección vinculada. PDF/XML conservan autorización de acceso. Implementar el tratamiento explícito de crédito, anulación y devolución sin borrar historia.

## Validación para cerrar la etapa

- Negocios A/B y sedes distintas: IDs de otro alcance, clientes/servicios/terminales cruzados y archivos fiscales deben denegarse.
- Recepcionista puede cobrar pero no emitir por usar la ruta GYM; operador fiscal necesita también alcance GYM. Revocar asignación o feature tiene efecto inmediato.
- Dos solicitudes simultáneas y reintentos tras error no duplican factura, secuencia, aplicación ni ingreso. La idempotencia debe recuperarse del estado persistido aunque falle la respuesta.
- Precio con y sin impuesto incluido, descuentos, centavos y modificación posterior del plan: total coherente o error previo a emitir; no cambiar el contrato confirmado.
- Pago completo y varios abonos antes/después de emitir: mismo dinero en contrato, aplicaciones y caja. Diferenciar las formas de pago fiscales de la cobranza real.
- Proveedor simulado: autorizado, pendiente, rechazo y timeout. Los pendientes solo consultan y conservan identidad. Un error fiscal no cancela automáticamente el contrato ni borra recibos.
- Cancelación de recibo aplicado, caja cerrada, nota de crédito y reemplazo: saldos y trazabilidad consistentes. Regresión de POS, Restaurante y API externa.

No se requiere instalar `facturada_api` para probar esta integración local ni migrar el piloto para desarrollar el puente.
