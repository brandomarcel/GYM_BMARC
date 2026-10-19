# Hoja de ruta de GYM

Fecha: 2026-10-17.

Estado: etapas 1 y 2 documentadas y base operativa de etapa 3 implementada y validada en sitio aislado. Ver [BASE_MULTIEMPRESA.md](BASE_MULTIEMPRESA.md) y [MEMBRESIAS_Y_COBROS.md](MEMBRESIAS_Y_COBROS.md). Etapa 4.1 con preparación de borrador implementada; ver [BORRADOR_FISCAL.md](BORRADOR_FISCAL.md). Aplicaciones de recibos implementadas en etapa 4.2: ver [APLICACIONES_DE_RECIBOS.md](APLICACIONES_DE_RECIBOS.md). Emisión y seguimiento de etapa 4.3 implementados con proveedor simulado según [EMISION_FISCAL.md](EMISION_FISCAL.md); correcciones fiscales y devolución vinculada pendientes. Este documento no autoriza despliegues o migraciones de producción.

## 1. Decisiones acordadas

- Producto SaaS: varios gimnasios independientes pueden compartir un sitio Frappe.
- Cada cliente se representa mediante un negocio de FacturADA Core (`business`).
- Un negocio puede tener varias sucursales; una sucursal pertenece a un solo negocio.
- Los socios pertenecen al negocio. La membresía define las sucursales donde pueden acceder.
- Core conserva negocios, usuarios, permisos, licencias y configuración tributaria. GYM conserva la operación del gimnasio. Lite conserva facturación electrónica y su ciclo fiscal.
- Una suscripción al software es distinta de una membresía de un socio. No reutilizar sus estados, cobros ni planes como si fueran el mismo contrato.
- Mantener un código común y módulos configurables. No crear copias por gimnasio ni condiciones por nombre de cliente.
- Preparar la extracción de un negocio hacia un sitio exclusivo. Esa extracción requiere migración, pruebas y corte de operaciones; no es un cambio automático de dominio.
- Frontend operativo: proyecto Angular independiente de Facturada. Frappe conserva lógica, APIs y administración/configuración del creador de negocios; no se sustituye la configuración administrativa por la interfaz diaria de recepción.
- Español, Ecuador, USD y America/Guayaquil son la configuración inicial del piloto. Los ajustes regionales globales son compartidos dentro de un sitio.

## 2. Responsabilidades y límites

| Área | Responsable | Regla |
| --- | --- | --- |
| Negocio y autorización | Core | Reutilizar resolución de negocio, asignaciones y permisos; revisar ampliaciones para GYM. |
| Licencia y módulos contratados | Core | Ya existe la feature `gym`; comprobar su aplicación efectiva en las nuevas operaciones. |
| Sedes y operación del gimnasio | GYM, con enlaces a Core | Revisar primero si hay entidades reutilizables para ubicación; no crear modelos paralelos sin necesidad. |
| Socios y membresías | GYM | Separar identidad de socio, vigencia, derechos de acceso y cobros. |
| Cobros y caja | Recibos compartidos Lite y caja existente de Restaurante | Aplicaciones y reversos implementados en etapa 4.2; no duplicar ingresos al facturar. |
| Facturas y notas de crédito | Lite | Delegar cálculos fiscales, numeración, emisión, consulta y documentos. |
| Administración comercial del SaaS | Componentes existentes a revisar | Platform es transicional; no asumir que sus altas y sincronizaciones están listas para producción. |

No instalar ERPNext únicamente para facturar. La app actual define `Company` y `Customer`, nombres que coinciden con ERPNext; resolver su propiedad y compatibilidad antes de cualquier convivencia.

## 3. Etapas y criterios de cierre

### Etapa 1 — Inventario, diseño y migración

Estado: inventario y diseño base realizados el 2026-10-17 en [DISENO_BASE_Y_MIGRACION.md](DISENO_BASE_Y_MIGRACION.md). En ese inventario inicial, `gym_bmarc` estaba vacío y solo tenía Frappe/GYM. Posteriormente se respaldó y preparó como piloto local de demostración: ver [PILOTO_LOCAL.md](PILOTO_LOCAL.md). Se definieron políticas configurables para los escenarios solicitados. Queda una revisión específica de cobros/caja compartidos antes de implementar la etapa 3.

