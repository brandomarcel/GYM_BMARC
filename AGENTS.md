# Guía para agentes de IA — GYM_MANAGEMENT

## 1. Alcance y arquitectura

Este repositorio contiene la app Frappe `gym_management`, titulada **Gym BMARC**, para administrar gimnasios. Su módulo es `Gym BMARC` y su paquete de dominio es `gym_management/gym_bmarc`. No confundir esta app con el frontend Angular ni con las apps FacturADA vecinas del Bench.

La arquitectura sigue el modelo estándar de Frappe:

- **Persistencia y metadatos:** DocTypes definidos en JSON, con campos, relaciones, permisos y configuración de formularios.
- **Backend:** controladores Python que heredan de `frappe.model.document.Document`. La mayoría son plantillas; `Customer.before_save` construye `full_name` en mayúsculas.
- **Interfaz:** Frappe Desk con JavaScript, eventos `frappe.ui.form.on`, llamadas `frappe.call`, páginas y Workspaces. No hay una aplicación SPA independiente.
- **Reportes:** Script Reports con `execute(filters=None)`, consultas SQL y retorno de columnas/datos; sus archivos JS declaran filtros.
- **API propia:** `gym_management/public/apiRest.py` contiene el método autenticado `get_company_and_plans(user)`, expuesto con `@frappe.whitelist()`. Su ubicación es atípica: conservar la ruta pública Python existente al modificarla.
- **Extensiones:** `hooks.py` contiene los metadatos de la app; las opciones de eventos, scheduler, assets y permisos están comentadas. No asumir que esos ejemplos están activos.

### Modelo de negocio

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

La lista activa de dependencias Python está vacía: Frappe se instala mediante Bench. No se declara `required_apps` activo ni dependencia explícita de ERPNext. No hay `package.json`, lockfile JS ni pipeline de CI versionado en esta app. Las consultas actuales usan sintaxis de MariaDB/MySQL (`DATEDIFF`, `IF`, nombres con backticks); no asumir compatibilidad con PostgreSQL.

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
9. Añadir pruebas útiles al cambiar lógica: permisos entre compañías, valores monetarios, descuentos, fechas y contratos API según el alcance. Los siete `test_*.py` actuales son clases `FrappeTestCase` vacías: no representan cobertura funcional.
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
