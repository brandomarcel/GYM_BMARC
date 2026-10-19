# Aplicaciones de recibos y conciliación — etapa 4.2

Implementación en GYM y FacturADA Lite, validada en el sitio aislado `gym_stage2_test.localhost`. No se migró `gym_bmarc` ni producción. La emisión/consulta se añadió después en [EMISION_FISCAL.md](EMISION_FISCAL.md); las aplicaciones siguen siendo el único registro de asignación del dinero recibido.

## Qué resuelve

Una membresía de USD 30 puede tener un recibo de USD 15. Aplicarlo a su borrador fiscal deja USD 15 aplicados y USD 15 pendientes, sin crear otro recibo, abono tradicional ni movimiento de caja. Después puede registrarse otro recibo por USD 15 y aplicarlo para completar el saldo.

El saldo operativo de la membresía depende de los recibos confirmados. El saldo de su factura depende de las aplicaciones confirmadas. Reversar una aplicación libera su importe para asignarlo de nuevo y modifica el saldo fiscal; no devuelve dinero ni cambia el derecho de acceso del socio. Anular el recibo es una operación distinta y requiere resolver antes sus aplicaciones.

## Arquitectura

| Pieza | Responsabilidad |
| --- | --- |
| Lite `api/receipt_applications.py` | Transporte autenticado, payload permitido, savepoints y contexto de interfaz. |
| Lite `payments/applications.py` | Caso de uso, límites, idempotencia, bloqueos, reversos, permisos y proyección de saldos. |
| `FacturADA Receipt Application` | Registro auditable entre recibo, factura, negocio e importe, con autor/fecha y motivo/actor del reverso. Solo documentos confirmados afectan saldos. |
| GYM `BillingRequestInvoiceSource` | Autoriza negocio/sede/contrato, declara soporte de aplicaciones y valida que recibo y factura tengan el mismo origen operativo. Lite no importa GYM. |
| Lite `collections.py` y controlador de factura | Reutilizan la proyección de aplicaciones para estas facturas, sin sustituir el flujo de cobros de otros orígenes. |
| GYM `receipt_application_forms.js` | Diálogo para aplicar recibos existentes, indicadores de saldo e historial/reverso. |

Se reutiliza el registro de fuentes de factura `invoice_source_adapters`. Un origen debe declarar explícitamente `receipt_applications = True` y proveer autorización, bloqueo de su obligación y selección de recibos. Una factura ordinaria no acepta aplicaciones por el mero hecho de recibir su ID.

No se añadió otra caja, motor fiscal, dependencia externa ni conexión por API keys. El rol técnico `FacturADA Payments User` habilita el acceso base al DocType; el servidor vuelve a comprobar la autorización de la fuente en cada operación.

## Uso

1. Registrar el dinero realmente recibido desde la membresía. Preparar su borrador fiscal si aún no existe.
2. Abrir **Solicitud fiscal**. El formulario muestra lo aplicado y lo pendiente.
3. Con permisos de administración/gerencia y sede, pulsar **Aplicar recibo**, seleccionar uno disponible y confirmar el importe. No se registra otro cobro.
4. Aplicar recibos posteriores de la misma manera. La asignación es explícita, no automática.
5. Si hubo una asignación incorrecta, abrir **Historial de aplicaciones → Reversar aplicación** e indicar el motivo. El historial se conserva. La misma clave de una aplicación reversada no la confirma otra vez; una nueva asignación requiere una nueva clave.

Recepción continúa registrando cobros y asistencias; no aplica ni reversa importes fiscales. Aplicar exige `billing.manage` además de permisos GYM y alcance de sede. Reversar exige también `gym.payments.cancel`. Administrador técnico conserva su acceso de soporte; no es un rol operativo de empleados.

## Integridad, saldos y caja

