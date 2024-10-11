// Copyright (c) 2024, S/N and contributors
// For license information, please see license.txt
frappe.query_reports["Membresias Registradas"] = {
	
    "filters": [
        {
            "fieldname": "company",
            "label": "Compañía",
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("for_value") || "Compañía Predeterminada"  // Si no hay compañía configurada, usa una compañía por defecto
        },
		{
            "fieldname": "status",
            "label": "Estado",
            "fieldtype": "Select",
            "options": ['Todos','Activo','Inactivo'],
            "default": 'Todos' 
        }
    ]
};
