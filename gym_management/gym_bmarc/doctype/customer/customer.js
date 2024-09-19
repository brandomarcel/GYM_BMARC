// Copyright (c) 2024, S/N and contributors
// For license information, please see license.txt

frappe.ui.form.on('Customer', {
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
    validate: function(frm) {
        const phone = frm.doc.phone;
        const phone_regex = /^\d{10}$/;
        if (!phone_regex.test(phone)) {
            frappe.msgprint(__('El número de teléfono debe tener exactamente 10 dígitos.'));
            frappe.validated = false;
        }
    }
});






frappe.ui.form.on('memberships_acquired', {
    plan: function (frm, cdt, cdn) {
        var row = locals[cdt][cdn];  // Obtiene la fila actual de la tabla secundaria

        if (row.plan) {
            console.log('Plan seleccionado:', row.plan);

            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Membership_Type',  // Asegúrate de que este sea el Doctype correcto
                    name: row.plan   // El valor seleccionado en el campo 'plan'
                },
                callback: function (r) {
                    if (!r.exc && r.message) {
                        console.log('Datos del Plan:', r.message);
                        console.log('date_ini:', row.date_ini);
                        console.log('time_month:', r.message.time_month);

                        // Asigna el precio del plan obtenido a la fila actual
                        // frappe.model.set_value(cdt, cdn, 'cost', r.message.cost);
                        // console.log('Precio asignado:', r.message.cost);
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

    date_ini: function (frm, cdt, cdn) {
        var row = locals[cdt][cdn];  // Obtiene la fila actual de la tabla secundaria

        if (row.plan) {
            console.log('Plan seleccionado:', row.plan);

            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Membership_Type',  // Asegúrate de que este sea el Doctype correcto
                    name: row.plan   // El valor seleccionado en el campo 'plan'
                },
                callback: function (r) {
                    if (!r.exc && r.message) {
                        console.log('Datos del Plan:', r.message);
                        console.log('date_ini:', row.date_ini);
                        console.log('time_month:', r.message.time_month);

                        // Asigna el precio del plan obtenido a la fila actual
                        // frappe.model.set_value(cdt, cdn, 'cost', r.message.cost);
                        // console.log('Precio asignado:', r.message.cost);
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