1. Verificar datos, apps y servicios de `gym_bmarc` antes de usarlo como piloto. Usar un sitio de pruebas identificado para pruebas automáticas y evitar sitios de producción.
2. Inventariar DocTypes, API, JS, reportes, archivos y tablas hijas que dependen de `Company`, `company`, `company_id`, `Customer` y planes existentes.
3. Revisar instalación y compatibilidad de Core/Lite. Definir mapeo de compañías actuales a `FacturADA Business` y decidir cómo relacionar socios con clientes fiscales sin duplicar identidades innecesariamente.
4. Definir el modelo mínimo de sucursal, acceso del personal y relación con establecimientos/puntos de emisión. No asumir que una sucursal operativa equivale siempre a un establecimiento fiscal.
5. Definir membresía mínima: inicio y fin, renovación, pagos parciales/deuda, acceso a una o varias sedes y comportamiento ante vencimiento. Las reglas comerciales no acordadas quedan pendientes de consulta.
6. Revisar qué caja y registro de cobros se pueden reutilizar sin acoplar GYM al flujo de órdenes de restaurante.
7. Diseñar migración gradual, respaldo y recuperación: detectar registros ambiguos, conservar relaciones e identificadores y no eliminar esquemas históricos antes de verificar equivalencia.

Cierre: documento con modelos y campos concretos, reglas pendientes resueltas para el alcance inicial, dependencias, archivos afectados, mapeo de datos y validaciones de migración. No ejecutar cambios destructivos para descubrir el modelo.

### Etapa 2 — Negocios, sucursales y seguridad

Estado: base implementada y validada el 2026-10-17 en `gym_stage2_test.localhost`. Ver [BASE_MULTIEMPRESA.md](BASE_MULTIEMPRESA.md). Pasaron 13 pruebas GYM, 16 pruebas relacionadas de Core, comprobaciones HTTP y el flujo de socios en Chromium. Se agregaron sucursales, asignaciones, socios y permisos Core; no se modificaron los esquemas del piloto. La migración histórica de datos sigue pendiente de una adopción explícita.

- Integrar contexto de negocio y feature `gym` mediante Core. Extender permisos de GYM en los puntos canónicos cuando corresponda.
- Asociar sucursales al negocio y definir asignaciones explícitas del personal. No usar `System Manager` como rol rutinario de recepcionista o dueño de gimnasio.
- Validar negocio y sucursal en creación, lectura, actualización, cancelación, eliminación, reportes, archivos privados, API y tareas en segundo plano.
- Comprobar que todo enlace a socio, plan o sucursal pertenezca al negocio autorizado; un filtro en el frontend no es autorización.
- Migrar datos según el plan, con operaciones repetibles y detección de inconsistencias. Preservar contratos existentes o documentar su transición.

Cierre: pruebas con negocios A y B, varias sedes, personal restringido, administrador del negocio y usuario sin asignación. A no puede leer ni modificar datos o archivos de B, incluso proporcionando IDs directamente. Un usuario con acceso explícito a ambos puede cambiar de contexto correctamente.

### Etapa 3 — Flujo operativo mínimo

Estado: implementada la primera versión por tiempo y validada en sitio aislado. Ver [MEMBRESIAS_Y_COBROS.md](MEMBRESIAS_Y_COBROS.md). Incluye planes, contratos, políticas configurables, recibos internos compartidos con Lite, caja existente para efectivo, asistencia y reporte de saldos. El panel y el historial paginado de asistencias se exponen por API para Angular según [API_OPERATIVA.md](API_OPERATIVA.md). La configuración administrativa usa `gym-setup` según [CONFIGURACION_RAPIDA.md](CONFIGURACION_RAPIDA.md). Entrega operativa validada con 97 pruebas GYM y revisión de la configuración en Chromium, únicamente en sitio aislado. El piloto local ya fue preparado con configuración demo y acceso comprobado en el puerto 10100 según [PILOTO_LOCAL.md](PILOTO_LOCAL.md). El frontend Angular y la adopción de datos reales siguen pendientes.

- Completar alta de socios, catálogo de membresías por tiempo, contratación, cobro, renovación y vencimiento.
- Aplicar alcance por sede o multisede y registrar asistencias con negocio, socio, sucursal, fecha y responsable.
- Separar estado de la membresía, estado del pago y derecho de acceso; validar importes, descuentos y fechas en el servidor.
- Conservar condiciones de la contratación para que editar el catálogo no altere el historial.
- Agregar reportes de vigencias, cobros y asistencias por sucursal y consolidados con permisos.

