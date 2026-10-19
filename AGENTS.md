# Guía para agentes de IA — GYM_MANAGEMENT

## 1. Alcance y arquitectura

Este repositorio contiene la app Frappe `gym_management`, titulada **Gym BMARC**, para administrar gimnasios. Su módulo es `Gym BMARC` y su paquete de dominio es `gym_management/gym_bmarc`. No confundir esta app con el frontend Angular ni con las apps FacturADA vecinas del Bench.

### Dirección acordada

Leer [docs/HOJA_DE_RUTA.md](docs/HOJA_DE_RUTA.md) antes de cambios estructurales. El objetivo acordado es un SaaS multiempresa y multisucursal integrado con FacturADA Core/Lite, con módulos configurables y posibilidad de trasladar un negocio a un sitio exclusivo. La base con Core está implementada y validada en sitio aislado; las membresías y los cobros internos están implementados en pruebas; el puente fiscal con Lite incluye borrador, aplicaciones y emisión/consulta simulada; las correcciones vinculadas siguen pendientes. No reemplazar los campos actuales de compañía ni instalar dependencias sin resolver el mapeo y la migración descritos en la etapa 1. Actualizar el estado de cada etapa únicamente con evidencia de implementación y validación.

El inventario y la propuesta concreta están en [docs/DISENO_BASE_Y_MIGRACION.md](docs/DISENO_BASE_Y_MIGRACION.md). El piloto fue respaldado y preparado posteriormente con configuración demo según [docs/PILOTO_LOCAL.md](docs/PILOTO_LOCAL.md). Antes de cambios posteriores, volver a inventariar sus datos: ya no es un sitio vacío. El usuario pidió políticas configurables para pago completo/abonos/crédito, renovaciones y acceso por sede; consultar [docs/MEMBRESIAS_Y_COBROS.md](docs/MEMBRESIAS_Y_COBROS.md) para las políticas implementadas y sus límites. Los recibos compartidos de Lite son internos y no emiten facturas.

La nueva base y su validación se describen en [docs/BASE_MULTIEMPRESA.md](docs/BASE_MULTIEMPRESA.md). La validación inicial fue en `gym_stage2_test.localhost`. Posteriormente el usuario autorizó preparar el piloto local `gym_bmarc`; ahora contiene negocio, usuarios, sede, planes y terminal de demostración. No ejecutar pruebas automáticas ni limpieza de fixtures sobre ese piloto. El código requiere Core y define `GYM Branch`, `GYM Branch User`, `GYM Member`, permisos por negocio/sede y el rol técnico `GYM User`. Las listas y documentos deben conservar los hooks de `permissions.py`. `GymAwareFile` protege además la descarga privada y valida antes de escribir archivos públicos. No quitar esos controles ni habilitar compartición genérica. Los modelos heredados siguen existiendo; no están migrados.

La arquitectura sigue el modelo estándar de Frappe:

- **Persistencia y metadatos:** DocTypes definidos en JSON, con campos, relaciones, permisos y configuración de formularios.
- **Backend:** controladores Python que heredan de `frappe.model.document.Document`. La mayoría son plantillas; `Customer.before_save` construye `full_name` en mayúsculas.
- **Interfaz:** Frappe Desk con JavaScript, eventos `frappe.ui.form.on`, llamadas `frappe.call`, páginas y Workspaces. No hay una aplicación SPA independiente.
- **Reportes:** Script Reports con `execute(filters=None)`, consultas SQL y retorno de columnas/datos; sus archivos JS declaran filtros.
- **API propia:** `gym_management/public/apiRest.py` contiene el método autenticado `get_company_and_plans(user)`, expuesto con `@frappe.whitelist()`. Su ubicación es atípica: conservar la ruta pública Python existente al modificarla.
- **Extensiones:** `hooks.py` contiene metadatos y hooks activos de instalación, permisos, eventos, formularios y override de File para la nueva base. El resto de ejemplos comentados no están activos.

La decisión de integración fiscal está en [docs/INTEGRACION_FISCAL.md](docs/INTEGRACION_FISCAL.md): dentro del sitio se usan servicios Lite con permisos del operador; la API externa se reserva para sistemas remotos. La preparación de borradores está implementada según [docs/BORRADOR_FISCAL.md](docs/BORRADOR_FISCAL.md); las aplicaciones y reversos están implementados según [docs/APLICACIONES_DE_RECIBOS.md](docs/APLICACIONES_DE_RECIBOS.md); emisión/consulta están implementadas según [docs/EMISION_FISCAL.md](docs/EMISION_FISCAL.md). Respetar aplicaciones y saldos existentes, sin duplicar ingresos ni asumir impuestos incluidos. No usar credenciales API o contexto Administrator para ampliar permisos de recepción.

