frappe.pages['prueba'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Prueba Membresia',
		single_column: true
	});
 // Añadir un contenedor donde se colocará la tabla de resultados
 $(page.body).append(`
	<div class="report-info-block">
		<h2>Resultados del Reporte</h2>
		<table id="report-table" style="width: 100%; border-collapse: collapse;">
			<thead>
				<tr>
					<th style="border: 1px solid #ddd; padding: 8px;">ID</th>
					<th style="border: 1px solid #ddd; padding: 8px;">Cliente</th>
					<th style="border: 1px solid #ddd; padding: 8px;">Plan</th>
					<th style="border: 1px solid #ddd; padding: 8px;">Fecha Inicio</th>
					<th style="border: 1px solid #ddd; padding: 8px;">Fecha Fin</th>
					<th style="border: 1px solid #ddd; padding: 8px;">Costo</th>
					<th style="border: 1px solid #ddd; padding: 8px;">Total</th>
				</tr>
			</thead>
			<tbody>
				<!-- Aquí se llenarán los datos del reporte dinámicamente -->
			</tbody>
		</table>
	</div>
`);

// Función para formatear monedas
function formatCurrency(value) {
	return new Intl.NumberFormat('es-ES', {
		style: 'currency',
		currency: 'USD'  // Cambia a la moneda que necesites
	}).format(value);
}

// Llamar a la API de Frappe para obtener los datos del reporte personalizado
frappe.call({
	method: 'frappe.desk.query_report.run',
	args: {
		report_name: 'Membresias de la Semana Actual',  // Cambia esto por el nombre de tu reporte
		filters: {}  // Agrega filtros aquí si tu reporte lo requiere
	},
	callback: function(response) {
		let reportData = response.message.result;

		if (Array.isArray(reportData) && reportData.length > 0) {
			let tableBody = $('#report-table tbody');

			reportData.forEach(function(row) {
				let tableRow = $('<tr></tr>');
				
				for (const key in row) {
					if (row.hasOwnProperty(key)) {
						let tableCell = $('<td></td>');

						if (key === 'cost' || key === 'total') {
							tableCell.text(formatCurrency(row[key]));
						} else {
							tableCell.text(row[key]);
						}

						tableCell.css({
							'border': '1px solid #ddd',
							'padding': '8px'
						});
						tableRow.append(tableCell);
					}
				}
				tableBody.append(tableRow);
			});
		} else {
			console.error("No data returned from report.");
		}
	}
});
};
