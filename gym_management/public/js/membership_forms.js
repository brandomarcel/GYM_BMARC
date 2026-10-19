/* global gym */
for (const doctype of ["GYM Membership Plan", "GYM Membership", "GYM Attendance"]) {
	frappe.ui.form.on(doctype, {
		setup(frm) {
			// Link metadata is copied for each document, while setup runs once
			// per form instance. Renewals must inherit the same scoped-link policy.
			for (const field of ["business", "currency"]) {
				const df = frappe.meta.get_docfield(doctype, field);
				if (df) df.ignore_link_validation = true;
			}
			frm.set_df_property("business", "ignore_link_validation", true);
			if (frappe.meta.get_docfield(doctype, "currency"))
				frm.set_df_property("currency", "ignore_link_validation", true);
			frm.set_query("business", () => ({
				query: "gym_management.api.context.business_query",
			}));
			for (const field of ["origin_branch", "branch"]) {
				if (frappe.meta.get_docfield(doctype, field)) {
					frm.set_query(field, () => ({
						filters: { business: frm.doc.business, status: "Activo" },
					}));
				}
			}
			for (const field of ["member", "plan", "previous_membership"]) {
				if (frappe.meta.get_docfield(doctype, field)) {
					frm.set_query(field, () => ({ filters: { business: frm.doc.business } }));
				}
			}
			if (frappe.meta.get_docfield(doctype, "branches")) {
				frm.set_query("branch", "branches", () => ({
					filters: { business: frm.doc.business, status: "Activo" },
				}));
			}
		},
		async refresh(frm) {
			await gym.desk.defaults(frm);
			if (doctype === "GYM Membership" && frm.doc.docstatus === 0)
				frm.set_intro(
					__(
						"1. Seleccione socio y plan. 2. Revise fechas y promoción. 3. Guarde y confirme la membresía. Después registre el cobro."
					)
				);
			if (doctype === "GYM Membership" && frm.doc.docstatus === 1) {
				const capabilities = await frappe.xcall(
					"gym_management.api.memberships.get_membership_summary",
					{ name: frm.doc.name }
				);
				frm.set_intro(
					__(
						"Pagado: {0} · Pendiente: {1}. Use Registrar cobro para recibir dinero; la factura se gestiona por separado.",
						[
							format_currency(capabilities.paid, "USD"),
							format_currency(capabilities.outstanding, "USD"),
						]
					),
					Number(capabilities.outstanding) > 0 ? "orange" : "green"
				);
				if (capabilities.can_approve_credit && frm.doc.payment_policy === "Credito") {
					const creditAction = frm.doc.credit_approved
						? __("Revocar crédito")
						: __("Autorizar crédito");
					frm.add_custom_button(creditAction, () => {
						frappe.prompt(
							[
								{
									fieldname: "reason",
									fieldtype: "Small Text",
									label: __("Motivo"),
									reqd: 1,
								},
							],
							async (values) => {
								await frappe.xcall(
									"gym_management.api.memberships.approve_credit",
									{
										name: frm.doc.name,
										reason: values.reason,
										approved: frm.doc.credit_approved ? 0 : 1,
									}
								);
								await frm.reload_doc();
							},
							creditAction
						);
					});
				}
				if (capabilities.can_record_payment) {
					frm.add_custom_button(__("Registrar cobro"), () => {
						if (Number(capabilities.outstanding) <= 0) {
							frappe.msgprint(__("Esta membresía ya está pagada."));
							return;
						}
						const requestKey = frappe.utils.get_random(32);
						const dialog = new frappe.ui.Dialog({
							title: __("Registrar cobro recibido"),
							fields: [
								{
									fieldname: "amount",
									fieldtype: "Currency",
									label: __("Importe"),
									reqd: 1,
									default: capabilities.outstanding,
								},
								{
									fieldname: "payment_method",
									fieldtype: "Select",
									label: __("Forma de cobro"),
									options:
										"Transferencia\nTarjeta de crédito\nTarjeta de débito\nEfectivo",
									default: "Transferencia",
									reqd: 1,
								},
								{
									fieldname: "reference",
									fieldtype: "Data",
									label: __("Referencia del pago"),
									mandatory_depends_on: 'eval:doc.payment_method !== "Efectivo"',
									description: __(
										"Número de transferencia o comprobante de tarjeta."
									),
								},
								{
									fieldname: "cash_opening",
									fieldtype: "Select",
									label: __("Mi caja abierta"),
									options: [],
									depends_on: 'eval:doc.payment_method === "Efectivo"',
									mandatory_depends_on: 'eval:doc.payment_method === "Efectivo"',
									description: __(
										"Solo se muestra su caja de esta sucursal. Si no aparece, solicite al administrador que la abra desde Caja del gimnasio."
									),
								},
							],
							primary_action_label: __("Confirmar cobro"),
							async primary_action(values) {
								if (dialog._saving) return;
								dialog._saving = true;
								dialog.get_primary_btn().prop("disabled", true);
								try {
									await frappe.xcall(
										"facturada_lite.api.receipts.record_receipt",
										{
											payload: {
												...values,
												cash_opening:
													values.payment_method === "Efectivo"
														? values.cash_opening
														: null,
												business: frm.doc.business,
												source_doctype: "GYM Membership",
												source_name: frm.doc.name,
												request_key: requestKey,
											},
										}
									);
									dialog.hide();
									await frm.reload_doc();
								} finally {
									dialog._saving = false;
									dialog.get_primary_btn().prop("disabled", false);
								}
							},
						});
						dialog.fields_dict.payment_method.df.onchange = async () => {
							if (dialog.get_value("payment_method") !== "Efectivo") return;
							await dialog.set_value("cash_opening", "");
							const data = await frappe.xcall(
								"gym_management.api.cash.get_cash_context",
								{ business: frm.doc.business, branch: frm.doc.origin_branch }
							);
							const opening = data.opening;
							dialog.set_df_property(
								"cash_opening",
								"options",
								opening
									? [
											{
												label: __("Mi caja · fondo {0}", [
													format_currency(opening.opening_amount, "USD"),
												]),
												value: opening.name,
											},
									  ]
									: []
							);
							if (opening && dialog.get_value("payment_method") === "Efectivo")
								await dialog.set_value("cash_opening", opening.name);
						};
						dialog.show();
					});
					frm.add_custom_button(__("Historial de cobros"), async () => {
						const rows = await frappe.xcall(
							"facturada_lite.api.receipts.list_receipts",
							{
								business: frm.doc.business,
								source_doctype: "GYM Membership",
								source_name: frm.doc.name,
							}
						);
						const dialog = new frappe.ui.Dialog({
							title: __("Cobros"),
							fields: [
								{
									fieldname: "receipts",
									fieldtype: "Table",
									read_only: 1,
									data: rows.map((row) => ({
										...row,
										status_label:
											row.docstatus === 1
												? __("Confirmado")
												: row.docstatus === 2
												? __("Anulado")
												: __("Borrador"),
									})),
									fields: [
										{
											fieldname: "name",
											fieldtype: "Data",
											label: __("Recibo"),
											in_list_view: 1,
										},
										{
											fieldname: "amount",
											fieldtype: "Currency",
											label: __("Importe"),
											in_list_view: 1,
										},
										{
											fieldname: "payment_method",
											fieldtype: "Data",
											label: __("Forma"),
											in_list_view: 1,
										},
										{
											fieldname: "status_label",
											fieldtype: "Data",
											label: __("Estado"),
											in_list_view: 1,
										},
									],
								},
							],
						});
						dialog.show();
						if (
							capabilities.can_cancel_payment &&
							rows.some((row) => row.docstatus === 1)
						) {
							dialog.set_secondary_action_label(__("Anular cobro"));
							dialog.set_secondary_action(() =>
								frappe.prompt(
									[
										{
											fieldname: "name",
											fieldtype: "Select",
											options: rows
												.filter((row) => row.docstatus === 1)
												.map((row) => row.name),
											label: __("Cobro"),
											reqd: 1,
										},
										{
											fieldname: "reason",
											fieldtype: "Small Text",
											label: __("Motivo"),
											reqd: 1,
										},
									],
									async (values) => {
										await frappe.xcall(
											"facturada_lite.api.receipts.cancel_receipt",
											values
										);
										dialog.hide();
										await frm.reload_doc();
									}
								)
							);
						}
					});
				}
				frm.add_custom_button(__("Consultar saldo"), async () => {
					const balance = await frappe.xcall(
						"gym_management.api.memberships.get_membership_summary",
						{ name: frm.doc.name }
					);
					frappe.msgprint(
						__("Pagado: {0}. Pendiente: {1}", [
							format_currency(balance.paid, "USD"),
							format_currency(balance.outstanding, "USD"),
						])
					);
				});
				frm.add_custom_button(__("Renovar"), () => {
					frappe.new_doc("GYM Membership", {
						business: frm.doc.business,
						origin_branch: frm.doc.origin_branch,
						member: frm.doc.member,
						plan: frm.doc.plan,
						previous_membership: frm.doc.name,
						start_date:
							frm.doc.end_date >= frappe.datetime.get_today()
								? frappe.datetime.add_days(frm.doc.end_date, 1)
								: frappe.datetime.get_today(),
					});
				});
			}
		},
		before_load(frm) {
			frm._gym_business = frm.doc.business;
		},
		business(frm) {
			if (!frm.is_new() || frm._gym_business === frm.doc.business) return;
			frm._gym_business = frm.doc.business;
			for (const field of [
				"member",
				"plan",
				"origin_branch",
				"branch",
				"previous_membership",
			]) {
				if (frappe.meta.get_docfield(doctype, field)) frm.set_value(field, null);
			}
		},
		async plan(frm) {
			if (
				doctype !== "GYM Membership" ||
				(!frm.is_new() && frm.doc.docstatus !== 0) ||
				!frm.doc.plan
			)
				return;
			const name = frm.doc.plan;
			const plan = await frappe.db.get_doc("GYM Membership Plan", name);
			if (frm.doc.plan !== name) return;
			for (const field of [
				"duration",
				"duration_unit",
				"price",
				"currency",
				"access_mode",
				"renewal_mode",
				"payment_policy",
				"minimum_percentage",
				"grace_days",
			]) {
				await frm.set_value(field, plan[field]);
			}
			await frm.set_value(
				"branches",
				(plan.branches || []).map((row) => ({ branch: row.branch }))
			);
		},
	});
}
