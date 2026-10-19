/* global gym */
frappe.pages["gym-cash"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Caja del gimnasio"),
		single_column: true,
	});
	const body = document.createElement("div");
	body.className = "p-4";
	page.body.append(body);
	gym.desk.text(
		body,
		"p",
		__(
			"1. El administrador abre caja para el cajero. 2. El cajero registra cobros desde cada membresía. 3. El administrador cuenta el efectivo y cierra el turno."
		),
		"text-muted"
	);
	const business = gym.desk.selector(body, __("Negocio"), "cash-business");
	const branch = gym.desk.selector(body, __("Sucursal"), "cash-branch");
	const user = gym.desk.selector(body, __("Cajero"), "cash-user");
	const result = document.createElement("div");
	result.setAttribute("aria-live", "polite");
	body.append(result);
	let context = { businesses: [], branches: [] };
	let sequence = 0;
	let busy = false;
	const selection = () => ({
		business: business.value,
		branch: branch.value,
		user: user.value || undefined,
	});
	const load = async () => {
		const version = ++sequence;
		result.replaceChildren();
		if (!business.value || !branch.value) {
			gym.desk.text(
				result,
				"p",
				__("Seleccione el negocio y la sucursal para consultar la caja.")
			);
			return;
		}
		const args = selection();
		try {
			const data = await frappe.xcall("gym_management.api.cash.get_cash_context", args);
			if (version !== sequence) return;
			gym.desk.fill(
				user,
				data.users.map((row) => ({
					...row,
					caption: `${row.full_name || row.name} · ${row.name}`,
				})),
				"caption",
				data.user
			);
			user.disabled = !data.can_manage;
			const opening = data.opening;
			gym.desk.text(result, "h4", opening ? __("Caja abierta") : __("Sin caja abierta"));
			if (!data.terminals.length) {
				gym.desk.text(
					result,
					"p",
					__(
						"Falta un terminal activo del establecimiento de esta sucursal. El administrador debe vincular establecimiento, terminal y cajero en la configuración de FacturADA."
					)
				);
				return;
			}
			if (opening) {
				gym.desk.text(
					result,
					"p",
					`${__("Fondo inicial")}: ${format_currency(opening.opening_amount, "USD")} · ${
						opening.opened_at
					}`
				);
				gym.desk.button(result, __("Ir a membresías para cobrar"), () =>
					frappe.set_route("List", "GYM Membership", {
						business: args.business,
						origin_branch: args.branch,
						docstatus: 1,
					})
				);
				if (data.can_manage) {
					const summary = await frappe.xcall(
						"gym_management.api.cash.get_cash_summary",
						{ ...args, user: data.user, cash_opening: opening.name }
					);
					if (version !== sequence) return;
					gym.desk.text(
						result,
						"p",
						`${__("Efectivo esperado")}: ${format_currency(
							summary.cash_system,
							"USD"
						)} · ${__("Retiros")}: ${format_currency(summary.withdrawals, "USD")}`
					);
					gym.desk.text(
						result,
						"p",
						__(
							"El efectivo esperado incluye el fondo inicial y los movimientos de la caja compartida. Los cobros sin vínculo a esta apertura no forman parte de este cierre."
						),
						"text-muted"
					);
					for (const row of summary.payments)
						gym.desk.text(
							result,
							"p",
							`${row.payment_method}: ${format_currency(row.amount, "USD")}`
						);
					gym.desk.button(
						result,
						__("Contar y cerrar caja"),
						() =>
							showDialog(
								"close_cash",
								{ ...args, user: data.user, cash_opening: opening.name },
								[
									{
										fieldname: "cash_counted",
										fieldtype: "Currency",
										label: __("Efectivo contado en caja (USD)"),
										reqd: 1,
										description: __(
											"Incluya el fondo inicial. Escriba 0 si no hay efectivo."
										),
									},
								],
								__("Confirmar cierre")
							),
						true
					);
				}
			} else if (data.can_manage) {
				gym.desk.button(
					result,
					__("Abrir caja"),
					() =>
						showDialog(
							"open_cash",
							{ ...args, user: data.user },
							[
								{
									fieldname: "pos_terminal",
									fieldtype: "Select",
									label: __("Terminal de esta sucursal"),
									reqd: 1,
									options: data.terminals.map((row) => ({
										label: row.terminal_name,
										value: row.name,
									})),
									default:
										data.terminals.length === 1
											? data.terminals[0].name
											: undefined,
								},
								{
									fieldname: "opening_amount",
									fieldtype: "Currency",
									label: __("Fondo inicial (USD)"),
									reqd: 1,
									description: __("Escriba 0 si inicia sin fondo de efectivo."),
								},
							],
							__("Confirmar apertura")
						),
					true
				);
			} else {
				gym.desk.text(
					result,
					"p",
					__(
						"Pida al administrador que abra caja a su nombre para cobrar en efectivo. Puede registrar transferencias y tarjetas desde la membresía."
					)
				);
			}
		} catch {
			if (version === sequence) {
				result.replaceChildren();
				gym.desk.text(
					result,
					"p",
					__(
						"No se pudo consultar la caja. Revise permisos, módulo POS y configuración de la sucursal."
					),
					"text-danger"
				);
			}
		}
	};
	const showDialog = (method, args, fields, label) => {
		const dialog = new frappe.ui.Dialog({
			title: label,
			fields: [
				...fields,
				{ fieldname: "notes", fieldtype: "Small Text", label: __("Observaciones") },
			],
			primary_action_label: label,
			async primary_action(values) {
				if (busy) return;
				busy = true;
				dialog.get_primary_btn().prop("disabled", true);
				try {
					const data = await frappe.xcall(`gym_management.api.cash.${method}`, {
						...args,
						...values,
					});
					dialog.hide();
					frappe.msgprint(
						method === "close_cash"
							? __("Caja cerrada. Diferencia: {0}. Cierre: {1}", [
									format_currency(data.difference, "USD"),
									data.name,
							  ])
							: __("Caja abierta para el cajero seleccionado.")
					);
					await load();
				} finally {
					busy = false;
					dialog.get_primary_btn().prop("disabled", false);
				}
			},
		});
		dialog.show();
	};
	const changeBusiness = () => {
		user.replaceChildren();
		gym.desk.fill(
			branch,
			context.branches.filter(
				(row) => row.business === business.value && row.status === "Activo"
			),
			"branch_name"
		);
		load();
	};
	business.addEventListener("change", changeBusiness);
	branch.addEventListener("change", () => {
		user.replaceChildren();
		load();
	});
	user.addEventListener("change", load);
	page.set_secondary_action(__("Actualizar"), load);
	wrapper.gym_refresh = load;
	frappe
		.xcall("gym_management.api.context.get_context")
		.then((data) => {
			context = data;
			gym.desk.fill(business, context.businesses, "business_name");
			changeBusiness();
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
frappe.pages["gym-cash"].on_page_show = (wrapper) => wrapper.gym_refresh?.();
