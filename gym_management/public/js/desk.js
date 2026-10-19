/* global gym */
/* Shared Desk presentation helpers. Server permissions remain authoritative. */
frappe.provide("gym.desk");
gym.desk.text = (parent, tag, text, className = "") => {
	const node = document.createElement(tag);
	node.textContent = text;
	node.className = className;
	parent.append(node);
	return node;
};
gym.desk.button = (parent, label, action, primary = false) => {
	const button = gym.desk.text(
		parent,
		"button",
		label,
		`btn btn-${primary ? "primary" : "default"} mr-2 mb-2`
	);
	button.type = "button";
	button.addEventListener("click", action);
	return button;
};
gym.desk.selector = (parent, label, name) => {
	const group = document.createElement("div");
	group.className = "form-group";
	parent.append(group);
	const caption = gym.desk.text(group, "label", label);
	const select = document.createElement("select");
	select.id = `gym-${name}`;
	caption.htmlFor = select.id;
	select.className = "form-control";
	group.append(select);
	return select;
};
gym.desk.fill = (select, rows, label, selected = "") => {
	select.replaceChildren(new Option(__("Seleccione una opción"), ""));
	for (const row of rows) select.add(new Option(row[label] || row.name, row.name));
	select.value = rows.some((row) => row.name === selected)
		? selected
		: rows.length === 1
		? rows[0].name
		: "";
};
gym.desk.defaults = async (frm) => {
	if (!frm.is_new() || frm._gym_defaults_loading) return;
	frm._gym_defaults_loading = true;
	try {
		const context = await frappe.xcall("gym_management.api.context.get_context");
		if (!frm.is_new()) return;
		if (!frm.doc.business && context.businesses.length === 1)
			await frm.set_value("business", context.businesses[0].name);
		const branches = context.branches.filter(
			(row) => row.business === frm.doc.business && row.status === "Activo"
		);
		const field = ["home_branch", "origin_branch", "branch"].find(
			(name) => frm.fields_dict[name]
		);
		if (field && !frm.doc[field] && branches.length === 1)
			await frm.set_value(field, branches[0].name);
	} finally {
		frm._gym_defaults_loading = false;
	}
};
