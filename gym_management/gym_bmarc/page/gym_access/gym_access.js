frappe.pages["gym-access"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Control de acceso"),
		single_column: true,
	});
	const container = document.createElement("div");
	container.className = "p-4";
	page.body.append(container);
	const makeField = (label, element, id) => {
		const group = document.createElement("div");
		group.className = "form-group";
		const caption = document.createElement("label");
		element.id = id;
		caption.htmlFor = id;
		caption.textContent = label;
		group.append(caption, element);
		container.append(group);
		element.className = "form-control";
		return element;
	};
	const business = makeField(
		__("Negocio"),
		document.createElement("select"),
		"gym-access-business"
	);
	const branch = makeField(
		__("Sucursal"),
		document.createElement("select"),
		"gym-access-branch"
	);
	const code = makeField(
		__("Código de socio"),
		document.createElement("input"),
		"gym-access-code"
	);
	const button = document.createElement("button");
	button.className = "btn btn-primary";
	button.textContent = __("Registrar ingreso");
	const result = document.createElement("p");
	result.className = "mt-3";
	result.setAttribute("role", "status");
	container.append(button, result);
	let context = { businesses: [], branches: [] };
	let requestKey = null;
	const reset = () => {
		requestKey = null;
		result.textContent = "";
	};
	const fillBranches = () => {
		branch.replaceChildren(new Option(__("Seleccione una sucursal"), ""));
		for (const row of context.branches.filter(
			(row) => row.business === business.value && row.status === "Activo"
		)) {
			branch.add(new Option(row.branch_name, row.name));
		}
		if (branch.options.length === 2) branch.selectedIndex = 1;
		reset();
	};
	business.addEventListener("change", fillBranches);
	branch.addEventListener("change", reset);
	code.addEventListener("input", reset);
	code.addEventListener("keydown", (event) => {
		if (event.key === "Enter" && !button.disabled) {
			event.preventDefault();
			button.click();
		}
	});
	button.addEventListener("click", async () => {
		if (!business.value || !branch.value || !code.value.trim()) {
			frappe.msgprint(__("Seleccione negocio y sucursal e indique el código del socio."));
			return;
		}
		button.disabled = true;
		business.disabled = branch.disabled = code.disabled = true;
		try {
			const member = await frappe.xcall(
				"gym_management.api.memberships.find_access_member",
				{ business: business.value, branch: branch.value, member_code: code.value }
			);
			requestKey = requestKey || frappe.utils.get_random(32);
			const response = await frappe.xcall(
				"gym_management.api.memberships.record_attendance",
				{
					business: business.value,
					branch: branch.value,
					member: member.name,
					request_key: requestKey,
				}
			);
			result.textContent = `${member.full_name}: ${__(response.result)} — ${__(
				response.reason
			)}`;
			result.className =
				response.result === "Permitido" ? "mt-3 text-success" : "mt-3 text-danger";
			// A successful, completed entry can be followed by another intentional entry.
			code.value = "";
			requestKey = null;
		} catch {
			result.textContent = __(
				"No se pudo registrar el ingreso. Revise los datos y vuelva a intentar."
			);
			result.className = "mt-3 text-danger";
		} finally {
			button.disabled = false;
			business.disabled = branch.disabled = code.disabled = false;
			code.focus();
		}
	});
	frappe
		.xcall("gym_management.api.context.get_context")
		.then((data) => {
			context = data;
			business.add(new Option(__("Seleccione un negocio"), ""));
			for (const row of context.businesses)
				business.add(new Option(row.business_name, row.name));
			if (context.businesses.length === 1) business.selectedIndex = 1;
			fillBranches();
			code.focus();
		})
		.catch(() => {
			result.textContent = __("No se pudo cargar su contexto. Actualice la página.");
		});
};
