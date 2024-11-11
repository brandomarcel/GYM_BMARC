frappe.query_reports["Membresias Registradas"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": "Compañía",
            "fieldtype": "Link",
            "options": "Company",
            "default": "Compañía Predeterminada"  // Valor predeterminado provisional
        },
        {
            "fieldname": "status",
            "label": "Estado",
            "fieldtype": "Select",
            "options": ['Todos', 'Activo', 'Inactivo'],
            "default": 'Todos' 
        }
    ],

    // Usamos onload para obtener y establecer la compañía predeterminada
    onload: function(report) {

        frappe.call({
            method: "frappe.client.get_value",
            args: {
                doctype: "User Permission",
                filters: { user: frappe.session.user },
                fieldname: "for_value"
            },
            callback: function(response) {
                
                if (response.message && response.message.for_value) {
                    const company = response.message.for_value;
                    report.set_filter_value("company", company);  // Establecer el valor predeterminado de la compañía
                    
                }
            }
        });
    }
};
