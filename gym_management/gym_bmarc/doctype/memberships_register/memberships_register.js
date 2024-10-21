var planOriginal = '';

frappe.ui.form.on("memberships_register", {
    refresh(frm) {
        console.log(frm.is_new);
        if (frm.is_new()) {
            frm.fields_dict['recibo_html'].html(null);
        }
        // Si el documento no es nuevo y tiene un plan seleccionado, cargamos el plan original
        if (!frm.is_new() && frm.doc.plan) {
            // Agregar botón personalizado con ícono y color de WhatsApp
            frm.add_custom_button(__('Enviar por WhatsApp'), function () {
                // Formatear el mensaje a enviar
                let mensaje = `
            ${frm.doc.recibo_info}
            `;

                // Número de teléfono (reemplazar por uno dinámico si es necesario)
                let numero_telefono = `${frm.doc.phone}`; // Formato internacional (sin '+', guiones o espacios)

                // Codificar el mensaje para URL
                let url = `https://wa.me/+593${numero_telefono}?text=${encodeURIComponent(mensaje)}`;

                // Abrir la URL en una nueva pestaña
                window.open(url);
            }, 'fa fa-whatsapp').css({
                'background-color': '#25D366', // Color verde de WhatsApp
                'color': 'white',              // Texto en blanco
                'border-color': '#25D366'      // Borde verde de WhatsApp
            });
            let recibo_html = `
    <div style="
        border: 2px solid #25D366; 
        padding: 15px; 
        background-color: #f9f9f9; 
        border-radius: 10px;
        margin-top: 10px;
    ">
    <p><strong>RESUMEN</strong></p>
        <p><strong>Servicio Contratado:</strong> ${frm.doc.nombre_plan}</p>
        <p><strong>Inicio:</strong> ${frm.doc.date_ini}</p>
        <p><strong>Caduca:</strong> ${frm.doc.date_fin}</p>
        <p><strong>Costo de Plan:</strong> $${frm.doc.cost} Dolares</p>
        <p><strong>Descuento:</strong> $${frm.doc.discount || 0.00} Dolares</p>
        <p><strong>Total Pagado:</strong> $${frm.doc.total} Dolares</p>
        <p><strong>Cajero:</strong> ${frm.doc.owner}</p>
        <p>Gracias por preferirnos.</p>
    </div>
`;

            // Asignar el contenido HTML al campo 'recibo_html'
            frm.fields_dict['recibo_html'].html(recibo_html);
            console.log('no es nuevo');
            loadPlanOriginal(frm);
        }
    },

    validate: function (frm) {
        // Formatear el contenido del recibo usando datos del formulario
        let recibo_info = `
        Servicio Contratado: ${frm.doc.nombre_plan}
        Inicio: ${frm.doc.date_ini}
        Caduca: ${frm.doc.date_fin}
        Costo de Plan: $${frm.doc.cost} Dolares
        Descuento: $${frm.doc.discount || 0.00} Dolares
        Total Pagado: $${frm.doc.total} Dolares
        Cajero: ${frm.doc.owner}
        Gracias por preferirnos.
    `;

        // Guardar la información del recibo en el campo 'recibo_info'
        frm.set_value('recibo_info', recibo_info);
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

        if (frm.doc.discount == 0) {
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
