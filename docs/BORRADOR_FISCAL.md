# Preparación de borrador fiscal — etapa 4.1

La etapa 4.1 añade preparación explícita de un borrador Lite desde una membresía confirmada. No reserva numeración, emite al SRI ni registra ingresos. La etapa 4.2 posterior permite aplicar recibos existentes: ver [APLICACIONES_DE_RECIBOS.md](APLICACIONES_DE_RECIBOS.md). Solo se migró el sitio aislado `gym_stage2_test.localhost`; el piloto `gym_bmarc` sigue sin migrar.

## Arquitectura implementada

```text
Desk / RPC
  → api/invoicing.py                 contrato HTTP y transacción
  → billing/service.py              autorización, idempotencia y caso de uso
  → DraftGateway                    interfaz pequeña: preparar / crear
  → billing/lite.py                 adaptador local y validación del origen fiscal
  → servicios de facturada_lite      cálculo y persistencia de factura
```

El controlador de `GYM Billing Request` reutiliza el caso de uso para que insertar por REST genérica no evite sus reglas. La API no contiene cálculos fiscales ni consultas al proveedor. No se añadió un framework, contenedor de dependencias, nueva app ni conexión HTTP interna.

La responsabilidad de cada pieza es concreta: el servicio coordina la solicitud; el adaptador traduce el contrato a un servicio facturable; Lite recalcula impuestos y total. `PreparedDraft` describe la propuesta y `DraftGateway` permite probar o reemplazar ese adaptador sin mover las reglas del caso de uso. El adaptador conserva las validaciones Core y Lite con el usuario autenticado; no usa contexto Administrator ni añade permisos fiscales a recepción.

Lite incorpora `invoice_source_adapters` como extensión para apps instaladas. Los orígenes sin adaptador conservan su comportamiento. Para GYM, el adaptador valida factura/origen, lectura y listas; bloquea numeración y emisión genéricas antes de sus efectos. La entrega 4.3 añade el flujo autorizado descrito en [EMISION_FISCAL.md](EMISION_FISCAL.md). El helper de listas aplica condiciones SQL provenientes únicamente de código de hooks confiable, con valores escapados por la política GYM; nunca recibe una condición SQL del navegador.

## Flujo de uso

1. Entrar con permiso fiscal `billing.create` y acceso GYM al contrato y su sede. Gerente necesita asignación activa de sede; recepción no puede realizar este paso.
2. Abrir la membresía confirmada y pulsar **Preparar borrador fiscal**.
3. Seleccionar cliente fiscal/pagador, servicio Lite activo sin inventario, terminal autorizado del establecimiento de la sede y si el importe incluye impuestos. El pagador puede ser distinto del socio; no se crea un cliente automáticamente.
4. El servidor toma precio y descuento del contrato, tarifa del servicio y ambiente del perfil tributario activo. El cálculo final lo valida Lite. Si el total difiere del contratado, muestra un error sin cambiar la membresía.
5. Se crean solicitud y borrador dentro de una transacción. La solicitud conserva las condiciones fiscales, autor, fecha y relación con la factura. Después se accede mediante **Solicitud fiscal** / **Ver borrador Lite**.

El esquema usa campos Data para IDs de entidades opcionales de Lite y búsquedas explícitas autorizadas en el diálogo. Esto evita convertir Lite en dependencia obligatoria de instalación de GYM. Sus pertenencias y estados se validan en servidor; un nombre guardado no es autorización.

## Garantías y límites

