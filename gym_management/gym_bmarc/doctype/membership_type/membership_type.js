// Copyright (c) 2024, S/N and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Membership_Type", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on('Membership_Type', {
    before_insert: function(frm) {
        if (!frm.doc.company) {
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "User",
                    filters: {
                        'name': frappe.session.user
                    },
                    fieldname: "default_company"
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value("company", r.message.default_company);
                    }
                }
            });
        }
    },
    cost: function(frm, cdt, cdn) {
        calculate_total(frm, cdt, cdn);
    },
    iva: function(frm, cdt, cdn) {
        calculate_total(frm, cdt, cdn);
    }

});

// Función para calcular el total
function calculate_total(frm, cdt, cdn) {
    var row = locals[cdt][cdn];  // Obtiene la fila actual de la tabla secundaria
    if (row.cost && (row.iva || row.iva === 0)) {
        var total = row.cost + (row.cost * (row.iva / 100));  // Calcula el total
        
        // Establece el valor del total en la fila actual
        frappe.model.set_value(cdt, cdn, 'total', total);
    }
}
