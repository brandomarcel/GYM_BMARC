# Emisión fiscal y seguimiento

Implementación de la entrega 4.3 en el sitio aislado `gym_stage2_test.localhost`.
Las pruebas usan un proveedor simulado. No se configuró un certificado real,
no se emitió al SRI y no se migró `gym_bmarc`.

## Flujo disponible

1. Confirmar la membresía y preparar su solicitud fiscal según
   [BORRADOR_FISCAL.md](BORRADOR_FISCAL.md).
2. Aplicar todos los recibos confirmados del contrato a la factura mediante
   [APLICACIONES_DE_RECIBOS.md](APLICACIONES_DE_RECIBOS.md).
3. En `GYM Billing Request`, seleccionar **Emitir factura**. Revisar ambiente y
   total; indicar formas fiscales, importes y plazos en días para el saldo.
   Se admiten varias condiciones; deben sumar exactamente el pendiente. Si ya
   está pagado todo, no se agregan condiciones para saldo futuro.
4. Confirmar. El servidor vuelve a comprobar permisos, feature `billing`,
   configuración del proveedor, cuota, origen y saldos actuales. Lite reserva
   la numeración y calcula/persiste la factura.
5. Después del primer intento, usar **Consultar estado fiscal**. Los reintentos
   de emisión también pasan a consulta de la misma clave, incluso ante rechazo
   o pérdida de respuesta. Los trabajos de seguimiento existentes de Lite
   conservan sus intervalos, límite de revisión y consultas sin reemisión.

El operador necesita permisos fiscales Core y acceso GYM al negocio/sucursal.
Recepción no recibe permisos de emisión. PDF/XML verifican también el alcance
del origen antes de generar archivos o consultar adjuntos.

## Identidad persistente y límite de la transacción

`billing/emission.py` dirige la transacción HTTP de emisión. Antes del POST al
proveedor confirma en base de datos las condiciones, el responsable, el RUC,
la clave, número, fecha y marca del intento. Conserva el lock Redis compartido
con las consultas durante la reserva, ambos commits y el envío.

Ese commit es deliberado: un timeout, una excepción durante la persistencia de
la respuesta o la caída del proceso no deshacen la identidad fiscal. Después
de esa marca solo se consulta. No existe garantía de entrega exactamente una
vez a un servicio remoto: si el proceso cae entre el commit y el POST, la clave
queda reservada y puede requerir revisión humana. Esta versión prioriza evitar
doble emisión; no incluye una ruta para reenviar ni regenerar ese documento.
Un resultado no confirmado se registra con un mensaje general, sin secretos.

No invocar este caso de uso como parte de una transacción de negocio mayor:
es propietario de sus commits. Las rutas genéricas Lite de numeración/envío
no pueden sustituirlo para un origen GYM. La autorización interna usa contexto
Python acotado, nunca flags recibidos por RPC ni una sesión Administrator para
el operador.

## Condiciones fiscales frente a cobranza

Las formas fiscales del dinero recibido se derivan de aplicaciones activas y
recibos mediante lecturas actuales con locks. Las condiciones del saldo las
declara el operador y se validan en servidor. Los plazos positivos se transmiten
por Lite como `plazo` y `unidadTiempo = dias`.

Estas condiciones son un snapshot fiscal y no registran dinero, abonos Lite
tradicionales ni movimientos de caja. El saldo real continúa calculándose con
aplicaciones; un cobro posterior puede completar el saldo sin alterar las
condiciones de la factura enviada. Se conserva la condición interna `Credito`
para administrar ese saldo, incluso si ya fue pagado al emitir.

La clave, número, fecha, importes y condiciones de pago quedan protegidos.
Modificar/inactivar después el cliente o servicio no reescribe el snapshot
de una factura numerada ni impide persistir su respuesta fiscal. El seguimiento
técnico como Administrator puede terminar un documento ya numerado aunque
se deshabilite GYM; esto no habilita nuevas emisiones ni acceso de usuarios.

## Límites y siguiente entrega

- Se factura explícitamente el total de un contrato. Facturación parcial y
  agrupación de contratos requieren reglas y conciliación adicionales.
- La corrección vinculada mediante nota de crédito, reemplazo y devolución
  queda pendiente. Las rutas genéricas no pueden crear una nota de crédito
  desvinculada ni clonar la factura GYM. Una membresía con clave reservada no
  puede cancelarse omitiendo la resolución fiscal.
- Reversar una aplicación no ejecuta una devolución bancaria. Se mantienen las
  restricciones de caja cerrada y la historia de recibos/aplicaciones.
- Certificado/proveedor, ambiente de pruebas real, PDF/XML reales y adopción
  del piloto requieren una validación de integración posterior. Un mock no
  acredita autorización del SRI.

## Validación reproducible

Desde el Bench, exclusivamente sobre un sitio de pruebas preparado:

```bash
bench --site gym_stage2_test.localhost run-tests --module gym_management.tests.test_emission --skip-test-records
bench --site gym_stage2_test.localhost run-tests --app gym_management --skip-test-records
```

La suite fiscal cubre autorización, pago parcial/completo, gerente/recepción,
aislamiento, datos manipulados, pérdida de respuesta, lectura del intento
confirmado desde otra conexión, consulta ante 43/70/rechazo, reintento durante
el POST, snapshot histórico, cobro posterior y seguimiento técnico. Las
regresiones compartidas deben incluir Lite, polling, POS, Restaurante y API.

Resultado de esta entrega: **86 pruebas GYM** (13 de emisión) y **47
regresiones compartidas** aprobadas: 14 de facturación Lite, 16 de seguimiento,
3 de POS y 14 de Restaurante. Se verificó además el guardado del snapshot tras
inactivar cliente/servicio. Ruff, ESLint, Prettier y revisión de sintaxis/JSON
pasaron sobre los archivos afectados.

Chromium validó como gerente la apertura del diálogo, saldo USD 30, catálogo de
formas fiscales y plazo. No se confirmó emisión desde el navegador. Se retiraron
sus cuentas/documentos sintéticos y se detuvo el servidor temporal.

La regresión de API externa queda pendiente: al intentar sus 30 pruebas se
obtuvieron 18 errores por ausencia de los DocTypes de `facturada_api`, que no
está instalada en este sitio. No se declara aprobada ni se instaló como nueva
dependencia de GYM. Repetirla en un sitio aislado preparado con esa app antes
de publicar cambios compartidos hacia instalaciones que la utilicen.
