### Gym BMARC

App para gestion de gimnacios

La base nueva requiere `facturada_core` y agrega sucursales, asignaciones de personal
y socios separados por negocio. Ver [configuración y validación de la etapa 2](docs/BASE_MULTIEMPRESA.md).
La base fue validada en un sitio aislado. La etapa 3 añade membresías por tiempo, políticas de pago/acceso, asistencias y recibos internos con Lite: ver [membresías y cobros](docs/MEMBRESIAS_Y_COBROS.md). Efectivo usa la caja existente de Restaurante; La [etapa 4.1](docs/BORRADOR_FISCAL.md) prepara borradores fiscales con Lite, sin emitir. La [etapa 4.2](docs/APLICACIONES_DE_RECIBOS.md) permite aplicar y reversar recibos existentes sin duplicar caja. La [etapa 4.3](docs/EMISION_FISCAL.md) integra emisión y consulta con proveedor simulado. Correcciones fiscales vinculadas y datos reales siguen pendientes. El [piloto local](docs/PILOTO_LOCAL.md) está preparado con configuración demo.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench --site <sitio> install-app facturada_core
bench --site <sitio> install-app gym_management
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/gym_management
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit

La emisión y consulta fiscal mediante Lite se describen en [docs/EMISION_FISCAL.md](docs/EMISION_FISCAL.md). Las pruebas usan proveedor simulado; las correcciones fiscales vinculadas y la adopción de datos reales siguen pendientes.

El frontend operativo de GYM será Angular independiente. La administración permanece en Frappe: [configuración rápida](docs/CONFIGURACION_RAPIDA.md), ruta `/app/gym-setup`. El backend del panel y las asistencias se describe en [API operativa](docs/API_OPERATIVA.md).

El piloto `gym_bmarc` ya está configurado para desarrollo local: [accesos y configuración demo](docs/PILOTO_LOCAL.md). Angular aún no se ha creado.

Las [promociones individuales](docs/PROMOCIONES.md) por porcentaje o importe fijo ya se configuran en Frappe y se seleccionan al contratar. El 2×1 grupal sigue pendiente.

Guía del Desk y caja: [docs/USO_DEL_DESK.md](docs/USO_DEL_DESK.md).