Cierre: alta → contratación → cobro → asistencia → vencimiento/renovación funciona de extremo a extremo; probar acceso permitido/denegado, errores de pago y reintentos sin cobros duplicados. No convertir recibos internos en comprobantes fiscales.

### Ampliación operativa — Promociones

Requisito incorporado: promociones como 2×1, separadas del catálogo de planes. Descuentos individuales por porcentaje/importe fijo implementados según [PROMOCIONES.md](PROMOCIONES.md), con campaña, cotización y snapshot del contrato. Validación: 111 pruebas GYM y formulario de recepción revisado en Chromium; piloto local respaldado/migrado con campaña demo del 10 % sobre el plan mensual completo. Tiempo adicional y promociones grupales siguen pendientes. Distinguir descuentos, tiempo adicional y beneficios para varios socios. Las promociones grupales necesitan contratación vinculada, reparto explícito de importes/acceso y cobro único sin duplicar ingresos. Definir las condiciones comerciales antes de modificar el modelo; el descuento manual actual no representa este flujo. La configuración y lógica vivirán en Frappe y serán consumidas posteriormente por Angular.

Nota para el 2×1 grupal pendiente: el usuario indicó que cada gimnasio decidirá su reparto. La campaña deberá permitir reparto igual o titular con beneficiario bonificado, y una condición explícita de activación. No establecer una regla global ni presentar esas opciones como implementadas todavía; ver [PROMOCIONES.md](PROMOCIONES.md).

### Etapa 4 — Facturación con Lite

Estado: etapa 4.1 implementada y validada en sitio aislado; ver [BORRADOR_FISCAL.md](BORRADOR_FISCAL.md). Se crea una solicitud/borrador inmutable e idempotente, sin emitir ni duplicar cobros. Etapa 4.2 implementada con aplicaciones explícitas, saldos y reversos: ver [APLICACIONES_DE_RECIBOS.md](APLICACIONES_DE_RECIBOS.md). Etapa 4.3 con emisión y seguimiento implementados: 86 pruebas GYM y 47 regresiones compartidas aprobadas, formulario revisado en Chromium. Regresión externa pendiente por app API no instalada; ver [EMISION_FISCAL.md](EMISION_FISCAL.md). Corrección mediante nota de crédito/reemplazo y devolución vinculada pendientes; no cerrar todavía toda la etapa 4. Se eligió integración local con servicios Lite, manteniendo permisos del operador. Ver [INTEGRACION_FISCAL.md](INTEGRACION_FISCAL.md) para evidencia, aplicaciones de recibos y entregas 4.1–4.3. `facturada_api` se reserva para integraciones entre sistemas/sitios.

- Definir cuándo se solicita factura y qué operación origina el documento; soportar reintentos sin duplicados.
- Mapear negocio, cliente fiscal, servicios/productos, pagos, establecimiento, punto de emisión y ambiente hacia Lite.
- Preservar relación entre contratación/cobro y documentos fiscales. Revisar el modelo si existen varios cobros o conceptos por factura; no imponer cardinalidad sin definir el caso.
- Delegar el ciclo fiscal a Lite. Los estados pendientes conservan identidad; una consulta de estado nunca debe convertirse en reemisión.
- Una cancelación de membresía o devolución no borra comprobantes autorizados. Definir el flujo de nota de crédito y devolución con las reglas existentes.

Cierre: pruebas con proveedor simulado y, cuando se configure expresamente, ambiente de pruebas. Cubrir autorización, procesamiento pendiente, rechazo, fallo de red y reintento sin factura duplicada. Ninguna prueba emite en producción.

### Etapa 5 — Modalidades adicionales

Estado: posterior al flujo mínimo; priorizar según clientes reales.

- Clases: horarios, capacidad, reservas y cancelaciones.
- Paquetes: sesiones disponibles, consumo y vencimiento.
- Entrenamiento personal: asignación de entrenador y agenda.

Un negocio puede combinar modalidades. Separar configuración comercial, módulos contratados y permisos del usuario. Incorporar cada modalidad con su propia validación y pruebas; no construir todas antes de validar la primera.

