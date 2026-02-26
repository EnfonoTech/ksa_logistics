# Copyright (c) 2026, ramees@enfono.com and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"fieldname": "date",                 "label": "Date",                 "fieldtype": "Date",         "width": 110},
        {"fieldname": "job_record",           "label": "Job Record",           "fieldtype": "Link",         "options": "Job Record", "width": 140},
        {"fieldname": "voucher_type",         "label": "Voucher Type",         "fieldtype": "Data",         "width": 140},
        {"fieldname": "invoice_no",           "label": "Invoice No",           "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 180},
        {"fieldname": "customer_name",        "label": "Customer Name",        "fieldtype": "Data",         "width": 160},
        {"fieldname": "customer_vat_no",      "label": "Customer VAT No",      "fieldtype": "Data",         "width": 160},
        {"fieldname": "receipt_vat_amt",      "label": "Receipt VAT Amt",      "fieldtype": "Currency",     "width": 140},
        {"fieldname": "supplier_name",        "label": "Supplier Name",        "fieldtype": "Data",         "width": 160},
        {"fieldname": "supplier_purchase_no", "label": "Supplier Purchase No", "fieldtype": "Data",         "width": 190},
        {"fieldname": "supplier_vat_no",      "label": "Supplier VAT No",      "fieldtype": "Data",         "width": 140},
        {"fieldname": "supplier_vat_amt",     "label": "Supplier VAT Amt",     "fieldtype": "Currency",     "width": 140},
        {"fieldname": "journal_amt",          "label": "Journal Amt",          "fieldtype": "Currency",     "width": 130},
        {"fieldname": "difference",           "label": "Difference",           "fieldtype": "Currency",     "width": 130},
    ]


def get_data(filters):
    if not filters:
        filters = {}

    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    job_record_filter = filters.get("job_record")

    data = []

    # Sales Invoices
    si_conditions = "si.docstatus = 1 AND si.custom_job_record IS NOT NULL AND si.custom_job_record != ''"
    si_values = {}
    if from_date:
        si_conditions += " AND jr.date >= %(from_date)s"
        si_values["from_date"] = from_date
    if to_date:
        si_conditions += " AND jr.date <= %(to_date)s"
        si_values["to_date"] = to_date
    if job_record_filter:
        si_conditions += " AND jr.name = %(job_record)s"
        si_values["job_record"] = job_record_filter

    sales_invoices = frappe.db.sql(
        f"""
        SELECT
            jr.date                                     AS date,
            jr.name                                     AS job_record,
            'Sales Invoice'                             AS voucher_type,
            si.name                                     AS invoice_no,
            si.customer_name                            AS customer_name,
            cust.custom_vat_registration_number         AS customer_vat_no,
            si.total_taxes_and_charges                  AS receipt_vat_amt,
            NULL                                        AS supplier_name,
            NULL                                        AS supplier_purchase_no,
            NULL                                        AS supplier_vat_no,
            0                                           AS supplier_vat_amt,
            0                                           AS journal_amt
        FROM `tabSales Invoice` si
        INNER JOIN `tabJob Record` jr ON jr.name = si.custom_job_record
        LEFT JOIN `tabCustomer` cust ON cust.name = si.customer
        WHERE {si_conditions}
        """,
        si_values, as_dict=True
    )
    data.extend(sales_invoices)

    # Purchase Invoices
    pi_conditions = "pi.docstatus = 1 AND pi.custom_job_record IS NOT NULL AND pi.custom_job_record != ''"
    pi_values = {}
    if from_date:
        pi_conditions += " AND jr.date >= %(from_date)s"
        pi_values["from_date"] = from_date
    if to_date:
        pi_conditions += " AND jr.date <= %(to_date)s"
        pi_values["to_date"] = to_date
    if job_record_filter:
        pi_conditions += " AND jr.name = %(job_record)s"
        pi_values["job_record"] = job_record_filter

    purchase_invoices = frappe.db.sql(
        f"""
        SELECT
            jr.date                         AS date,
            jr.name                         AS job_record,
            'Purchase Invoice'              AS voucher_type,
            pi.name                         AS invoice_no,
            NULL                            AS customer_name,
            NULL                            AS customer_vat_no,
            0                               AS receipt_vat_amt,
            pi.supplier_name                AS supplier_name,
            pi.bill_no                      AS supplier_purchase_no,
            pi.tax_id                       AS supplier_vat_no,
            pi.total_taxes_and_charges      AS supplier_vat_amt,
            0                               AS journal_amt
        FROM `tabPurchase Invoice` pi
        INNER JOIN `tabJob Record` jr ON jr.name = pi.custom_job_record
        WHERE {pi_conditions}
        """,
        pi_values, as_dict=True
    )
    data.extend(purchase_invoices)

    # Journal Entries
    je_conditions = "je.docstatus = 1 AND je.custom_job_record IS NOT NULL AND je.custom_job_record != ''"
    je_values = {}
    if from_date:
        je_conditions += " AND jr.date >= %(from_date)s"
        je_values["from_date"] = from_date
    if to_date:
        je_conditions += " AND jr.date <= %(to_date)s"
        je_values["to_date"] = to_date
    if job_record_filter:
        je_conditions += " AND jr.name = %(job_record)s"
        je_values["job_record"] = job_record_filter

    journal_entries = frappe.db.sql(
        f"""
        SELECT
            jr.date                         AS date,
            jr.name                         AS job_record,
            'Journal Entry'                 AS voucher_type,
            je.name                         AS invoice_no,
            NULL                            AS customer_name,
            NULL                            AS customer_vat_no,
            0                               AS receipt_vat_amt,
            NULL                            AS supplier_name,
            NULL                            AS supplier_purchase_no,
            NULL                            AS supplier_vat_no,
            0                               AS supplier_vat_amt,
            je.total_debit                  AS journal_amt
        FROM `tabJournal Entry` je
        INNER JOIN `tabJob Record` jr ON jr.name = je.custom_job_record
        WHERE {je_conditions}
        """,
        je_values, as_dict=True
    )
    data.extend(journal_entries)

    # Sort by date then job record
    data.sort(key=lambda x: (str(x.get("date") or ""), x.get("job_record") or ""))

    
    for row in data:
        row["difference"] = (
            (row.get("receipt_vat_amt") or 0)
            - (row.get("supplier_vat_amt") or 0)
            - (row.get("journal_amt") or 0)
        )

    return data