- Cada aplicación pertenece a un negocio, factura y recibo compatibles, con moneda USD. En GYM ambos deben corresponder a la misma membresía y solicitud fiscal. No se pueden mezclar contratos ni negocios, incluso con un usuario autorizado en ambos.
- Se exige recibo confirmado, importe positivo a centavos y factura apta a crédito. La suma activa no supera el dinero disponible del recibo ni el total disponible de la factura. Los límites se comprueban en inserción y confirmación, también por REST genérica.
- La clave de reintento es única por negocio. La huella incluye factura, recibo e importe. Repetir datos devuelve la aplicación existente; usar la clave con otros datos falla. Los fallos del endpoint revierten también las inserciones y cambios de saldo de esa solicitud.
- Los registros son inmutables y no se borran. Reversar conserva importe/origen, registra motivo, usuario y fecha, y actualiza el saldo sin ejecutar una devolución bancaria. Repetir el mismo reverso no vuelve a afectar saldos.
- `paid_amount`, `total_collected`, `outstanding_amount`, estado y fecha del último cobro se proyectan desde aplicaciones activas de recibos confirmados. La fecha del dinero se toma del recibo; la fecha de aplicación se conserva por separado.
- Guardar o recalcular una factura GYM vuelve a derivar esos saldos; no permite inyectarlos desde el cliente. Los otros orígenes mantienen su cálculo de cobranza tradicional.
- Los endpoints y el controlador de `FacturADA Lite Invoice Collection` rechazan un segundo abono tradicional sobre estas facturas. No se copian los recibos a esa tabla ni a la tabla fiscal de formas de pago.
- La caja sigue sumando el recibo original una sola vez. Aplicar un recibo de una caja ya cerrada está permitido: solo asigna su dinero histórico y no modifica el cierre. Reversar una aplicación vinculada a una caja cerrada se rechaza en esta versión. Anular el recibo también respeta el control previo de caja abierta y usuario de caja.
- Un recibo con aplicaciones activas no puede anularse. Primero deben reversarse, si las condiciones de caja lo permiten. Las aplicaciones en borrador no consumen dinero; un recibo anulado no se puede confirmar como aplicación después.
- El orden de bloqueo es obligación operativa (socio → contrato → solicitud), factura, recibo, aplicación y caja cuando corresponde. Guardar factura/recibo adquiere el origen antes del lock interno de Frappe. Los totales críticos usan lecturas actuales; guardar una factura con una instantánea previa no borra aplicaciones recién confirmadas.
- Listas, lectura por ID, archivos privados y compartición conservan los controles de origen. No se permite publicar o compartir adjuntos para ampliar permisos.

## Alcance pendiente

La factura sigue siendo un borrador sin pagos fiscales ni identidad SRI. `Credito` es su condición provisional para administrar el saldo mediante aplicaciones, no una aprobación de crédito operativo ni la condición fiscal definitiva. La etapa 4.3 definirá las formas/plazos fiscales y la emisión con estado, reintentos, notas de crédito y reemplazos, manteniendo un único ingreso de dinero.

En esta versión una solicitud fiscal cubre el contrato completo y el recibo se aplica solo a su propio contrato. No se implementan distribución entre contratos, facturas agrupadas, edición de solicitudes ni devolución bancaria. El modelo compartido conserva importes e identidad para ampliar esas políticas explícitamente más adelante.

## Pruebas

```bash
bench --site gym_stage2_test.localhost run-tests --app gym_management --skip-test-records
bench --site gym_stage2_test.localhost run-tests --module gym_management.tests.test_receipt_applications --skip-test-records
bench --site gym_stage2_test.localhost run-tests --module facturada_lite.api.test_invoice_api --skip-test-records
bench --site gym_stage2_test.localhost run-tests --module facturada_lite.api.test_pos_sale --skip-test-records
bench --site gym_stage2_test.localhost run-tests --module facturada_restaurante.api.test_frontend --skip-test-records
```

Pruebas de integración con MariaDB real y datos sintéticos; ninguna emite al proveedor. Las pruebas concurrentes confirman sus fixtures para usar dos conexiones y las limpian al finalizar. No ejecutar suites simultáneas en el mismo sitio ni sobre datos de clientes.

### Resultados verificados

| Área | Pruebas aprobadas |
| --- | ---: |
| GYM: aislamiento, membresías, recibos y borradores | 55 |
| Aplicaciones de recibos y reversos | 18 |
| API de facturación Lite | 14 |
| POS Lite | 3 |
| Restaurante y caja | 14 |

Se ejecutó la suite completa GYM con 71 casos antes de añadir los dos escenarios finales de concurrencia; después se ejecutaron los 18 casos de aplicaciones y las regresiones Lite/POS/Restaurante. Los escenarios adicionales verifican guardar la factura mientras se aplica el recibo y anular el recibo mientras se intenta aplicar: se conserva el saldo y no se permiten resultados incompatibles.

Chromium comprobó como Gerente la selección de un recibo, aplicación de USD 15 a una factura de USD 30, saldo pendiente de USD 15 y reverso con motivo. El reverso devuelve USD 15 al disponible del mismo recibo y deja USD 30 pendientes en la factura, sin otro cobro. La prueba terminó sin errores HTTP ni excepciones JavaScript. Se retiraron sus negocios/cuentas/documentos sintéticos y credenciales temporales y se detuvo el servidor de pruebas.

Ruff, ESLint, Prettier, sintaxis Python/JSON/JavaScript y revisión de diff se comprobaron en el alcance modificado. No se ejecutaron migraciones del piloto ni llamadas fiscales reales.
