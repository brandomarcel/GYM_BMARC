frappe.ui.form.on("GYM Billing Request", {
	async refresh(frm) {
		if (frm.is_new() || !frm.doc.invoice) return;
		const context = await frappe.xcall("facturada_lite.api.receipt_applications.get_context", {
			invoice: frm.doc.invoice,
		});
		frm.dashboard.add_indicator(
			__("Aplicado: {0}", [format_currency(context.summary.total_collected, "USD")]),
			"green"
		);
		frm.dashboard.add_indicator(
			__("Pendiente: {0}", [format_currency(context.summary.outstanding_amount, "USD")]),
			"orange"
		);
		const available = context.receipts.filter((row) => row.available > 0);
		if (context.can_apply && available.length && context.summary.outstanding_amount > 0) {
			frm.add_custom_button(__("Aplicar recibo"), () => {
				const requestKey = frappe.utils.get_random(32);
				let dialog;
				dialog = new frappe.ui.Dialog({
					title: __("Aplicar un recibo existente"),
					fields: [
						{
							fieldname: "explanation",
							fieldtype: "HTML",
							options: `<p>${__(
								"Esta acción asigna dinero ya recibido a la factura. No registra otro cobro."
							)}</p>`,
						},
						{
							fieldname: "receipt",
							fieldtype: "Select",
							label: __("Recibo"),
							options: available.map((row) => ({
								value: row.name,
								label: `${row.name} · ${row.payment_method} · ${format_currency(
									row.available,
									"USD"
								)}`,
							})),
							reqd: 1,
							onchange() {
								if (!dialog) return;
								const row = available.find(
									(item) => item.name === dialog.get_value("receipt")
								);
								if (row)
									dialog.set_value(
										"amount",
										Math.min(row.available, context.summary.outstanding_amount)
									);
							},
						},
						{
							fieldname: "amount",
							fieldtype: "Currency",
							label: __("Importe a aplicar"),
							default: Math.min(
								available[0].available,
								context.summary.outstanding_amount
							),
							reqd: 1,
						},
					],
					primary_action_label: __("Confirmar aplicación"),
					async primary_action(values) {
						dialog.get_primary_btn().prop("disabled", true);
						try {
							await frappe.xcall(
								"facturada_lite.api.receipt_applications.apply_receipt",
								{
									payload: {
										...values,
										invoice: frm.doc.invoice,
										request_key: requestKey,
									},
								}
							);
							dialog.hide();
							await frm.reload_doc();
						} finally {
							dialog.get_primary_btn().prop("disabled", false);
						}
					},
				});
				dialog.show();
			});
		}
		frm.add_custom_button(__("Historial de aplicaciones"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Aplicaciones y reversos"),
				fields: [
					{
						fieldname: "applications",
						fieldtype: "Table",
						read_only: 1,
						data: context.applications.map((row) => ({
							...row,
							status_label:
								row.docstatus === 1
									? __("Confirmada")
									: row.docstatus === 2
									? __("Reversada")
									: __("Borrador"),
						})),
						fields: [
							{
								fieldname: "name",
								fieldtype: "Data",
								label: __("Aplicación"),
								in_list_view: 1,
							},
							{
								fieldname: "receipt",
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
			const active = context.applications.filter((row) => row.docstatus === 1);
			if (context.can_reverse && active.length) {
				dialog.set_secondary_action_label(__("Reversar aplicación"));
				dialog.set_secondary_action(() =>
					frappe.prompt(
						[
							{
								fieldname: "name",
								fieldtype: "Select",
								label: __("Aplicación"),
								options: active.map((row) => row.name),
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
								"facturada_lite.api.receipt_applications.reverse_application",
								values
							);
							dialog.hide();
							await frm.reload_doc();
						}
					)
				);
			}
		});
	},
});
