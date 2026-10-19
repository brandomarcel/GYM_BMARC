/* global gym */
for (const doctype of ["GYM Branch", "GYM Branch User", "GYM Member"]) {
	frappe.ui.form.on(doctype, {
		setup(frm) {
			// Core links use authorized GYM searches; their generic read/select API
			// is intentionally unavailable to reception. Controllers revalidate all links.
			for (const field of ["business", "establishment", "user"]) {
				const df = frappe.meta.get_docfield(doctype, field);
				if (df) df.ignore_link_validation = true;
				if (frappe.meta.get_docfield(doctype, field, frm.doc.name)) {
					frm.set_df_property(field, "ignore_link_validation", true);
				}
			}
			frm.set_query("business", () => ({
				query: "gym_management.api.context.business_query",
			}));
			const branchField = doctype === "GYM Member" ? "home_branch" : "branch";
			if (doctype !== "GYM Branch") {
				frm.set_query(branchField, () => ({
					filters: { business: frm.doc.business, status: "Activo" },
				}));
			}
			for (const field of ["establishment", "user"]) {
				if (frm.fields_dict[field]) {
					frm.set_query(field, () => ({
						query: "gym_management.api.context.business_link_query",
						filters: { business: frm.doc.business },
					}));
				}
			}
		},
		async refresh(frm) {
			await gym.desk.defaults(frm);
			if (doctype !== "GYM Member") return;
			if (frm.is_new()) {
				frm.set_intro(
					__("Complete los datos del socio y guarde. Después podrá crear su membresía.")
				);
				return;
			}
			frm.add_custom_button(__("Ver membresías"), () =>
				frappe.set_route("List", "GYM Membership", {
					business: frm.doc.business,
					member: frm.doc.name,
				})
			);
			if (frm.doc.status === "Activo")
				frm.add_custom_button(__("Crear membresía"), () =>
					frappe.new_doc("GYM Membership", {
						business: frm.doc.business,
						origin_branch: frm.doc.home_branch,
						member: frm.doc.name,
						start_date: frappe.datetime.get_today(),
					})
				);
		},
		business(frm) {
			if (!frm.is_new()) return;
			for (const field of ["home_branch", "branch", "establishment", "user"]) {
				if (frm.fields_dict[field]) frm.set_value(field, null);
			}
		},
	});
}
