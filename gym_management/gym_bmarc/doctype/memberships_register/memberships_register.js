var planOriginal = '';

frappe.ui.form.on("memberships_register", {
    refresh(frm) {
        console.log(frm.is_new);
        $(frm.fields_dict.discount.wrapper).find('.help-box').css({
            'color': 'blue',            // Cambiar el color del texto a azul
            'font-size': '14px',         // Ajustar el tamaño de la fuente
            'font-weight': 'bold',       // Hacer el texto negrita
            'background-color': '#f0f8ff', // Fondo suave
            'padding': '5px',            // Espacio interno (padding)
            'border-radius': '5px'       // Bordes redondeados
        });

        // Si el documento no es nuevo y tiene un plan seleccionado, cargamos el plan original
        if (!frm.is_new() && frm.doc.plan) {
            console.log('no es nuevo');
            loadPlanOriginal(frm);
        }
    },
    plan: function (frm) {
        console.log('frm', frm);

        if (frm.doc.plan) {
            frm.set_value('discount', '');
            console.log('Plan seleccionado:', frm.doc.plan);

            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Membership_Type',  // Asegúrate de que este sea el Doctype correcto
                    name: frm.doc.plan   // El valor seleccionado en el campo 'plan'
                },
                callback: function (r) {
                    if (!r.exc && r.message) {
                        console.log('Datos del Plan:', r.message);
                        console.log('date_ini:', frm.doc.date_ini);
                        console.log('time_month:', r.message.time_month);
                        planOriginal = r.message;

                        // Asigna el precio del plan obtenido a la fila actual
                        // frappe.model.set_value(cdt, cdn, 'cost', r.message.cost);
                        // console.log('Precio asignado:', r.message.cost);
                        var date_fin = frappe.datetime.add_months(frm.doc.date_ini, r.message.time_month);
                        console.log('date_fin:', date_fin);
                        // Establecer la nueva fecha fin un mes después
                        frm.set_value('date_fin', date_fin);
                        frm.set_value('total', r.message.total);
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
    discount: function (frm) {
        console.log('plan', frm.doc);
        console.log('planOriginal', planOriginal);

        if (frm.doc.plan && frm.doc.discount > frm.doc.cost) {
            frappe.msgprint(__('El descuento no puede ser mayor que el costo del plan.'));
            frm.set_value('discount', 0); // Reinicia el descuento si es mayor
            frm.set_value('total', planOriginal.total);
        } else {
            var valTotal = planOriginal.total - frm.doc.discount;
            frm.set_value('total', valTotal);
        }

        if (frm.doc.discount == 0 ) {
            console.log('entro discount 0');
            frm.set_value('total', planOriginal.total);
        }
    }
});

// Función para cargar el plan original cuando el documento está en modo de edición
function loadPlanOriginal(frm) {
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Membership_Type',  // Asegúrate de que este sea el Doctype correcto
            name: frm.doc.plan           // El valor seleccionado en el campo 'plan'
        },
        callback: function (r) {
            if (!r.exc && r.message) {
                console.log('Cargando plan original:', r.message);
                planOriginal = r.message;
            } else {
                frappe.msgprint(__('No se encontró el plan o no tiene un precio asignado.'));
            }
        },
        error: function (err) {
            console.error('Error al obtener el plan original:', err);
            frappe.msgprint(__('Hubo un error al obtener el plan original.'));
        }
    });
}
