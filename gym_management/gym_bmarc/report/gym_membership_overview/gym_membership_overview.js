frappe.query_reports["GYM Membership Overview"] = {
	filters: [
		{ fieldname: "business", label: __("Negocio"), fieldtype: "Link", options: "FacturADA Business", reqd: 1,
			ignore_link_validation: true, get_query: () => ({ query: "gym_management.api.context.business_query" }) },
		{ fieldname: "branch", label: __("Sucursal"), fieldtype: "Link", options: "GYM Branch",
			get_query: () => ({ filters: { business: frappe.query_report.get_filter_value("business") } }) },
	],
};