Lite conserva las aplicaciones en `FacturADA Receipt Application` y su caso de uso en `payments/applications.py`. No convertirlas en nuevos recibos o abonos tradicionales. El adaptador GYM autoriza origen, negocio y sede. Conservar locks antes de `save` de Frappe, proyección de saldos con lecturas actuales, límites por recibo/factura, reversos con motivo y bloqueo de anulación de recibos aplicados. Aplicar dinero histórico de caja cerrada no modifica el cierre; reversar aplicaciones de esa caja está bloqueado.

El flujo fiscal separa `api/invoicing.py` (RPC), `billing/service.py` (caso de uso y `DraftGateway`), `billing/lite.py` (adaptador) y `GYM Billing Request` (persistencia inmutable). Las inserciones genéricas reutilizan el mismo caso de uso. Lite ejecuta `invoice_source_adapters` antes de validar, numerar, enviar y devolver/listar estos documentos. Conservar la protección del origen, el orden de locks y los controles de archivos; el envío GYM solo pasa por `billing/emission.py`, que confirma identidad e intento antes del POST y conserva el lock compartido entre commits. Todo reintento posterior solo consulta. No envolver este caso de uso en otra transacción. Conservar `emission_identity`, condiciones inmutables y lecturas actuales de formas fiscales; las rutas genéricas no emiten ni crean correcciones desvinculadas. Los campos Data hacia Lite evitan dependencias obligatorias de esquema, pero se validan como referencias de negocio en servidor.

La etapa 3 añade `GYM Membership Plan`, `GYM Membership`, `GYM Membership Branch` y `GYM Attendance`, APIs en `api/memberships.py`, reglas en `membership_rules.py`, adaptador Lite en `payments.py` y página `gym-access`. Conservar snapshots confirmados, orden de bloqueos socio → contrato, claves de reintento y recibos compartidos. No duplicar ingresos al conectar facturación ni sustituir anulación por borrado. Lite es opcional para GYM; sin Lite no hay cobros. Efectivo utiliza la caja existente de Restaurante.

### Frontend y administración acordados

El frontend operativo de GYM será un proyecto Angular independiente del Angular de Facturada. Frappe conserva lógica, permisos, persistencia y APIs; El 2026-10-18 el usuario autorizó mejorar el Desk para facilitar el uso actual; esto no reemplaza el frontend Angular previsto. Los formularios y herramientas Desk existentes siguen disponibles para administración y prueba. El administrador técnico configura negocios, licencias, sucursales, usuarios y planes en Frappe mediante `gym-setup` y los formularios existentes; no otorgar System Manager al personal o a los dueños de gimnasios para facilitarlo.

`operations.py` contiene las consultas operativas y `api/operations.py` su transporte para Angular. Conservar alcance SQL por negocio/sede también en totales y listas, paginación y límites de fechas. Los nombres de socios visitantes requieren además permiso sobre su perfil de origen. Los saldos provienen de recibos confirmados, no de formas fiscales. El checklist `api/setup.py` es de lectura y exige rol técnico y usuario habilitado; no convierte conteos básicos en alta automática ni en garantía de preparación completa. Ver [docs/API_OPERATIVA.md](docs/API_OPERATIVA.md) y [docs/CONFIGURACION_RAPIDA.md](docs/CONFIGURACION_RAPIDA.md).

El usuario requiere promociones, incluido 2×1. Ver [docs/PROMOCIONES.md](docs/PROMOCIONES.md): los descuentos individuales por porcentaje/importe fijo están implementados en `promotions.py` y `api/promotions.py`; los grupos y el beneficio por tiempo siguen pendientes. Conservar cálculo de servidor, validación de campaña al confirmar, snapshot histórico y compatibilidad de hashes sin promoción. Recepción aplica campañas con permisos de contratación, sin ampliar el permiso de descuento manual. No simular una promoción grupal con socios fusionados, recibos duplicados o modificaciones retroactivas del plan. Distinguir beneficio de tiempo y de varios socios; definir contratación, distribución de importes/acceso y vínculo fiscal antes de implementar el grupo.

