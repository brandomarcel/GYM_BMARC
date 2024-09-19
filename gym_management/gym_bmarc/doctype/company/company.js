// Copyright (c) 2024, S/N and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Company", {
// 	refresh(frm) {

// 	},
// });

// Evento sobre el Doctype principal (Company)
frappe.ui.form.on('Company', {
    refresh: function (frm) {
        console.log('Formulario Company refrescado.');
    },

    // Evento cuando se añade una nueva fila a la tabla planes_contratados_id
    planes_contratados_id_add: function (frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        console.log('Nueva fila añadida a planes_contratados_id:', row);
    }
});

// Evento específico en el campo 'plan_id' dentro de la tabla 'planes_contratados_id'
frappe.ui.form.on('Planes Contratados', {
    plan_id: function (frm, cdt, cdn) {
        var row = locals[cdt][cdn];  // Obtiene la fila actual de la tabla secundaria

        if (row.plan_id) {
            console.log('Plan seleccionado:', row.plan_id);

            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Planes',  // Asegúrate de que este sea el Doctype correcto
                    name: row.plan_id   // El valor seleccionado en el campo 'plan_id'
                },
                callback: function (r) {
                    if (!r.exc && r.message) {
                        console.log('Datos del Plan:', r.message);
                        console.log('date_ini:', row.date_ini);
                        console.log('time_month:', r.message.time_month);

                        // Asigna el precio del plan obtenido a la fila actual
                        frappe.model.set_value(cdt, cdn, 'cost', r.message.cost);
                        console.log('Precio asignado:', r.message.cost);
                        var fecha_inicio = frappe.datetime.add_months(row.date_ini, r.message.time_month);
                        console.log('fecha_inicio:', fecha_inicio);
                        // Establecer la nueva fecha fin un mes después
                        frappe.model.set_value(cdt, cdn, 'date_fin', fecha_inicio);
                    } else {
                        frappe.msgprint(__('No se encontró el plan o no tiene un precio asignado.'));
                    }
                },
                error: function (err) {
                    console.error('Error al obtener el plan:', err);
                    frappe.msgprint(__('Hubo un error al obtener el plan.'));
                }
            });
        } else {
            frappe.msgprint(__('Por favor, selecciona un plan.'));
        }
    },
});

frappe.ui.form.on('Membership_Type', {
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


