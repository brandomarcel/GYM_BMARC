import frappe

def execute(filters=None):
    # Verificar si hay un filtro de compañía o asignar automáticamente si el usuario es el dueño
    if not filters:
        filters = {}

    # Obtener el usuario actual
    current_user = frappe.session.user

    # Verificar si el usuario es dueño de una compañía
    company_name = frappe.get_value("User Permission", {"user": current_user, "allow": "Company"}, "for_value")
    
    # Si el usuario tiene una compañía y no se ha pasado una compañía manualmente, aplicar el filtro
    if not filters.get("company") and company_name:
        filters["company"] = company_name

    # Aplicar el filtro de compañía en la consulta SQL
    company_filter = ""
    if filters.get("company"):
        company_filter = " AND mr.company_id = %(company)s"

    # Aplicar el filtro de estado en la consulta SQL
    status_filter = ""
    if filters.get("status") !='Todos':
        status_filter = " AND mr.status = %(status)s"

    # Consulta para obtener todas las membresías con los filtros aplicados (compañía y estado)
    memberships = frappe.db.sql(f"""
        SELECT 
            mr.name as membership_id,
            COALESCE(c.full_name, 'Unknown') as customer_name,
            COALESCE(p.name_type, 'Unknown') as plan_name,
            mr.date_ini,
            mr.date_fin,
            mr.cost,
            mr.discount,
            mr.total,
            mr.status
        FROM 
            `tabmemberships_register` mr
        LEFT JOIN 
            `tabCustomer` c ON mr.customer_id = c.name
        LEFT JOIN 
            `tabMembership_Type` p ON mr.plan = p.name
        WHERE 
            1 = 1 {company_filter} {status_filter}  -- Aplicar filtros de compañía y estado si están presentes
        ORDER BY 
            mr.creation DESC  -- Ordenar por la fecha de creación (los más recientes primero)
    """, filters, as_dict=True)

    # Definir las columnas del reporte
    columns = [
        {"fieldname": "membership_id", "label": "ID", "fieldtype": "Link", "options": "memberships_register", "width": 120},
        {"fieldname": "customer_name", "label": "Cliente", "fieldtype": "Data", "width": 300},
        {"fieldname": "plan_name", "label": "Plan", "fieldtype": "Data", "width": 150},
        {"fieldname": "date_ini", "label": "Fecha Inicio", "fieldtype": "Date", "width": 150},
        {"fieldname": "date_fin", "label": "Fecha Fin", "fieldtype": "Date", "width": 150},
        {"fieldname": "status", "label": "Estado", "fieldtype": "Data", "width": 100},
        {"fieldname": "cost", "label": "Costo", "fieldtype": "Currency", "width": 100},
        {"fieldname": "discount", "label": "Descuento", "fieldtype": "Currency", "width": 100},
        {"fieldname": "total", "label": "Total", "fieldtype": "Currency", "width": 100}
    ]

    # Retornar las columnas y los datos del reporte
    return columns, memberships
