frappe.ui.form.on("GYM Billing Request", {
	async refresh(frm) {
		if (frm.is_new() || !frm.doc.invoice) return;
		const context = await frappe.xcall("gym_management.api.invoicing.get_emission_context", {
			name: frm.doc.name,
		});
		frm.dashboard.add_indicator(__("Factura: {0}", [context.status]), "blue");
		if (context.document_number) {
			frm.dashboard.add_indicator(context.document_number, "blue");
		}
		if (context.can_query) {
			frm.add_custom_button(__("Consultar estado fiscal"), async () => {
				await frappe.xcall("gym_management.api.invoicing.query_billing_request", {
					name: frm.doc.name,
				});
				await frm.reload_doc();
			});
		}
		if (!context.can_emit) return;
		frm.add_custom_button(__("Emitir factura"), () => {
			const pending = context.summary.outstanding_amount;
			const dialog = new frappe.ui.Dialog({
				title: __("Confirmar emisión fiscal"),
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "summary",
						options: `<p>${frappe.utils.escape_html(
							__("Ambiente: {0}. Total: {1}. Saldo pendiente: {2}.", [
								context.environment,
								format_currency(frm.doc.invoice_total, "USD"),
								format_currency(pending, "USD"),
							])
						)}</p><p>${__(
							"Los recibos aplicados se incluirán automáticamente. Indique cómo se pagará el saldo; esto no registra un nuevo cobro."
						)}</p>`,
					},
					{
						fieldname: "future_payments",
						fieldtype: "Table",
						label: __("Condiciones del saldo pendiente"),
						hidden: pending <= 0,
						data: pending > 0 ? [{ amount: pending, credit_days: 0 }] : [],
						fields: [
							{
								fieldname: "payment_code",
								fieldtype: "Select",
								label: __("Forma fiscal"),
								options: ["", ...context.payment_codes],
								in_list_view: 1,
								reqd: 1,
							},
							{
								fieldname: "amount",
								fieldtype: "Currency",
								label: __("Importe USD"),
								in_list_view: 1,
								reqd: 1,
							},
							{
								fieldname: "credit_days",
								fieldtype: "Int",
								label: __("Plazo en días"),
								in_list_view: 1,
								default: 0,
							},
						],
					},
				],
				primary_action_label: __("Confirmar emisión"),
				async primary_action(values) {
					dialog.get_primary_btn().prop("disabled", true);
					try {
						await frappe.xcall("gym_management.api.invoicing.emit_billing_request", {
							name: frm.doc.name,
							future_payments: (values.future_payments || []).map((row) => ({
								payment_code: row.payment_code,
								amount: row.amount,
								credit_days: row.credit_days || 0,
							})),
						});
						dialog.hide();
					} finally {
						dialog.get_primary_btn().prop("disabled", false);
						await frm.reload_doc();
					}
				},
			});
			dialog.show();
		});
	},
});
