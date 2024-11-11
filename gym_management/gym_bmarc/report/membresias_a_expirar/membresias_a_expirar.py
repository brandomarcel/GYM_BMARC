import frappe
from frappe.utils import getdate, today, date_diff

def execute(filters=None):
    # Verificar si hay un filtro de compañía o asignar automáticamente si el usuario es el dueño
    if not filters:
        filters = {}

    # Obtener el usuario actual
    current_user = frappe.session.user

    # Verificar si el usuario es dueño de una compañía (por ejemplo, si el usuario tiene una propiedad company_id o similar)
    company_name = frappe.get_value("User Permission", {"user": current_user, "allow": "Company"}, "for_value")
    
    # Si el usuario tiene una compañía y no se ha pasado una compañía manualmente, aplicar el filtro
    if not filters.get("company") and company_name:
        filters["company"] = company_name

    # Aplicar el filtro de compañía en la consulta SQL
    company_filter = ""
    if filters.get("company"):
        company_filter = " AND mr.company_id = %(company)s"

    # Calcular la diferencia en días entre la fecha final y la fecha actual
    today_date = today()

    # Consulta para obtener las membresías activas, con filtro de compañía (si existe), calcular los días restantes y limitar a 20 resultados
    memberships = frappe.db.sql(f"""
        SELECT 
            mr.name as membership_id,
            COALESCE(c.full_name, 'Unknown') as customer_name,
            COALESCE(p.name_type, 'Unknown') as plan_name,
            mr.date_ini,
            mr.date_fin,
            IF( (DATEDIFF(mr.date_fin, %(today_date)s)) <=0 , "FINALIZO", DATEDIFF(mr.date_fin, %(today_date)s)) as days_left  -- Calcular los días restantes
        FROM 
            `tabmemberships_register` mr
        LEFT JOIN 
            `tabCustomer` c ON mr.customer_id = c.name
        LEFT JOIN 
            `tabMembership_Type` p ON mr.plan = p.name
        WHERE 
            1 = 1 
            {company_filter}  -- Aplicar filtro de compañía si está presente
            AND mr.status = 'Activo'  -- Solo incluir membresías activas
        ORDER BY 
            CASE 
                WHEN DATEDIFF(mr.date_fin, %(today_date)s) <= 10 THEN 0
                ELSE DATEDIFF(mr.date_fin, %(today_date)s)
            END, -- Priorizar membresías que expiren en 10 días o menos
            mr.date_fin ASC  -- Ordenar por la fecha de finalización después de la prioridad
        LIMIT 20  -- Limitar los resultados a los 20 más recientes
    """, {"today_date": today_date, **filters}, as_dict=True)

    # Definir las columnas del reporte
    columns = [
        {"fieldname": "membership_id", "label": "ID", "fieldtype": "Link", "options": "memberships_register", "width": 120},
        {"fieldname": "customer_name", "label": "Cliente", "fieldtype": "Data", "width": 300},
        {"fieldname": "plan_name", "label": "Plan", "fieldtype": "Data", "width": 150},
        {"fieldname": "date_ini", "label": "Fecha Inicio", "fieldtype": "Date", "width": 150},
        {"fieldname": "date_fin", "label": "Fecha Fin", "fieldtype": "Date", "width": 150},
        {"fieldname": "days_left", "label": "Días Restantes", "fieldtype": "Int", "width": 100},
        {"fieldname": "cost", "label": "Costo", "fieldtype": "Currency", "width": 100},
        {"fieldname": "total", "label": "Total", "fieldtype": "Currency", "width": 100}
    ]

    # Retornar las columnas y los datos del reporte
    return columns, memberships
