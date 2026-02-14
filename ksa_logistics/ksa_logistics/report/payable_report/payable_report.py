# Copyright (c) 2026, ramees@enfono.com and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import today, getdate, money_in_words, flt


def execute(filters=None):
    columns = [
        {"fieldname": "posting_date", "label": "Date", "fieldtype": "Date", "width": 120},
        {"fieldname": "name", "label": "Voucher No", "fieldtype": "Link", "options": "Purchase Invoice", "width": 200},
        {"fieldname": "supplier_name", "label": "Supplier Name", "fieldtype": "Data", "width": 200},
        {"fieldname": "cost_center", "label": "Branch", "fieldtype": "Data", "width": 140},
        {"fieldname": "narration", "label": "Narration", "fieldtype": "Data", "width": 200},
        {"fieldname": "amount", "label": "Total Amount", "fieldtype": "Currency", "width": 150},
        {"fieldname": "os_amount", "label": "O/S Amount", "fieldtype": "Currency", "width": 150},
        {"fieldname": "running_total", "label": "Running Total", "fieldtype": "Currency", "width": 150},
        {"fieldname": "ageing", "label": "Ageing", "fieldtype": "Int", "width": 120},
    ]

    condns = {"docstatus": 1}
    data = []
    address_display = None

    if filters:
        if filters.supplier:
            condns["supplier"] = filters.supplier
            address_name = frappe.db.get_value(
                "Dynamic Link",
                {
                    "link_doctype": "Supplier",
                    "link_name": filters.supplier,
                    "parenttype": "Address",
                },
                "parent",
            )
            if address_name:
                address_doc = frappe.get_doc("Address", address_name)
                address_display = frappe.get_attr(
                    "frappe.contacts.doctype.address.address.get_address_display"
                )(address_doc.as_dict())

        if filters.get("from_date") and filters.get("to_date"):
            condns["posting_date"] = ["between", [filters.from_date, filters.to_date]]
        elif filters.get("from_date"):
            condns["posting_date"] = [">=", filters.from_date]
        elif filters.get("to_date"):
            condns["posting_date"] = ["<=", filters.to_date]

    fields = [
        "name",
        "posting_date",
        "grand_total",
        "outstanding_amount",
        "cost_center",
        "supplier",
        "supplier_name",
    ]

    meta = frappe.get_meta("Purchase Invoice")
    if meta.has_field("custom_job_record"):
        fields.append("custom_job_record")
    if meta.has_field("custom_warehouse_job_record"):
        fields.append("custom_warehouse_job_record")

    condns["outstanding_amount"] = [">", 0]

    invoices = frappe.get_all(
        "Purchase Invoice",
        filters=condns,
        fields=fields,
        order_by="posting_date",
    )

    if invoices:
        as_of_date = today()
        ageing_buckets = {
            "ageing_30": 0,
            "ageing_60": 0,
            "ageing_90": 0,
            "ageing_120": 0,
            "ageing_150": 0,
            "ageing_180": 0,
            "ageing_plus": 0,
        }

        total_amt = sum(flt(inv.get("grand_total", 0)) for inv in invoices)
        total_os = sum(flt(inv.get("outstanding_amount", 0)) for inv in invoices)

        running_balance = total_os
        running_total = 0

        for idx, invoice in enumerate(invoices):
            posting_date = invoice.get("posting_date")
            amount = flt(invoice.get("grand_total", 0))
            os_amount = flt(invoice.get("outstanding_amount", 0))

            invoice["narration"] = (
                invoice.get("custom_job_record")
                or invoice.get("custom_warehouse_job_record")
                or ""
            )
            invoice["amount"] = amount
            invoice["os_amount"] = os_amount
            invoice["balance"] = running_balance

            running_balance -= os_amount
            running_total += os_amount
            invoice["running_total"] = running_total

            if posting_date:
                age = (getdate(as_of_date) - getdate(posting_date)).days
                invoice["ageing"] = age
            else:
                invoice["ageing"] = ""

            if idx == 0 and address_display:
                invoice["primary_address"] = address_display

            amt = flt(invoice.get("outstanding_amount", 0))
            if age < 30:
                ageing_buckets["ageing_30"] += amt
            elif age < 60:
                ageing_buckets["ageing_60"] += amt
            elif age < 90:
                ageing_buckets["ageing_90"] += amt
            elif age < 120:
                ageing_buckets["ageing_120"] += amt
            elif age < 150:
                ageing_buckets["ageing_150"] += amt
            elif age < 180:
                ageing_buckets["ageing_180"] += amt
            else:
                ageing_buckets["ageing_plus"] += amt

        data.extend(invoices)

        balance_row = {
            "posting_date": "",
            "name": "",
            "supplier_name": "",
            "cost_center": "",
            "narration": "",
            "amount": total_amt,
            "os_amount": total_os,
            "balance": total_os,
            "running_total": running_total,
            "ageing": "",
            "ageing_30": ageing_buckets["ageing_30"],
            "ageing_60": ageing_buckets["ageing_60"],
            "ageing_90": ageing_buckets["ageing_90"],
            "ageing_120": ageing_buckets["ageing_120"],
            "ageing_150": ageing_buckets["ageing_150"],
            "ageing_180": ageing_buckets["ageing_180"],
            "ageing_plus": ageing_buckets["ageing_plus"],
            "amount_in_words": money_in_words(total_os, "SAR") if total_os else "",
            "primary_address": address_display,
        }
        data.append(balance_row)

        return columns, data

    return columns, []