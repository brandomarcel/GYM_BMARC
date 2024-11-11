frappe.ui.form.on('Customer', {
    refresh(frm) {
        frm.fields_dict['qr_code_html'].wrapper.innerHTML = ``;

        if (frm.doc.qr_code) {
            // frm.add_custom_button(__('Enviar QR por WhatsApp'), function() {
            //     sendQRCodeViaWhatsApp(frm);
            // });
            frm.fields_dict['qr_code_html'].wrapper.innerHTML = `
                <img src="${frm.doc.qr_code}" alt="Código QR" id="qr_image" style="margin-right: 10px;">
                
            `;

        }
    },
    
    after_save(frm) {
        if (!frm.doc.qr_code) {
            generateQRCode(frm);
        }
    },
});

async function generateQRCode(frm) {
    try {
        const data = `${frm.doc.name}` || "Texto de Ejemplo";
        const qrApiUrl = `https://api.qrserver.com/v1/create-qr-code/?data=${encodeURIComponent(data)}&size=150x150&format=png`;

        const response = await fetch(qrApiUrl);
        const blob = await response.blob();
        const reader = new FileReader();

        reader.onload = async function () {
            frm.set_value('qr_code', reader.result);
            frm.refresh_field('qr_code');

            frm.fields_dict['qr_code_html'].wrapper.innerHTML = `
                <img src="${frm.doc.qr_code}" alt="Código QR" id="qr_image" style="margin-right: 10px;">
                <button class="btn btn-primary btn-sm" id="copy_qr_button">Copiar Imagen</button>
            `;
            
            document.getElementById("copy_qr_button").addEventListener("click", copyQRCodeURL);
            await frm.save();
        };

        reader.readAsDataURL(blob);
    } catch (error) {
        console.error("Error al generar el QR:", error);
    }
}


// Función para enviar el QR por WhatsApp
function sendQRCodeViaWhatsApp(frm) {
    const phone_number = frm.doc.phone;
    if (!phone_number) {
        frappe.msgprint(__('Por favor, ingresa un número de teléfono para enviar el QR.'));
        return;
    }

    const message = `Hola, aquí está el código QR que solicitaste: ${frm.doc.qr_code}`;
    const encodedMessage = encodeURIComponent(message);
    const whatsappUrl = `https://wa.me/+593${phone_number}?text=${encodedMessage}`;

    window.open(whatsappUrl, '_blank');
}
