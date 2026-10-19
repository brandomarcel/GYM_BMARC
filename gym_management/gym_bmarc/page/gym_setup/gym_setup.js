frappe.pages["gym-setup"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Configuración de GYM"),
		single_column: true,
	});
	page.set_primary_action(__("Crear negocio"), () => frappe.new_doc("FacturADA Business"));
	const body = document.createElement("div");
	body.className = "p-4";
	page.body.append(body);
	const caption = document.createElement("label");
	caption.htmlFor = "gym-setup-business";
	caption.textContent = __("Negocio a configurar");
	const business = document.createElement("select");
	business.id = "gym-setup-business";
	business.className = "form-control mb-4";
	const result = document.createElement("div");
	result.setAttribute("aria-live", "polite");
	body.append(caption, business, result);
	const message = (text) => {
		const paragraph = document.createElement("p");
		paragraph.textContent = text;
		result.append(paragraph);
	};
	let requestId = 0;
	const render = async () => {
		const selected = business.value;
		const current = ++requestId;
		result.replaceChildren();
		if (!selected) {
			message(
				__("Cree un negocio o seleccione uno existente para revisar su configuración.")
			);
			return;
		}
		try {
			const data = await frappe.xcall("gym_management.api.setup.get_setup_checklist", {
				business: selected,
			});
			if (current !== requestId) return;
			result.replaceChildren();
			message(
				__(
					"Configure en este orden. La suscripción al software pertenece al gimnasio; los planes de membresía pertenecen a sus socios."
				)
			);
			const help = {
				subscription: __(
					"Active el módulo GYM en la suscripción del negocio. Para caja también se necesita POS."
				),
				branches: __(
					"Registre cada sede. Para cobrar en efectivo, vincule su establecimiento de FacturADA."
				),
				users: __(
					"Vincule las cuentas al negocio y asigne el rol adecuado; recepción no necesita System Manager."
				),
				assignments: __("Indique en qué sucursales puede trabajar cada usuario."),
				plans: __(
					"Configure duración, precio en USD, sedes, renovación y condiciones de pago."
				),
			};
			for (const [index, step] of data.steps.entries()) {
				const row = document.createElement("div");
				row.className = "mb-4";
				const label = document.createElement("p");
				label.textContent = `${index + 1}. ${
					step.ready ? __("Registrado") : __("Por configurar")
				} · ${step.title} (${step.count})`;
				row.append(label);
				if (help[step.key]) {
					const description = document.createElement("p");
					description.className = "text-muted";
					description.textContent = help[step.key];
					row.append(description);
				}
				const open = document.createElement("button");
				open.className = "btn btn-default btn-sm mr-2";
				open.textContent = __("Abrir");
				open.addEventListener("click", () =>
					frappe.set_route("List", step.doctype, { business: selected })
				);
				row.append(open);
				if (step.key !== "subscription" || !step.count) {
					const create = document.createElement("button");
					create.className = "btn btn-default btn-sm";
					create.textContent = __("Crear");
					create.addEventListener("click", () =>
						frappe.new_doc(step.doctype, { business: selected })
					);
					row.append(create);
				}
				result.append(row);
			}
			message(data.note);
			if (!data.payments_available)
				message(
					__(
						"Los cobros requieren Lite instalado. La operación GYM no requiere habilitar facturación electrónica."
					)
				);
			if (!data.cash_available)
				message(__("Los cobros en efectivo requieren la caja compartida de Restaurante."));
		} catch {
			if (current === requestId) {
				result.replaceChildren();
				message(
					__(
						"No se pudo consultar la configuración. Revise permisos y actualice la página."
					)
				);
			}
		}
	};
	business.addEventListener("change", render);
	const loadBusinesses = async () => {
		const selected = business.value;
		const rows = await frappe.xcall("gym_management.api.setup.get_setup_businesses");
		business.replaceChildren(new Option(__("Seleccione un negocio"), ""));
		for (const row of rows) business.add(new Option(row.business_name, row.name));
		business.value = rows.some((row) => row.name === selected)
			? selected
			: rows.length === 1
			? rows[0].name
			: "";
		await render();
	};
	page.set_secondary_action(__("Actualizar"), loadBusinesses);
	loadBusinesses().catch(() => message(__("No se pudo cargar la lista de negocios.")));
};
