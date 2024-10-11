import frappe

@frappe.whitelist()
def get_company_and_plans(user):
    # Obtener la compañía asociada al usuario logueado a través de User Permissions
    company_name = frappe.get_value("User Permission", {"user": user, "allow": "Company"}, "for_value")

    if not company_name:
        frappe.throw("No se ha encontrado una compañía asociada al usuario.")
    
    # Obtener los detalles de la compañía
    company = frappe.get_doc("Company", company_name)
    
    # Obtener los planes contratados de la compañía
    planes_contratados = frappe.get_all("Planes Contratados", 
                                        filters={"parent": company_name}, 
                                        fields=["plan_id", "date_ini", "date_fin", "cost", "status"])

    # Obtener detalles del nombre del plan a través del ORM
    planes_con_info = []
    for plan in planes_contratados:
        # Obtener el nombre del plan a partir del ID del plan
        plan_name = frappe.get_value("Planes", plan["plan_id"], "name_plan")
        planes_con_info.append({
            "plan_name": plan_name,
            "date_start": plan["date_ini"],
            "date_end": plan["date_fin"],
            "plan_cost": plan["cost"],
            "plan_status": plan["status"]
        })

    # Preparar la respuesta con la información de la compañía y los planes
    result = {
        "company_name": company.name_company,
        "company_logo": company.logo,
        "planes": planes_con_info
    }

    return result
