frappe.ui.form.on("GYM Membership", {
	async refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		const context = await frappe.xcall(
			"gym_management.api.memberships.get_membership_summary",
			{ name: frm.doc.name }
		);
		if (context.billing_request) {
			frm.add_custom_button(__("Solicitud fiscal"), () =>
				frappe.set_route("Form", "GYM Billing Request", context.billing_request)
			);
			return;
		}
		if (!context.can_prepare_invoice) return;
		frm.add_custom_button(__("Preparar borrador fiscal"), () => {
			const requestKey = frappe.utils.get_random(32);
			const query = () => ({
				query: "gym_management.api.invoicing.billing_link_query",
				filters: { membership: frm.doc.name },
			});
			const dialog = new frappe.ui.Dialog({
				title: __("Preparar borrador fiscal"),
				fields: [
					{
						fieldname: "explanation",
						fieldtype: "HTML",
						options: `<p>${__(
							"Seleccione el pagador y el servicio fiscal. El total debe coincidir con el contrato. Este paso no cobra ni emite al SRI."
						)}</p>`,
					},
					{
						fieldname: "customer",
						fieldtype: "Link",
						options: "FacturADA Lite Customer",
						label: __("Cliente fiscal / pagador"),
						reqd: 1,
						get_query: query,
						ignore_link_validation: true,
					},
					{
						fieldname: "service",
						fieldtype: "Link",
						options: "FacturADA Lite Item",
						label: __("Servicio"),
						reqd: 1,
						get_query: query,
						ignore_link_validation: true,
					},
					{
						fieldname: "pos_terminal",
						fieldtype: "Link",
						options: "FacturADA POS Terminal",
						label: __("Terminal fiscal de la sede"),
						reqd: 1,
						get_query: query,
						ignore_link_validation: true,
					},
					{
						fieldname: "price_basis",
						fieldtype: "Select",
						label: __("El precio contratado tiene"),
						options: "\nImpuestos incluidos\nImpuestos no incluidos",
						reqd: 1,
					},
				],
				primary_action_label: __("Crear borrador"),
				async primary_action(values) {
					dialog.get_primary_btn().prop("disabled", true);
					try {
						const selections = { membership: frm.doc.name, ...values };
						const preview = await frappe.xcall(
							"gym_management.api.invoicing.preview_billing",
							selections
						);
						if (!preview.ready) {
							frappe.msgprint(preview.message);
							return;
						}
						const result = await frappe.xcall(
							"gym_management.api.invoicing.prepare_billing_request",
							{ payload: { ...selections, request_key: requestKey } }
						);
						dialog.hide();
						frappe.set_route("Form", "GYM Billing Request", result.name);
					} finally {
						dialog.get_primary_btn().prop("disabled", false);
					}
				},
			});
			dialog.show();
		});
	},
});

frappe.ui.form.on("GYM Billing Request", {
	setup(frm) {
		for (const field of ["business", "prepared_by"]) {
			frappe.meta.get_docfield("GYM Billing Request", field).ignore_link_validation = true;
			frm.set_df_property(field, "ignore_link_validation", true);
		}
	},
	refresh(frm) {
		frm.disable_save();
		if (frm.is_new()) {
			frm.dashboard.set_headline(__("Prepare la solicitud desde una membresía confirmada."));
			return;
		}
		frm.dashboard.set_headline(
			__(
				"Borrador fiscal preparado. Aplique sus recibos y revise las condiciones antes de emitir."
			)
		);
		if (frm.doc.invoice) {
			frm.add_custom_button(__("Ver borrador Lite"), () =>
				frappe.set_route("Form", "FacturADA Lite Invoice", frm.doc.invoice)
			);
		}
	},
});
