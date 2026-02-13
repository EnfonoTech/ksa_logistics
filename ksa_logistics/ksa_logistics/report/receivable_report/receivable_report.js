// Copyright (c) 2026, ramees@enfono.com and contributors
// For license information, please see license.txt

frappe.query_reports["Receivable Report"] = {
	"filters": [
		{
            fieldname: "customer",
            label: "Customer",
            fieldtype: "Link",
            options: "Customer",
            width: 150
        },
        {
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        }

	]
};