- Los reintentos con las mismas selecciones recuperan la solicitud existente, incluso con otra clave. Cambiar las selecciones de una solicitud existente produce un conflicto controlado.
- En esta entrega se prepara el importe completo del contrato y se admite una solicitud inmutable por contrato. No hay todavía corrección/anulación de solicitudes, división de importes ni agrupación de varios contratos. Esta es una restricción inicial del caso de uso, no un índice único permanente sobre membresía.
- El precio incluye/no incluye impuestos se elige explícitamente. Como el contrato actual ya tiene un total comercial final, añadir un impuesto que aumente ese total se rechaza. Algunos importes/descuentos pueden no coincidir al centavo después del desglose: se detienen para revisión, sin ajuste silencioso.
- Se requiere un contrato con total positivo. La facturación de contratos gratuitos queda fuera de esta entrega.
- El borrador no contiene pagos. Usa provisionalmente condición fiscal `Credito` para representar el importe todavía sin aplicar a sus recibos; esto no autoriza crédito operativo ni determina la condición de la factura definitiva. La etapa 4.2 ya permite conciliar explícitamente los recibos GYM mediante aplicaciones; no cambia todavía esta condición fiscal provisional.
- Editar el catálogo no modifica las condiciones fiscales guardadas ni el contrato confirmado. Los borradores protegidos no admiten cambios de cliente, ubicación, ambiente, servicio, importes, pagos ni origen.
- La fuente queda protegida también en lectura por ID, listas Desk, listado API de facturas y cuentas por cobrar. Los adjuntos asociados a estas facturas deben ser privados y conservar el alcance de la solicitud. La política de archivos/facturas de otros orígenes no se sustituye.
- No se permite clonar la factura para la misma solicitud ni desvincular su origen para eludir el bloqueo de emisión. Llamar directamente a numeración o al servicio de envío también se rechaza antes de reservar secuencia o contactar al proveedor.
- Las transacciones concurrentes toman socio → contrato → solicitud → factura y recuperan el estado actual. La etapa 4.2 añade un override de `save` que adquiere el origen antes del lock interno de Frappe también al guardar facturas existentes, preservando ese orden y su saldo actual.
- Si falla la creación de factura, el endpoint revierte también la solicitud. Una referencia eliminada o inconsistente exige revisión; no se reconstruye creando una segunda factura automáticamente.

## Validación

En el sitio de pruebas con Core, GYM y Lite instalados:

```bash
bench --site gym_stage2_test.localhost run-tests --app gym_management --skip-test-records
bench --site gym_stage2_test.localhost run-tests --module gym_management.tests.test_invoicing --skip-test-records
bench --site gym_stage2_test.localhost run-tests --module facturada_lite.api.test_invoice_api --skip-test-records
bench --site gym_stage2_test.localhost run-tests --module facturada_lite.api.test_pos_sale --skip-test-records
bench --site gym_stage2_test.localhost run-tests --module facturada_restaurante.api.test_frontend --skip-test-records
```

La suite fiscal usa proveedor simulado y MariaDB real, incluidas dos conexiones con instantáneas previas a la primera solicitud. Cubrir aislamiento de negocio/sede, roles, búsquedas, archivos, importes, reintentos, rollback y bloqueo previo a numeración/envío. Las pruebas de concurrencia confirman solo sus fixtures sintéticas y las limpian al finalizar. No ejecutarlas simultáneamente en el mismo sitio ni sobre clientes reales.

Resultados verificados: 86 pruebas distintas aprobadas en el alcance comprobado:

| Área | Pruebas |
| --- | ---: |
| Base GYM: aislamiento, membresías y cobros | 37 |
| Preparación fiscal GYM, incluyendo listas y paginación | 18 |
| API de facturación Lite | 14 |
| POS Lite | 3 |
| Restaurante y caja | 14 |

La suite completa GYM pasó con 54 casos antes de añadir el último escenario de listas mixtas; después se repitieron los 18 casos fiscales y las regresiones Lite/POS/Restaurante. Ruff, sintaxis Python/JSON/JavaScript y revisión de diff se comprobaron en los archivos del alcance.

Chromium validó como Gerente el flujo membresía → selección fiscal → borrador USD 30 → solicitud, recarga y recuperación del mismo vínculo, sin errores HTTP o JavaScript. Sus negocios y cuentas sintéticos se retiraron, las credenciales temporales se eliminaron y se detuvo el servidor temporal.

La etapa 4.2 ya añade aplicaciones y reversos según [APLICACIONES_DE_RECIBOS.md](APLICACIONES_DE_RECIBOS.md). La etapa 4.3 añade emisión/seguimiento según [EMISION_FISCAL.md](EMISION_FISCAL.md); las correcciones fiscales vinculadas siguen pendientes.