### Modelo de negocio heredado

| Entidad | Función y relaciones |
| --- | --- |
| `Company` | Gimnasio/compañía; contiene `Planes Contratados`. |
| `Planes` / `Planes Contratados` | Catálogo de planes contratados por compañías y tabla hija con vigencia, costo y estado. |
| `Customer` / `Medidas` | Clientes vinculados mediante `company_id` y tabla hija de medidas corporales; incluye datos de contacto y QR. |
| `Membership_Type` | Tipos de membresía por `company`, costo, IVA, total y duración en meses. |
| `memberships_register` | Cliente, compañía, plan, fechas, descuento, total, estado y tabla hija `payment_method`. |
| `products` / `sales_products` | Catálogo y registros de ventas asociados a `company_id`. |

Los reportes disponibles son `Membresias Registradas` y `Membresias a expirar`. Los estados de membresías y planes contratados son `Activo` e `Inactivo`; los métodos de pago definidos son `EFECTIVO` y `TRANSFERENCIA`.

## 2. Stack y versiones verificables

| Componente | Versión o condición | Fuente |
| --- | --- | --- |
| App | `0.0.1` | `gym_management/__init__.py` |
| Python | `>=3.10`; Ruff apunta a `py310` | `pyproject.toml` |
| Frappe | Gestionado por Bench, sin restricción activa en la app | `pyproject.toml` |
| Empaquetado | `flit_core >=3.4,<4`, backend `flit_core.buildapi` | `pyproject.toml` |
| Ruff | `v0.8.1` | `.pre-commit-config.yaml` |
| ESLint | `v8.44.0`, configuración clásica `.eslintrc`, entorno ES2022 | Configuración local |
| Prettier | `v2.7.1` | `.pre-commit-config.yaml` |
| Hooks generales de pre-commit | `v5.0.0` | `.pre-commit-config.yaml` |

En el checkout vecino inspeccionado, Frappe declara `15.116.1` y Node.js `>=18`. Son referencias del entorno actual, **no versiones fijadas por este repositorio**; verificar el Bench de destino antes de asumir compatibilidad.

La lista activa de dependencias Python está vacía: Frappe se instala mediante Bench. `hooks.py` declara `required_apps = ["facturada_core"]`; instalar Core antes de GYM. No se declara dependencia de ERPNext. No hay `package.json`, lockfile JS ni pipeline de CI versionado en esta app. Las consultas actuales usan sintaxis de MariaDB/MySQL (`DATEDIFF`, `IF`, nombres con backticks); no asumir compatibilidad con PostgreSQL.

Integraciones presentes en el navegador: generación de QR mediante `api.qrserver.com` y enlaces de WhatsApp `wa.me` con prefijo ecuatoriano `+593`. No son paquetes instalados ni implican envío automático desde el backend.

## 3. Estructura del repositorio

```text
gym_management/
├── __init__.py                 # Versión de la app
├── hooks.py                    # Metadatos y puntos de extensión
├── modules.txt                 # Módulo Gym BMARC
├── patches.txt                 # Registro pre_model_sync / post_model_sync
├── patches/                    # Migraciones Python; actualmente sin implementaciones
├── public/apiRest.py           # API existente de compañía y planes
├── config/                     # Configuración; actualmente inicializadores
├── templates/pages/            # Plantillas; actualmente inicializadores
└── gym_bmarc/
    ├── doctype/<nombre>/       # Esquema JSON, controlador PY, JS y tests si existen
    ├── report/<nombre>/        # Script Reports: JSON + PY + JS
    ├── page/prueba/            # Página Desk de prueba
    └── workspace/              # Principal, Membresias y Reportes
```

En la raíz: `pyproject.toml`, `.editorconfig`, `.eslintrc`, `.pre-commit-config.yaml`, `.gitignore`, `README.md` y licencia MIT. Respetar además las instrucciones aplicables del `AGENTS.md` superior del Bench; no trasladar reglas específicas de facturación a este dominio sin comprobar su pertinencia.

## 4. Comandos esenciales

Ejecutar los comandos `bench` desde la **raíz del Bench**, normalmente dos niveles por encima de esta app. Sustituir `<sitio_dev>` y `<sitio_test>` por sitios identificados expresamente; nunca adivinar un sitio de producción.

