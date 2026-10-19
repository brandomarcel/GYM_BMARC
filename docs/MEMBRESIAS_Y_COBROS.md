# Membresías, cobros y acceso — etapa 3

Implementación validada en `gym_stage2_test.localhost` el 2026-10-17. El piloto `gym_bmarc` y producción no se migraron. Esta etapa añade membresías por tiempo; las clases, reservas y paquetes de sesiones siguen pendientes.

## Modelo y reglas

- `GYM Membership Plan`: catálogo por negocio, duración en días/meses, precio USD, acceso a una sede, varias sedes seleccionadas o todas las del negocio. Solo administración/gerencia puede editarlo.
- `GYM Membership`: contrato confirmado mediante Submit. Copia las condiciones del plan al confirmar; cambiar el catálogo después no cambia contratos confirmados. No permite períodos confirmados superpuestos para el mismo socio. La sede de contratación gobierna la administración del contrato.
- Renovación `Continua`: empieza al día siguiente del vencimiento anterior, incluso si el socio vuelve después; las fechas retroactivas requieren permiso de gerencia/administración. `Desde regreso` y `Fecha elegida` permiten elegir la nueva fecha; la interfaz propone hoy o el día siguiente al vencimiento si el contrato sigue vigente.
- El último día es inclusivo: inicio + duración − un día. Los meses usan aritmética calendario con ajuste de día al mes de destino; 31 de enero + un mes − un día termina el 27 de febrero en un año no bisiesto.
- Descuentos requieren permiso y motivo. Solo crédito aprobado expresamente por administración/gerencia permite deuda sin pago inicial. No se aceptan totales, saldos ni aprobaciones calculados por el cliente.
- `GYM Attendance`: registro inmutable del intento de ingreso, con resultado, razón, actor y fecha del servidor. No es un contador editable ni modifica la membresía.

## Derecho de acceso

El servidor comprueba negocio y licencia activos, asignación del operador a la sede, socio activo, contrato confirmado vigente y sede incluida. Luego aplica la condición de pago:

| Condición | Requisito |
| --- | --- |
| Completo | Total recibido igual al total del contrato. |
| Abonos | Porcentaje mínimo recibido; un contrato con saldo positivo exige al menos un centavo. |
| Credito | Aprobación explícita con motivo y actor. |
| Gratuito | Total cero, sujeto a las demás reglas. |

Si queda saldo después de la fecha límite más los días de gracia, se deniega el acceso. La fecha límite por defecto es el inicio: configurarla al contratar si se desea un plazo mayor, sin superar el fin del contrato. Los cálculos monetarios redondean a centavos.

La búsqueda exacta de código en `/app/gym-access` devuelve solo identidad mínima dentro del negocio autorizado. Permite atender un socio multisede sin conceder lectura general de su perfil de otra sede. Cada intento genera asistencia, permitido o denegado. Los reintentos conservan una clave y devuelven el mismo registro.

## Cobros compartidos con Lite

`FacturADA Payment Receipt`, en Lite, registra dinero ya recibido contra una fuente autorizada. La fuente GYM valida negocio, permiso, contrato y sede en cada operación. GYM no mantiene otro libro de pagos. No procesa tarjetas ni hace cargos bancarios.

- Transferencia y tarjetas requieren referencia. Se pueden registrar sin instalar Restaurante.
- Efectivo requiere la caja existente de Restaurante abierta por el operador, terminal autorizada y establecimiento asociado a la sede. No crea una caja paralela ni concede a recepción permisos fiscales o de apertura/cierre. Su configuración requiere las features/permisos POS correspondientes.
- El cierre incluye los recibos confirmados una sola vez y comparte bloqueo con su registro/anulación. No se permite anular efectivo de una caja cerrada.
- Cada cobro tiene clave de reintento por negocio y huella de sus datos; repetir la misma solicitud devuelve el recibo, cambiar los datos con la misma clave falla.
- Los bloqueos de socio → contrato y lecturas actuales impiden sobrecobros en transacciones simultáneas. Solo cuentan recibos confirmados.
- Los recibos confirmados son inmutables; anular requiere permiso de gerencia/administración y motivo. La anulación administrativa no ejecuta una devolución bancaria.
- No se puede cancelar un contrato mientras tenga cobros confirmados. No se borran contratos confirmados, asistencias ni recibos.
- Los archivos de estos modelos y tablas hijas conservan el alcance del documento padre y son privados.

Un recibo interno **no es una factura SRI**. La etapa fiscal debe relacionar estos cobros con la factura sin crear otro ingreso, perder su identidad o contar dos veces en caja.

## Interfaz y permisos

El Workspace GYM enlaza planes, contratos, control de acceso, asistencias y `GYM Membership Overview`. El formulario confirmado ofrece cobros, historial y saldo; crédito y anulaciones aparecen según permisos. Renovar conserva socio, sede, plan y contrato anterior.

Recepción puede contratar, registrar cobros y asistencia en sus sedes. No administra planes, descuentos, crédito ni anulaciones. Gerencia puede realizar esas operaciones y consultar el reporte de contratos, cobrado y pendiente dentro de su alcance de sedes. Administrador conserva el alcance completo de su negocio. Los roles técnicos `GYM User` y `FacturADA Payments User` solo habilitan Desk: cada operación vuelve a comprobar permisos Core y alcance.

## Reproducción

En un sitio de pruebas identificado, instalar Core y GYM. Instalar Lite para cobros; Restaurante es opcional, necesario para el escenario de caja en efectivo. Sincronizar las apps y sus metadatos con `bench --site <sitio_test> migrate`. Nunca ejecutar estas pruebas sobre datos reales.

```bash
bench --site gym_stage2_test.localhost run-tests --module gym_management.tests.test_business_isolation --skip-test-records
bench --site gym_stage2_test.localhost run-tests --module gym_management.tests.test_memberships --skip-test-records
bench --site gym_stage2_test.localhost run-tests --module gym_management.tests.test_membership_payments --skip-test-records
bench --site gym_stage2_test.localhost run-tests --module facturada_core.api.test_gym_permissions --skip-test-records
bench --site gym_stage2_test.localhost run-tests --module facturada_restaurante.api.test_frontend --skip-test-records
```

Las pruebas de concurrencia confirman fixtures sintéticas para compartirlas entre conexiones y las retiran mediante limpieza explícita. No ejecutar simultáneamente suites sobre este mismo sitio. Los escenarios de efectivo requieren Restaurante instalado; el caso sin Lite deniega pagos y acceso con deuda sin inventar saldos.

Resultados: 67 pruebas aprobadas: 13 de aislamiento, 11 de membresías, 13 de cobros, 14 de Restaurante y 16 de Core (permisos, usuarios y suscripciones). Incluyen fechas, políticas, aislamiento, permisos, saldos, caja, reporte y transacciones concurrentes. Se mantiene pendiente la emisión electrónica, automatización SaaS, migración histórica y adopción del piloto.

Chromium validó alta y confirmación de contrato, abono de USD 15 sobre USD 30, saldo, ingreso permitido y preparación de renovación con sus vínculos conservados, sin errores HTTP ni excepciones JavaScript. Se corrigieron títulos de formulario inválidos y validaciones visuales de Links que bloqueaban recepción. Los negocios, cuentas y documentos sintéticos de navegador se retiraron; sus credenciales temporales se eliminaron. El servidor web temporal fue detenido al finalizar.
