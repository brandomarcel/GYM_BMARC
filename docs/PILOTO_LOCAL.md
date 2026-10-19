# Piloto local de GYM preparado

Estado al 2026-10-17. El usuario autorizó preparar un gimnasio de prueba antes de
crear Angular. No se creó un frontend Angular.

## Acceso

- Sitio: `gym_bmarc`.
- Configuración técnica: `http://192.168.100.195:10100/app/gym-setup`.
- Workspace: `http://192.168.100.195:10100/app/gym`.
- Control administrativo de acceso: `/app/gym-access`.

| Cuenta local | Uso |
| --- | --- |
| `admin.gym@example.invalid` | Soporte/creador de negocios, con System Manager. |
| `dueno.gym@example.invalid` | Administrador del negocio, sin System Manager. |
| `recepcion.gym@example.invalid` | Recepción, asignada a Principal, sin System Manager. |

Las cuentas usan la contraseña local solicitada por el usuario. No está escrita
en el código ni en archivos de configuración del proyecto. No se cambió la
contraseña del Administrator existente. Los correos `.invalid` son de prueba;
no se enviaron correos de bienvenida ni mensajes externos.

## Configuración persistida

- Negocio **Gimnasio Prueba**, marcado como demostración (`is_demo`), con
  identificador sintético `9999999999999`; no representa un RUC fiscal real.
- Sucursal **Principal**, código `PRINCIPAL`.
- Suscripción **GYM-DEMO**, activa por tiempo durante 365 días desde el alta,
  máximo 5 usuarios. GYM habilitado; POS habilitado para la caja compartida.
- Facturación electrónica, restaurante, cocina, API externa e inventario no
  habilitados como módulos comerciales de esta suscripción.
- Planes de ejemplo por **USD 30 / 1 mes**, una sede y renovación Desde regreso:
  **Mensual completo**, **Mensual con abonos** (mínimo 50 %) y **Mensual a crédito**
  (requiere aprobación en el contrato). Son ejemplos editables del catálogo.
- Establecimiento/punto `001/001` y terminal **Recepción Principal demo**,
  asociados a la sucursal y a las tres cuentas para preparar la caja.
- Español, Ecuador, USD y America/Guayaquil conservados.

Apps instaladas: Frappe, GYM, FacturADA Core, Lite y Restaurante. Lite proporciona
los recibos y Restaurante la caja compartida; no se crearon mesas ni se activó
el módulo de restaurante para el negocio. No se instaló ERPNext ni API externa.

No hay socios, contratos, recibos ni facturas de demostración persistidos por
esta preparación. Las pantallas operativas comienzan vacías y los contadores
se mostraron en cero. Tampoco se creó perfil tributario, certificado ni secuencia
fiscal; no hay emisión al SRI configurada.

Para cobrar efectivo se debe abrir una caja por usuario/turno usando el terminal
preparado. El administrador autorizado puede gestionar la apertura; recepción
no adquiere permisos de gestión de caja por tener permisos para cobrar. No se
abrió un turno automáticamente ni se registraron movimientos de dinero.

## Respaldo y migración

Se verificaron vacíos los DocTypes heredados del módulo GYM antes del cambio.
Se creó un respaldo previo con base de datos, configuración y archivos en:

`sites/gym_bmarc/private/backups/20261017_185933-gym_bmarc-*`

La carpeta es privada del Bench y no debe versionarse. Se instalaron Core,
Lite y Restaurante, y se sincronizaron los modelos/hook de GYM en este sitio
local. No se borraron modelos heredados, no hubo datos históricos que mapear
ni se ejecutó una migración sobre otros sitios.

## Validación realizada

Chromium se conectó al servidor existente del puerto **10100** y comprobó:

1. Login de las tres cuentas y lectura del contexto del negocio demo.
2. Checklist completo y página `gym-setup` funcional para soporte técnico.
3. Respuesta 403 al checklist para dueño y recepción, con el panel operativo
   disponible para ambos. No se ampliaron sus roles técnicos.
4. Panel con cero contratos y sin crear cobros o documentos fiscales.

La revisión final confirmó que CSRF permanece habilitado y que dueño/recepción
no tienen System Manager. No se ejecutó `run-tests` en el piloto; las 97 pruebas
GYM previas pertenecen al sitio aislado `gym_stage2_test.localhost`.

## Lo siguiente

Usar Frappe para revisar/editar esta configuración y dar de alta los primeros
socios cuando corresponda. Angular se creará después como proyecto independiente,
consumiendo las APIs y permisos del servidor. Sus pruebas de sesión, CSRF, proxy
y cambio de negocio se realizarán con ese frontend; no requieren abrir CORS ni
introducir claves API de administrador en el cliente.

Este piloto sirve para desarrollo local y primera conexión de Angular. No
acredita preparación de producción, emisión fiscal real, automatización SaaS,
restauración ensayada ni extracción a un sitio exclusivo.

## Promoción individual habilitada posteriormente

Se respaldó nuevamente el sitio y se migró el modelo `GYM Promotion`.
La campaña **DEMO 10% mensual** aplica únicamente al plan `MENSUAL-COMPLETO`,
durante 30 días desde el alta: USD 30 de precio habitual, USD 3 de descuento,
USD 27 de total por persona. Se administra en `/app/gym-promotion` y se elige
al contratar; no se aplica automáticamente a todos los socios.

Ver [PROMOCIONES.md](PROMOCIONES.md). No es un 2×1 grupal. La entrega se validó
con 111 pruebas en el sitio aislado y revisión de formulario en Chromium.
No se ejecutaron pruebas automáticas ni se crearon operaciones en este piloto.

## Mejora de Desk del 2026-10-18

Piloto respaldado con archivos (`20261018_222650-gym_bmarc-*`) y migrado para
incorporar Inicio y Caja del gimnasio, Workspace organizado y formularios guiados.
Ver [USO_DEL_DESK.md](USO_DEL_DESK.md). Revisión Chromium con las tres cuentas
demo sin guardar operaciones. Antes y después: 1 socio, 2 membresías, 1 recibo,
0 facturas, 1 apertura y 0 cierres. La caja abierta existente se conserva.