| Objetivo | Comando |
| --- | --- |
| Ver versiones del Bench | `bench version` |
| Ver apps instaladas en un sitio | `bench --site <sitio_dev> list-apps` |
| Iniciar entorno de desarrollo | `bench start` |
| Compilar assets de la app | `bench build --app gym_management` |
| Compilar assets para producción | `bench build --app gym_management --production` |
| Ejecutar pruebas de la app | `bench --site <sitio_test> run-tests --app gym_management` |
| Ejecutar pruebas de un módulo | `bench --site <sitio_test> run-tests --module gym_management.gym_bmarc.doctype.customer.test_customer` |
| Instalar app en un sitio de desarrollo preparado | `bench --site <sitio_dev> install-app gym_management` |
| Sincronizar esquema y ejecutar patches | `bench --site <sitio_dev> migrate` |

Instalación y migración modifican la base de datos. Ejecutarlas solo en el entorno autorizado para la tarea. Las pruebas requieren un sitio de pruebas con la app instalada y pruebas habilitadas; no habilitarlas sobre producción. La app no contiene bundles propios actualmente: el build usa la infraestructura de Frappe y no sustituye una migración de DocTypes.

Desde la **raíz de este repositorio**, con las herramientas disponibles:

```bash
pre-commit install
pre-commit run --all-files
```

`pre-commit install` configura hooks Git locales; no es necesario para leer o editar código. Los hooks pueden descargar sus entornos y modificar archivos (orden de imports, formato, Prettier). Revisar el diff y limitar la ejecución a los archivos tocados cuando existan cambios ajenos:

```bash
pre-commit run --files ruta/al/archivo.py ruta/al/archivo.js
```

Si Ruff está instalado en una versión compatible, estas comprobaciones no corrigen archivos:

```bash
ruff check gym_management
ruff format --check gym_management
```

No inventar comandos `npm run dev`, `npm test` o `npm run lint`: no hay scripts npm locales. El README menciona pyupgrade, pero no existe un hook independiente de pyupgrade; Ruff tiene habilitada la familia `UP`. Informar si falta una herramienta o un servicio en lugar de afirmar que una validación pasó.

## 5. Estilo y patrones

- Respetar `.editorconfig`: UTF-8, LF, quitar espacios finales; tabulaciones de ancho 4 en Python/JS/CSS/HTML y dos espacios en JSON. Los JSON no requieren salto de línea final.
- Para Python prevalece el formato configurado en Ruff: comillas dobles, tabulaciones y longitud 110. `.editorconfig` indica 99: evitar reformateos masivos para resolver esta diferencia.
- Ruff selecciona `F`, `E`, `W`, `I`, `UP`, `B`, `RUF`, con exclusiones explícitas. No desactivar reglas para ocultar errores introducidos.
- JavaScript usa `.eslintrc` y Prettier del pre-commit. Los globales `frappe`, `__`, `$` y otros del Desk ya están declarados. Evitar nuevos logs de datos personales; `no-console` está configurado como advertencia.
- Conservar el patrón Frappe por DocType: esquema en JSON, validaciones y reglas persistentes en el controlador Python, interacción visual en JS. No confiar en cálculos o filtros del navegador como validación de servidor.
- Usar ORM de Frappe cuando sea apropiado. En reportes, mantener `execute(filters=None)` y la correspondencia entre filtros JS, columnas y datos Python; parametrizar valores SQL.
- Usar `__()` para nuevos textos visibles traducibles y nombres descriptivos para código nuevo. Mantener nombres exactos de DocTypes, campos, rutas RPC y clases existentes aunque mezclen idiomas, mayúsculas o snake_case.
- Mantener `Customer.full_name` y las relaciones de tablas hijas. No confundir los planes de compañía (`Planes`) con los tipos de membresía de clientes (`Membership_Type`).

## 6. Reglas estrictas al editar

### La IA DEBE