Cierre de cada modalidad: funciona junto con las existentes sin alterar contratos históricos ni introducir condiciones por cliente.

### Etapa 6 — Operación SaaS y salida a sitio exclusivo

Estado: pendiente. Las bases de portabilidad deben respetarse desde etapa 1.

- Revisar suscripciones, módulos, vencimientos, límites y sincronización existentes antes de automatizar altas.
- Definir suspensión y recuperación del servicio sin borrar datos ni impedir las acciones necesarias para resolver documentos fiscales pendientes.
- Preparar despliegue, respaldos, restauración, monitoreo y capacidad; compartir sitio también comparte recursos y fallos operativos.
- Crear procedimiento de extracción de un negocio: datos y tablas hijas, archivos, usuarios/permisos, referencias fiscales, configuración, secretos transferidos de forma segura y tareas pendientes.
- Ensayar extracción a sitio vacío con versiones compatibles: verificar conteos, relaciones, archivos, acceso y aislamiento. No trasladar otros negocios ni reutilizar sesiones o credenciales de integración indiscriminadamente.
- Definir corte de escrituras, tratamiento de tareas en curso, cambio de acceso y retorno controlado ante fallo. Conservar claves fiscales y continuidad de secuencias sin dos sitios emitiendo simultáneamente para el mismo origen.

Cierre: piloto operativo validado, restauración ensayada y extracción demostrada. La capacidad de ofrecer sitio exclusivo no debe anunciarse como automática antes de ese ensayo.

## 4. Forma de ejecutar

- Implementar una etapa en cambios revisables, indicando archivos, riesgos y pruebas antes de cambios importantes.
- Actualizar este documento con resultados y pendientes reales; no marcar etapas completas solo por crear DocTypes.
- Mantener datos sintéticos para pruebas de aislamiento y simular servicios externos.
- No introducir un nuevo frontend, un framework de plugins ni automatización de cobros recurrentes sin una necesidad definida.
- Publicación, migración de producción y extracción de clientes requieren alcance y entorno expresamente autorizados.

## 5. Próximo entregable

La prioridad indicada por el usuario fue dejar primero Frappe configurado antes de crear Angular. El piloto `gym_bmarc` ya tiene el negocio de demostración, sede, cuentas, tres planes y terminal preparados según [PILOTO_LOCAL.md](PILOTO_LOCAL.md). La siguiente fase será completar la experiencia de GYM en un proyecto Angular independiente, consumiendo las APIs de panel/asistencias y los casos de uso existentes. La administración y configuración de negocios permanece en Frappe: ver [CONFIGURACION_RAPIDA.md](CONFIGURACION_RAPIDA.md). El backend operativo está implementado según [API_OPERATIVA.md](API_OPERATIVA.md); el frontend aún no está creado.

En la línea fiscal sigue pendiente la corrección vinculada: nota de crédito, conciliación del contrato/aplicaciones y devolución o saldo a favor explícito, con proveedor simulado. La etapa 4.3 ya integra emisión/consulta Lite, formas/plazos fiscales y conservación de identidad ante fallos; falta esa corrección para cerrar la etapa 4. Las pruebas no emiten al SRI. Definir impuestos incluidos y momento/agrupación de facturación, sin duplicar los abonos como nuevos ingresos. La etapa 3 está validada en sitio aislado; la preparación demo de `gym_bmarc` ya cuenta con respaldo previo y validación de acceso; incorporar datos reales requiere su propio alcance e inventario. No confundir recibos internos con emisión electrónica ni dar por terminada la operación SaaS.

## Mejora del Desk solicitada el 2026-10-18

Workspace organizado por tareas, página de inicio con resumen por sucursal,
formularios agrupados y guiados, selección de caja al cobrar y pantalla de
apertura/cierre delegada al motor compartido de Restaurante. Se conserva la
separación del futuro frontend Angular. Ver [USO_DEL_DESK.md](USO_DEL_DESK.md).

Validación: 117 pruebas GYM aprobadas en el sitio aislado. Recorrido Chromium
de administrador y recepción: apertura con fondo USD 10, cobro USD 20, acceso
permitido y cierre USD 30 sin errores JavaScript. Los datos sintéticos fueron
retirados antes de la suite para evitar colisiones de nombres de usuario.
