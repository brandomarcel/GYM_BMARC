# Uso del Desk de GYM

El Workspace **GYM** agrupa operación diaria, seguimiento y administración.
El usuario autorizó esta mejora del Desk el 2026-10-18 para operar y administrar
el piloto con más facilidad. Angular sigue previsto como proyecto independiente;
la lógica y los permisos permanecen en Frappe.

## Recorrido diario

1. Abrir **Inicio del gimnasio** (`/app/gym-home`). Elegir negocio y sucursal.
   Se seleccionan automáticamente solo cuando hay una opción autorizada.
   El resumen muestra contratos vigentes por fecha, vencimientos en 7 días,
   ingresos permitidos hoy y contratos con saldo. Vigencia no garantiza acceso:
   también se comprueban pago mínimo, crédito, deuda y sedes del plan.
2. Como administrador del negocio, abrir **Caja del gimnasio** (`/app/gym-cash`).
   Elegir negocio, sucursal y cajero. Pulsar **Abrir caja**, seleccionar el terminal
   y escribir el fondo inicial en USD, incluso si es cero. Se necesita GYM activo,
   módulo POS habilitado y permiso `restaurant.cash.manage`. El terminal debe
   pertenecer al establecimiento de la sucursal y estar autorizado para el cajero.
   Si no aparece, revisar establecimiento en GYM Branch y terminal/asignaciones
   en FacturADA Core. No activar facturación electrónica para cobrar una membresía.
3. Abrir **Socios** y crear el socio con su código único dentro del negocio.
   Guardar y pulsar **Crear membresía**. Seleccionar el plan y revisar fecha,
   promoción y condiciones. Guardar y confirmar. Los campos de condiciones
   se copian desde el plan y el servidor calcula importes y fechas definitivos.
4. En la membresía confirmada, pulsar **Registrar cobro**. Transferencia y tarjetas
   requieren referencia. Efectivo muestra la caja abierta del usuario que cobra
   y de la sucursal de contratación; no escribir identificadores de caja.
   Si el administrador abrió caja para recepción, debe cobrar la cuenta de recepción.
   Se permiten abonos dentro del saldo, conforme a las condiciones del contrato.
   El aviso de la membresía muestra pagado y pendiente. **Historial de cobros**
   permite consultarlos; anular requiere autorización y motivo.
5. Abrir **Control de acceso**, seleccionar contexto e introducir el código del
   socio. Pulsar Enter o **Registrar ingreso**. Se informa Permitido/Denegado y
   el motivo; el resultado se registra en Asistencias.
6. Al terminar, el administrador vuelve a **Caja**, selecciona al cajero y pulsa
   **Contar y cerrar caja**. Ingresar el efectivo contado, incluyendo el fondo.
   El servidor recalcula los movimientos, confirma el cierre y marca la apertura
   como cerrada. El aviso informa la diferencia y el identificador del cierre.
   La consulta previa es orientativa: movimientos posteriores pueden cambiar
   el total definitivo. Actualizar después de un error antes de volver a actuar.

## Límites y conexiones

- Core controla negocios, usuarios, permisos, licencias y terminales; GYM controla
  socios, sedes, contratos y acceso; Lite registra recibos; Restaurante conserva
  apertura, movimientos y cierre. El adaptador `cash.py` añade alcance GYM y
  delega operaciones al servicio de Restaurante con el usuario autenticado.
- Recepción consulta su propia caja; no puede abrir o cerrar ni consultar otro
  cajero mediante esta pantalla. El administrador puede gestionar cajeros
  habilitados y autorizados para esa sucursal. No se amplían roles técnicos.
- La caja es compartida con otros módulos del negocio. El cierre incluye sus
  movimientos vinculados/contemplados por el motor existente, sin duplicar los
  recibos al facturar. Transferencias/tarjetas registradas sin apertura vinculada
  permanecen en el historial de cobros del contrato y no entran en ese cierre.
- El cobro interno no emite factura electrónica. Las promociones disponibles son
  individuales por porcentaje o importe fijo; 2×1 grupal sigue pendiente.
- **Configuración de GYM** es para administradores técnicos. Dueños y recepción
  conservan sus permisos del negocio sin recibir System Manager.
- No usar el formulario genérico de cierre como sustituto de **Contar y cerrar
  caja**: esa acción aplica las validaciones y cálculos del servicio compartido.

## Verificación

Las pruebas automáticas y los datos sintéticos de navegador se ejecutan únicamente
en `gym_stage2_test.localhost`. Nunca ejecutar la suite sobre `gym_bmarc`.

Pasaron 117 pruebas GYM en el sitio aislado y el recorrido de apertura, cobro,
acceso y cierre en Chromium. Se retiraron después los datos sintéticos del
navegador. El piloto local se respaldó antes de migrar las páginas y formularios.

Se comprobó también en Chromium el piloto `gym_bmarc:10100` con las cuentas
demo de dueño, recepción y administrador técnico: inicio, caja, socio sin guardar,
configuración y Workspace. No se realizaron movimientos en el piloto.