1. Leer las instrucciones aplicables, revisar `git status` y analizar controladores, esquemas, consumidores JS y reportes afectados antes de editar.
2. Explicar alcance, archivos previstos, solución y riesgos antes de cambios importantes. Preguntar cuando falte un dato indispensable de negocio o del entorno; no inventarlo.
3. Realizar cambios pequeños y mantenibles; preservar cambios del usuario y limitarse a esta app salvo alcance explícito.
4. Validar autorización en backend. El código utiliza `User Permission` con `allow = "Company"`, y campos `company` o `company_id` según el DocType: comprobar cada esquema y que la compañía solicitada sea accesible al usuario autenticado.
5. Tratar parámetros como `user` y `company` como entradas no confiables. `@frappe.whitelist()` permite invocar un método, pero no demuestra acceso al documento. `frappe.get_all` y SQL requieren comprobar explícitamente el alcance autorizado.
6. Mantener valores SQL parametrizados y comprobar permisos también en reportes. Aplicar filtros de compañía en el cliente o asignar una compañía por defecto no reemplaza la autorización del servidor.
7. Revisar antes de tocar permisos JSON: los DocTypes principales declaran `System Manager`, mientras los reportes incluyen `Admin_Gym`. La app no exporta una definición de ese rol; verificar su provisión en el sitio.
8. Para cambios de esquema, revisar Links, tablas hijas, nombres SQL, JS, reportes y API. Versionar metadatos y registrar un patch cuando sea necesario migrar datos, respetando las fases de `patches.txt` y evitando efectos duplicados al reintentar.
9. Añadir pruebas útiles al cambiar lógica: permisos entre compañías, valores monetarios, descuentos, fechas y contratos API según el alcance. Los tests heredados vacíos no representan cobertura; las suites funcionales nuevas viven en `gym_management/tests`.
10. Validar el flujo afectado en un sitio de desarrollo: guardar y recargar documentos, revisar cálculos y reportes, probar acceso permitido y denegado. Reportar archivos cambiados, comprobaciones ejecutadas, limitaciones y pasos manuales pendientes.

### La IA NO DEBE

1. Cambiar arquitectura, añadir frameworks/dependencias o mover la API existente sin autorización y análisis de compatibilidad.
2. Editar Frappe, ERPNext ni apps vecinas para implementar comportamiento de gimnasio sin una solicitud explícita.
3. Renombrar `Company`, `Customer` u otros DocTypes/campos por estética. `Company` y `Customer` coinciden con nombres de ERPNext: comprobar conflictos y propiedad del esquema antes de instalar o migrar en un sitio compartido; no sobrescribir modelos ajenos.
4. Añadir `allow_guest=True`, `ignore_permissions=True`, consultas sin alcance o ampliaciones de roles como atajos para resolver errores de acceso.
5. Interpolar entradas del usuario en SQL o introducir HTML no escapado con datos de clientes. No ampliar el envío de datos personales a proveedores QR u otros servicios sin una necesidad autorizada.
6. Versionar credenciales, tokens, `site_config.json`, respaldos, datos reales de clientes, medidas corporales, recibos o logs sensibles.
7. Ejecutar borrados, reinstalaciones, restauraciones, migraciones de producción, despliegues o pushes sin autorización para esa operación. No usar `bench update` como comprobación rutinaria: afecta el Bench completo.
8. Ejecutar formateos masivos, eliminar código no relacionado, limpiar cambios ajenos o alterar configuraciones globales del Bench para facilitar una tarea local.
9. Copiar patrones inseguros existentes como si fueran garantías. La API de compañía y los reportes necesitan revisión de autorización al modificarlos; no asumir que su comportamiento actual ya aísla compañías.
10. Afirmar que existen scheduler de expiración, integración contable ERPNext, suite E2E o CI sin evidencia. `page/prueba` referencia un reporte llamado `Membresias de la Semana Actual` que no está definido en este repositorio; no basar nuevas funcionalidades en esa referencia sin verificarla.

## 7. Mantenimiento de esta guía

Actualizar este archivo cuando cambien los comandos, dependencias, estructura o contratos del proyecto. Distinguir siempre entre configuración declarada, estado del entorno local y funcionalidad efectivamente implementada. Para cambios exclusivamente documentales, revisar exactitud y diff; no ejecutar migraciones ni pruebas con base de datos innecesariamente.

Las mejoras de Desk y el recorrido de caja están descritos en [docs/USO_DEL_DESK.md](docs/USO_DEL_DESK.md). `api/cash.py` es transporte y `cash.py` adapta el alcance GYM a los servicios de Restaurante; no duplicar el motor financiero ni ampliar permisos de recepción. `public/js/desk.js` contiene únicamente ayudas de presentación; el servidor sigue autorizando cada operación.
