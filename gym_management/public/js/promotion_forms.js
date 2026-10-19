frappe.ui.form.on("GYM Promotion", {
	refresh(frm) {
		frm.set_intro(
			__(
				"Esta promoción aplica un descuento individual. No vincula socios ni implementa un 2×1 grupal."
			)
		);
	},
	setup(frm) {
		frappe.meta.get_docfield("GYM Promotion", "business").ignore_link_validation = true;
		frm.set_df_property("business", "ignore_link_validation", true);
		frm.set_query("business", () => ({ query: "gym_management.api.context.business_query" }));
		frm.set_query("plan", () => ({
			filters: { business: frm.doc.business, status: "Activo" },
		}));
	},
});

frappe.ui.form.on("GYM Membership", {
	setup(frm) {
		frm.set_query("promotion", () => ({
			filters: {
				business: frm.doc.business,
				plan: frm.doc.plan,
				status: "Activo",
				valid_from: ["<=", frappe.datetime.get_today()],
				valid_until: [">=", frappe.datetime.get_today()],
			},
		}));
	},
	plan(frm) {
		if (frm.doc.docstatus === 0) frm.set_value("promotion", null);
	},
	business(frm) {
		if (frm.doc.docstatus === 0) frm.set_value("promotion", null);
	},
	async promotion(frm) {
		if (frm.doc.docstatus !== 0) return;
		await frm.set_value("promotion_snapshot", null);
		await frm.set_value("discount", 0);
		await frm.set_value("discount_reason", "");
		if (!frm.doc.plan || !frm.doc.origin_branch) return;
		const selection = {
			business: frm.doc.business,
			plan: frm.doc.plan,
			origin_branch: frm.doc.origin_branch,
			promotion: frm.doc.promotion || null,
		};
		const quote = await frappe.xcall("gym_management.api.promotions.quote_price", selection);
		if (Object.entries(selection).some(([key, value]) => (frm.doc[key] || null) !== value))
			return;
		for (const field of ["price", "discount", "discount_reason", "total"]) {
			await frm.set_value(field, quote[field]);
		}
	},
});
