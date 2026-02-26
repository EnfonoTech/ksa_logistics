// Copyright (c) 2026, ramees@enfono.com and contributors
// For license information, please see license.txt

frappe.query_reports["VAT Statement Report"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			
		},
		{
			"fieldname": "job_record",
			"label": __("Job Record"),
			"fieldtype": "Link",
			"options": "Job Record"
		}
	]
};