/* global gym */
frappe.pages["gym-home"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Inicio del gimnasio"),
		single_column: true,
	});
	const body = document.createElement("div");
	body.className = "p-4";
	page.body.append(body);
	gym.desk.text(
		body,
		"p",
		__(
			"Su jornada: abrir caja → registrar socio → contratar y confirmar membresía → cobrar → registrar ingresos → cerrar caja."
		),
		"text-muted"
	);
	const business = gym.desk.selector(body, __("Negocio"), "home-business");
	const branch = gym.desk.selector(body, __("Sucursal"), "home-branch");
	const actions = document.createElement("div");
	const result = document.createElement("div");
	result.setAttribute("aria-live", "polite");
	body.append(actions, result);
	let context = { businesses: [], branches: [] };
	let sequence = 0;
	const render = async () => {
		const version = ++sequence;
		actions.replaceChildren();
		result.replaceChildren();
		if (!business.value || !branch.value) {
			gym.desk.text(result, "p", __("Seleccione negocio y sucursal para comenzar."));
			return;
		}
		const args = { business: business.value, branch: branch.value };
		gym.desk.button(
			actions,
			__("Registrar socio"),
			() =>
				frappe.new_doc("GYM Member", {
					business: args.business,
					home_branch: args.branch,
				}),
			true
		);
		gym.desk.button(actions, __("Membresías y cobros"), () =>
			frappe.set_route("List", "GYM Membership", {
				business: args.business,
				origin_branch: args.branch,
			})
		);
		gym.desk.button(actions, __("Control de acceso"), () => frappe.set_route("gym-access"));
		gym.desk.button(actions, __("Caja"), () => frappe.set_route("gym-cash"));
		try {
			const data = await frappe.xcall(
				"gym_management.api.operations.get_reception_panel",
				args
			);
			if (version !== sequence) return;
			gym.desk.text(result, "h4", __("Hoy en esta sucursal"));
			const cards = document.createElement("div");
			cards.className = "row mb-4";
			result.append(cards);
			for (const [key, label] of Object.entries({
				active_contracts: "Contratos vigentes",
				expiring_contracts: "Vencen en 7 días",
				entries_today: "Ingresos permitidos hoy",
				contracts_with_balance: "Contratos con saldo",
			})) {
				const card = document.createElement("div");
				card.className = "col-sm-6 col-lg-3 mb-3";
				cards.append(card);
				gym.desk.text(card, "div", __(label), "text-muted");
				gym.desk.text(card, "strong", String(data.cards[key]), "h3");
			}
			gym.desk.text(
				result,
				"p",
				`${__("Saldo pendiente total")}: ${format_currency(data.cards.outstanding, "USD")}`
			);
			gym.desk.text(
				result,
				"p",
				__(
					"Un contrato vigente por fecha puede requerir pago o autorización de crédito para permitir el acceso."
				),
				"text-muted"
			);
			for (const [key, title] of [
				["expiring", "Próximos vencimientos"],
				["with_balance", "Cobros pendientes"],
			]) {
				gym.desk.text(result, "h4", __(title));
				const rows = data.lists[key];
				if (!rows.length)
					gym.desk.text(result, "p", __("Sin pendientes en esta lista."), "text-muted");
				for (const row of rows) {
					const line = document.createElement("div");
					line.className = "mb-2";
					result.append(line);
					gym.desk.button(line, row.member_name || row.name, () =>
						frappe.set_route("Form", "GYM Membership", row.name)
					);
					gym.desk.text(
						line,
						"span",
						`${__("Vence")}: ${row.end_date} · ${__("Saldo")}: ${format_currency(
							row.outstanding,
							"USD"
						)}`
					);
				}
			}
			gym.desk.text(
				result,
				"p",
				__(
					"Se muestran hasta 10 contratos por lista. Consulte Membresías y saldos para revisar el conjunto completo."
				),
				"text-muted"
			);
		} catch {
			if (version === sequence)
				gym.desk.text(
					result,
					"p",
					__(
						"No se pudo cargar el resumen. Puede usar los accesos disponibles según sus permisos."
					),
					"text-danger"
				);
		}
	};
	business.addEventListener("change", () => {
		gym.desk.fill(
			branch,
			context.branches.filter(
				(row) => row.business === business.value && row.status === "Activo"
			),
			"branch_name"
		);
		render();
	});
	branch.addEventListener("change", render);
	page.set_secondary_action(__("Actualizar"), render);
	wrapper.gym_refresh = render;
	frappe
		.xcall("gym_management.api.context.get_context")
		.then((data) => {
			context = data;
			gym.desk.fill(business, context.businesses, "business_name");
			business.dispatchEvent(new Event("change"));
		})
		.catch(() =>
			gym.desk.text(
				result,
				"p",
				__("No se pudo cargar su contexto. Actualice la página."),
				"text-danger"
			)
		);
};
frappe.pages["gym-home"].on_page_show = (wrapper) => wrapper.gym_refresh?.();
