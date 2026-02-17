frappe.ui.form.on("Job Record", {

    onload(frm) {

        frm.events.load_quotation(frm);

        frm.set_query('driver', 'job_assignment', (doc, cdt, cdn) => {
            const row = locals[cdt][cdn];
            if (row.driver_type === 'Own') {
                return {
                    query: 'ksa_logistics.api.get_drivers_by_type',
                    filters: { driver_type: 'Own' }
                };
            }
            if (row.driver_type === 'External') {
                return {
                    query: 'ksa_logistics.api.get_drivers_by_type',
                    filters: { driver_type: 'External' }
                };
            }
            return {};
        });

        frm.set_query('vehicle', 'job_assignment', (doc, cdt, cdn) => {
            const row = locals[cdt][cdn];
            if (row.driver_type === 'Own') return { filters: { custom_is_external: 'Internal' } };
            if (row.driver_type === 'External') return { filters: { custom_is_external: 'External' } };
            return {};
        });
    },

    shipper: function(frm) {
        // Origin and destination are independent fields - do not auto-populate from shipper/consignee
        // Shipper is just a link/reference, origin should be entered separately
    },

    consignee: function(frm) {
        // Origin and destination are independent fields - do not auto-populate from shipper/consignee
        // Consignee is just a link/reference, destination should be entered separately
    },

    customer: function(frm) {
        // Note: Shipper and Consignee are independent doctypes, no customer filtering needed
        // But you can add filters here if needed in the future

        frm.clear_custom_buttons();

        if (!frm.is_new() || !frm.doc.customer) return;

        frm.add_custom_button(__('Get Items from Quotation'), () => {

            frappe.call({
                method: 'ksa_logistics.api.get_quotations_for_customer',
                args: { customer: frm.doc.customer },

                callback(r) {

                    const quotations = r.message || [];

                    if (!quotations.length) {
                        frappe.msgprint(__('No submitted quotations found for this customer.'));
                        return;
                    }

                    const dialog = new frappe.ui.Dialog({
                        title: __('Select Quotations'),
                        fields: [{ fieldname: 'quotation_table_wrapper', fieldtype: 'HTML' }],
                        primary_action_label: __('Get Items'),

                        primary_action() {

                            const selected = dialog.$wrapper
                                .find('.quotation-checkbox:checked')
                                .map((i, el) => el.dataset.quotation)
                                .get();

                            if (!selected.length) {
                                frappe.msgprint(__('Please select at least one quotation.'));
                                return;
                            }

                            frappe.call({
                                method: 'ksa_logistics.api.get_items_from_multiple_quotations',
                                args: { quotations: selected },

                                callback(res) {

                                    if (!res.message || !res.message.items) return;

                                    frm.clear_table('items');

                                    res.message.items.forEach(item => {
                                        let row = frm.add_child("items");
                                        row.item = item.item_code;
                                        row.item_name = item.item_name;
                                        row.uom = item.uom;
                                        row.quantity = item.qty;
                                        row.rate = item.rate;
                                        row.amount = item.amount;
                                        row.from_quotation = item.parent;
                                    });

                                    frm.refresh_field('items');
                                    frm.events.update_totals(frm);
                                    dialog.hide();
                                }
                            });
                        }
                    });

                    dialog.show();

                    const table_html = `
                        <table class="table table-bordered">
                            <thead>
                                <tr>
                                    <th><input type="checkbox" id="select-all-quotations"></th>
                                    <th>Quotation</th>
                                    <th>Grand Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${quotations.map(q => `
                                    <tr>
                                        <td><input type="checkbox" class="quotation-checkbox" data-quotation="${q.name}"></td>
                                        <td>${q.name}</td>
                                        <td style="text-align:right;">${frappe.format(q.grand_total, { fieldtype: 'Currency' })}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    `;

                    dialog.fields_dict.quotation_table_wrapper.$wrapper.html(table_html);

                    dialog.$wrapper.find('#select-all-quotations').on('change', function () {
                        dialog.$wrapper.find('.quotation-checkbox').prop('checked', this.checked);
                    });
                }
            });
        });
    },

      chargeable_weight(frm) {
        if (
            frm.doc.chargeable_weight &&
            frm.doc.job_types === "Air Transport"
        ) {
            let cbm = flt(frm.doc.chargeable_weight) / 167;
            frm.set_value('volume_cbm', cbm.toFixed(3));
        } else {
            frm.set_value('volume_cbm', 0);
        }
    },

    job_types(frm) {       
        frm.trigger('chargeable_weight');
    },


    refresh(frm) {

        if (frm.is_new()) return;

        // Add workflow buttons per Job Assignment row
        setup_job_assignment_workflow_buttons(frm);
        
        // Populate vouchers table with workflow documents from all assignments
        // The Python sync_workflow_vouchers method handles this on save
        // Here we just ensure it's called if needed
        if (frm.fields_dict.vouchers2 && !frm.is_new()) {
            // Check if sync is needed and trigger it
            check_and_sync_vouchers(frm);
        }

        frm.add_custom_button(__('View Trips'), () => {
            frappe.set_route("List", "Trip Details", { job_records: frm.doc.name });
        }, __("View"));

        frm.add_custom_button(__('Create Trip Details'), function () {

            let pending_rows = (frm.doc.job_assignment || [])
                .filter(r => r.trip_detail_status === "Pending");

            if (!pending_rows.length) {
                frappe.msgprint("No Pending Trips Found.");
                return;
            }

            const required_fields = {
                driver: "Driver",
                vehicle: "Vehicle"
            };

            let errors = [];

            pending_rows.forEach(row => {
                let rn = row.idx || "?";
                Object.keys(required_fields).forEach(field => {
                    if (!row[field]) {
                        errors.push(`Row ${rn}: Missing ${required_fields[field]}`);
                    }
                });
            });

            if (errors.length) {
                frappe.msgprint({ title: "Validation Errors", indicator: "red", message: errors.join("<br>") });
                return;
            }

            function create_trip(index) {

                if (index >= pending_rows.length) {

                    frm.save().then(() => {
                        frappe.msgprint("All Trips Created Successfully");
                        frm.reload_doc();
                    });

                    return;
                }

                let row = pending_rows[index];

                frappe.call({
                    method: 'ksa_logistics.api.create_trip_details',
                    args: {
                        job_record: frm.doc.name,
                        job_assignment: row.name,   
                        driver: row.driver,
                        vehicle: row.vehicle,
                        trip_amount: row.trip_amount,
                        allowance: row.allowance || 0,
                        vehicle_revenue: row.vehicle_revenue || 0
                    },
                    callback(r) {

                        if (!r.message) {
                            frappe.msgprint("Trip created but server did not return any ID.");
                            return;
                        }
                    
                        row.__creating_trip = true;
                    
                        frappe.model.set_value(row.doctype, row.name, "trip_detail_status", "Created");
                    
                        frappe.show_alert({
                            message: __('Trip Created: ' + r.message.trip_name),
                            indicator: 'green'
                        }, 5);
                    
                        setTimeout(() => { delete row.__creating_trip; }, 500);
                    
                        if (index === pending_rows.length - 1) {
                            frm.save().then(() => {
                                frappe.set_route("Form", "Trip Details", r.message.trip_name);

                            });
                        }
                    
                        create_trip(index + 1);
                    }
                    
                });
                
            }

            create_trip(0);
        });

        setTimeout(() => {
            if (frm.dashboard) {
                frm.events.set_dashboard_indicators(frm);
                frm.events.add_status_indicators(frm);
                frm.events.show_progress_bar(frm);
            }
        }, 2000);
    },
    
    collection_required: function(frm) {
        // Auto-update document status when collection is required/not required
        if (frm.doc.collection_required && frm.doc.document_status === "Job Created") {
            frm.set_value('document_status', 'Collection Scheduled');
        }
    },
    
    add_status_indicators: function(frm) {
        // Collection status
        if (frm.doc.collection_required && frm.doc.collection_status === "Completed") {
            frm.dashboard.add_indicator(__('Collection Completed'), 'green');
        }
        
        // Waybill status
        if (frm.doc.waybill_status === "In Transit") {
            frm.dashboard.add_indicator(__('In Transit'), 'blue');
        } else if (frm.doc.waybill_status === "Delivered") {
            frm.dashboard.add_indicator(__('Delivered'), 'green');
        }
        
        // POD status
        if (frm.doc.pod_status === "Verified") {
            frm.dashboard.add_indicator(__('POD Verified'), 'green');
        }
        
        // Overall status
        if (frm.doc.document_status === "Completed") {
            frm.dashboard.set_headline_alert(__('Job Completed'), 'green');
        }
    },
    
    show_progress_bar: function(frm) {
        // Calculate progress percentage
        let progress = 0;
        let steps = 0;
        let completed = 0;
        
        // Step 1: Job Created
        steps++;
        completed++;
        
        // Step 2: Collection (if required)
        if (frm.doc.collection_required) {
            steps++;
            if (frm.doc.collection_status === "Completed") {
                completed++;
            }
        }
        
        // Step 3: Waybill Created
        steps++;
        if (frm.doc.waybill_reference) {
            completed++;
        }
        
        // Step 4: In Transit
        steps++;
        if (frm.doc.waybill_status === "In Transit" || frm.doc.waybill_status === "Arrived at Destination" || frm.doc.waybill_status === "Delivered") {
            completed++;
        }
        
        // Step 5: Delivered
        steps++;
        if (frm.doc.delivery_status === "Delivered") {
            completed++;
        }
        
        // Step 6: POD Verified
        steps++;
        if (frm.doc.pod_status === "Verified") {
            completed++;
        }
        
        progress = (completed / steps) * 100;
        
        // Show progress in dashboard
        frm.dashboard.add_progress(__('Job Progress'), progress);
    },

    set_dashboard_indicators(frm) {

        if (!frm.dashboard) return;

        const currency = frm.doc.currency || frappe.defaults.get_default("currency") || "SAR";

        function sum(rows, key) {
            return (rows || []).reduce((a, r) => a + (r[key] || 0), 0);
        }

        frappe.client.get_list('Sales Invoice', {
            filters: { custom_job_record: frm.doc.name, docstatus: 1 },
            fields: ['base_grand_total']
        }).then(salesRes => {

            const sales = sum(salesRes, 'base_grand_total');

            frappe.client.get_list('Purchase Invoice', {
                filters: { custom_job_record: frm.doc.name, docstatus: 1 },
                fields: ['base_grand_total']
            }).then(purchaseRes => {

                const purchase = sum(purchaseRes, 'base_grand_total');
                const profit = sales - purchase;

                frm.dashboard.add_indicator(`Sales: ${format_currency(sales, currency)}`, "blue");
                frm.dashboard.add_indicator(`Purchase: ${format_currency(purchase, currency)}`, "orange");
                frm.dashboard.add_indicator(
                    `${profit >= 0 ? 'Profit' : 'Loss'}: ${format_currency(profit, currency)}`,
                    profit >= 0 ? "green" : "red"
                );
            });
        });
    },

    update_totals(frm) {

        let total_qty = 0;
        let total_amt = 0;

        (frm.doc.items || []).forEach(row => {
            total_qty += flt(row.quantity);
            total_amt += flt(row.amount);
        });

        frm.set_value('total_quantity', total_qty);
        frm.set_value('total_amount', total_amt);
    },

    load_quotation(frm) {

        if (!frm.is_new() || !frm.doc.quotation) return;

        frappe.db.get_doc("Quotation", frm.doc.quotation).then(q => {

            frm.set_value("customer", q.party_name);
            frm.clear_table("items");

            (q.items || []).forEach(i => {
                let row = frm.add_child("items");
                row.item = i.item_code;
                row.item_name = i.item_name;
                row.uom = i.uom;
                row.quantity = i.qty;
                row.rate = i.rate;
                row.amount = i.amount;
                row.from_quotation = i.parent;
            });

            frm.refresh_field("items");
            frm.events.update_totals(frm);
        });
    }

});

function format_shipper_address(shipper) {
	let parts = [];
	if (shipper.address_line1) parts.push(shipper.address_line1);
	if (shipper.address_line2) parts.push(shipper.address_line2);
	if (shipper.city) parts.push(shipper.city);
	if (shipper.state) parts.push(shipper.state);
	if (shipper.pincode) parts.push(shipper.pincode);
	if (shipper.country) parts.push(shipper.country);
	return parts.join(', ');
}

function format_consignee_address(consignee) {
	let parts = [];
	if (consignee.address_line1) parts.push(consignee.address_line1);
	if (consignee.address_line2) parts.push(consignee.address_line2);
	if (consignee.city) parts.push(consignee.city);
	if (consignee.state) parts.push(consignee.state);
	if (consignee.pincode) parts.push(consignee.pincode);
	if (consignee.country) parts.push(consignee.country);
	return parts.join(', ');
}

function create_collection_note(frm) {
    // Get first job assignment if available
    let job_assignments = frm.doc.job_assignment || [];
    let first_assignment = job_assignments.length > 0 ? job_assignments[0] : null;
    
    frappe.route_options = {
        "job_record": frm.doc.name
    };
    
    if (first_assignment && (first_assignment.name || first_assignment.idx)) {
        frappe.route_options.job_assignment_name = first_assignment.name || first_assignment.idx;
    }
    
    frappe.new_doc("Collection Note");
}

function create_waybill_with_driver_selection(frm) {
    // Check if job_assignment has drivers
    let job_assignments = frm.doc.job_assignment || [];
    let available_drivers = job_assignments.filter(ja => ja.driver && ja.vehicle);
    
    if (available_drivers.length === 0) {
        frappe.msgprint({
            title: __('No Driver Assignment'),
            message: __('Please assign a driver and vehicle in Job Assignment table before creating Waybill.'),
            indicator: 'orange'
        });
        return;
    }
    
    if (available_drivers.length === 1) {
        // Only one driver, use it directly
        let ja = available_drivers[0];
        frappe.route_options = {
            "job_record": frm.doc.name,
            "driver": ja.driver,
            "vehicle": ja.vehicle,
            "job_assignment_name": ja.name || ja.idx
        };
        frappe.new_doc("Waybill");
    } else {
        // Multiple drivers, show selection dialog
        let options_list = [];
        let driver_map = {};
        
        available_drivers.forEach((ja, idx) => {
            let label = `${ja.driver_name || ja.driver} - Vehicle: ${ja.vehicle || 'N/A'}`;
            options_list.push(label);
            driver_map[label] = {
                driver: ja.driver,
                vehicle: ja.vehicle,
                driver_name: ja.driver_name,
                job_assignment_name: ja.name || ja.idx,
                job_assignment_row: ja
            };
        });
        
        frappe.prompt([
            {
                fieldname: 'selected_assignment',
                fieldtype: 'Select',
                label: __('Select Driver Assignment'),
                options: options_list.join('\n'),
                reqd: 1,
                description: __('Select which driver assignment to use for this waybill')
            }
        ], function(values) {
            let selected = driver_map[values.selected_assignment];
            if (selected) {
                frappe.route_options = {
                    "job_record": frm.doc.name,
                    "driver": selected.driver,
                    "vehicle": selected.vehicle,
                    "job_assignment_name": selected.job_assignment_name,
                    "job_assignment_row": selected.job_assignment_row
                };
                frappe.new_doc("Waybill");
            }
        }, __('Select Driver for Waybill'), __('Create'));
    }
}

function create_waybill(frm) {
    frappe.route_options = {
        "job_record": frm.doc.name
    };
    frappe.new_doc("Waybill");
}

function create_delivery_note_from_waybill(frm) {
    // Get job_assignment_name from waybill
    if (frm.doc.waybill_reference) {
        frappe.db.get_value('Waybill', frm.doc.waybill_reference, 'job_assignment_name', function(r) {
            frappe.route_options = {
                "job_record": frm.doc.name,
                "waybill": frm.doc.waybill_reference
            };
            if (r && r.job_assignment_name) {
                frappe.route_options.job_assignment_name = r.job_assignment_name;
            }
            frappe.new_doc("Delivery Note Record");
        });
    } else {
        frappe.route_options = {
            "job_record": frm.doc.name
        };
        frappe.new_doc("Delivery Note Record");
    }
}

function create_delivery_note(frm) {
    frappe.route_options = {
        "job_record": frm.doc.name
    };
    frappe.new_doc("Delivery Note Record");
}

function create_pod(frm) {
    // Get job_assignment_name from delivery note or waybill
    let job_assignment_name = null;
    
    if (frm.doc.delivery_note_record) {
        frappe.db.get_value('Delivery Note Record', frm.doc.delivery_note_record, 'job_assignment_name', function(r) {
            frappe.route_options = {
                "job_record": frm.doc.name,
                "delivery_note": frm.doc.delivery_note_record
            };
            if (r && r.job_assignment_name) {
                frappe.route_options.job_assignment_name = r.job_assignment_name;
            } else if (frm.doc.waybill_reference) {
                // Fallback to waybill
                frappe.db.get_value('Waybill', frm.doc.waybill_reference, 'job_assignment_name', function(r2) {
                    if (r2 && r2.job_assignment_name) {
                        frappe.route_options.job_assignment_name = r2.job_assignment_name;
                    }
                    frappe.new_doc("Proof of Delivery");
                });
                return;
            }
            frappe.new_doc("Proof of Delivery");
        });
    } else {
        frappe.route_options = {
            "job_record": frm.doc.name
        };
        frappe.new_doc("Proof of Delivery");
    }
}


frappe.ui.form.on('Job Item Detail', {

    async item(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.item) return;

        frappe.model.set_value(cdt, cdn, 'quantity', 1);

        const r = await frappe.db.get_value(
            'Item Price',
            { item_code: row.item, price_list: 'Standard Selling' },
            'price_list_rate'
        );

        let rate = r.message ? r.message.price_list_rate : 0;

        frappe.model.set_value(cdt, cdn, 'rate', rate);
        frappe.model.set_value(cdt, cdn, 'amount', rate);
        frm.events.update_totals(frm);
    },

    quantity(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "amount", row.quantity * row.rate);
        frm.events.update_totals(frm);
    },

    rate(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "amount", row.quantity * row.rate);
        frm.events.update_totals(frm);
    },

    items_remove(frm) {
        frm.events.update_totals(frm);
    }
});


frappe.ui.form.on('Job Assignment', {

    trip_amount(frm, cdt, cdn) {

        let row = locals[cdt][cdn];
        let amount = flt(row.trip_amount) || 0;

        let allowance = 0;

        if (row.driver_type === "Own") {

            let allowance_rate = flt(frm.doc.allowance_amount);

            if (!allowance_rate) {
                frappe.msgprint(__("Allowance % is not set in Job Record"));
                allowance = 0;
            } else {
                allowance = amount * allowance_rate;
            }

            frappe.model.set_value(cdt, cdn, 'allowance', allowance);

        } else if (row.driver_type === "External") {

            allowance = amount;

            frappe.model.set_value(cdt, cdn, 'allowance', allowance);
            frappe.model.set_value(cdt, cdn, 'vehicle_revenue', allowance);
        }

        if (!row.__creating_trip) {
            frappe.model.set_value(cdt, cdn, 'trip_detail_status', 'Pending');
        }
    },


    driver_type(frm, cdt, cdn) {

        let row = locals[cdt][cdn];

        if (!row.__creating_trip) {
            frappe.model.set_value(cdt, cdn, 'trip_detail_status', 'Pending');
        }

        // Reset always
        frappe.model.set_value(cdt, cdn, 'driver', '');
        frappe.model.set_value(cdt, cdn, 'vehicle', '');

    },

    driver(frm, cdt, cdn) {

        const row = locals[cdt][cdn];

        if (!row.__creating_trip) {
            frappe.model.set_value(cdt, cdn, 'trip_detail_status', 'Pending');
        }

        if (!row.driver) {
            frappe.model.set_value(cdt, cdn, 'vehicle', '');
            frappe.model.set_value(cdt, cdn, 'transporter', '');
            return;
        }

        frappe.db.get_value('Driver', row.driver, ['employee', 'transporter']).then(r => {

            const employee = r.message.employee;
            const transporter = r.message.transporter;

            // AUTO DETECT DRIVER TYPE
            if (employee) {
                frappe.model.set_value(cdt, cdn, 'driver_type', 'Own');
            } else {
                frappe.model.set_value(cdt, cdn, 'driver_type', 'External');
            }

            // SET TRANSPORTER IF EXTERNAL DRIVER
            if (!employee && transporter) {
                frappe.model.set_value(cdt, cdn, 'transporter', transporter);
            } else {
                frappe.model.set_value(cdt, cdn, 'transporter', '');
            }

          
            if (employee) {
                frappe.db.get_list('Vehicle', {
                    filters: { employee: employee },
                    fields: ['name'],
                    limit: 1
                }).then(v => {
                    frappe.model.set_value(cdt, cdn, 'vehicle', v.length ? v[0].name : '');
                });
            }

            if (!employee && transporter) {
                frappe.db.get_list('Vehicle', {
                    filters: { custom_transporter: transporter },
                    fields: ['name'],
                    limit: 1
                }).then(v => {

                    frappe.model.set_value(cdt, cdn, 'vehicle', v.length ? v[0].name : '');

                    if (!v.length) {
                        frappe.msgprint(__('No vehicle linked to this transporter'));
                    }

                });
            }

        });

    },

    vehicle(frm, cdt, cdn) {

        let row = locals[cdt][cdn];

        if (!row.__creating_trip) {
            frappe.model.set_value(cdt, cdn, 'trip_detail_status', 'Pending');
        }

        if (row.vehicle && row.driver_type) {
            frappe.db.get_value('Vehicle', row.vehicle, 'custom_is_external').then(r => {
                const type = r.message.custom_is_external;

                if (
                    (row.driver_type === 'Own' && type !== 'Internal') ||
                    (row.driver_type === 'External' && type !== 'External')
                ) {
                    frappe.msgprint("Vehicle does not match Driver Type");
                    frappe.model.set_value(cdt, cdn, 'vehicle', '');
                }
            });
        }
    },
    
    // Sync vouchers when job assignment workflow fields change
    'job_assignment': {
        collection_note: function(frm, cdt, cdn) {
            if (!frm.is_new()) {
                sync_vouchers_after_save(frm);
            }
        },
        waybill_reference: function(frm, cdt, cdn) {
            if (!frm.is_new()) {
                sync_vouchers_after_save(frm);
            }
        },
        delivery_note_record: function(frm, cdt, cdn) {
            if (!frm.is_new()) {
                sync_vouchers_after_save(frm);
            }
        },
        pod_reference: function(frm, cdt, cdn) {
            if (!frm.is_new()) {
                sync_vouchers_after_save(frm);
            }
        }
    }

});

// Helper function to sync vouchers after save
function sync_vouchers_after_save(frm) {
    // This will be called after the document is saved
    // The Python sync_workflow_vouchers method will handle it in validate()
    // But we can also trigger a refresh of vouchers on next load
    frm.dirty();
}


frappe.ui.form.on("Job Record", {

    refresh(frm) {

        if (frm.doc.__islocal) return;

        if (frm.doc.invoice_status !== "Invoice Created") {
            frm.add_custom_button("Create Sales Invoice", () => {
                frm.events.create_sales_invoice(frm);
            });
        }

        // ------------------------------------------------
        // FILTER ITEM TAX TEMPLATE BY COMPANY (CHILD TABLE)
        // ------------------------------------------------
        frm.set_query("item_tax_template", "invoice_item", function (doc, cdt, cdn) {
            if (!frm.doc.company) return {};
            return {
                filters: {
                    company: frm.doc.company
                }
            };
        });
    },

    async create_sales_invoice(frm) {

        // ---------------------------
        // CHECK DUPLICATE
        // ---------------------------
        const existing_invoice = await frappe.db.get_list("Sales Invoice", {
            filters: { custom_job_record: frm.doc.name },
            fields: ["name", "docstatus"],
            limit: 1
        });

        if (existing_invoice.length && existing_invoice[0].docstatus !== 2) {
            frappe.msgprint({
                title: __("Duplicate Invoice"),
                message: __("A Sales Invoice already exists for this Job Record."),
                indicator: "red"
            });
            return;
        }

        // ---------------------------
        // BASIC VALIDATION
        // ---------------------------
        if (!frm.doc.invoice_item || !frm.doc.invoice_item.length) {
            frappe.msgprint({
                title: __("No Items"),
                message: __("Please add at least one row in Invoice Items."),
                indicator: "red"
            });
            return;
        }

        if (!frm.doc.company || !frm.doc.customer) {
            frappe.msgprint({
                title: __("Missing Data"),
                message: __("Company and Customer are required."),
                indicator: "red"
            });
            return;
        }

        // ---------------------------
        // BUILD ITEMS + ITEM-WISE TAX
        // ---------------------------
        let items = [];
        let tax_accounts = {};   // tax heads for header

        for (let row of frm.doc.invoice_item) {

            if (!row.item || !row.qty || !row.rate) {
                frappe.throw(__("Item, Qty and Rate are mandatory in Invoice Items"));
            }

            let item_tax_rate = null;

            if (row.item_tax_template) {

                const tax_doc = await frappe.db.get_doc(
                    "Item Tax Template",
                    row.item_tax_template
                );

                if (tax_doc.taxes && tax_doc.taxes.length) {

                    let tax_map = {};

                    tax_doc.taxes.forEach(t => {
                        tax_map[t.tax_type] = t.tax_rate;
                        tax_accounts[t.tax_type] = true; // collect header tax head
                    });

                    item_tax_rate = JSON.stringify(tax_map);
                }
            }

            items.push({
                item_code: row.item,
                qty: row.qty,
                rate: row.rate,
                item_tax_template: row.item_tax_template || null,
                item_tax_rate: item_tax_rate,   // ✅ item-wise VAT
                custom_container_no: frm.doc.custom_container_no
            });
        }

        // ---------------------------
        // HEADER TAX ROWS (RATE = 0)
        // ---------------------------
        let taxes = Object.keys(tax_accounts).map(acc => ({
            charge_type: "On Net Total",
            account_head: acc,
            description: acc,
            rate: 0,                     // item-wise tax will apply
            included_in_print_rate: 0
        }));

        // ---------------------------
        // CREATE SALES INVOICE
        // ---------------------------
        frappe.call({
            method: "frappe.client.insert",
            args: {
                doc: {
                    doctype: "Sales Invoice",
                    company: frm.doc.company,
                    customer: frm.doc.customer,
                    cost_center: frm.doc.branch,
                    posting_date: frappe.datetime.get_today(),
                    custom_job_record: frm.doc.name,
                    items: items,
                    taxes: taxes
                }
            },
            callback(r) {
                if (!r.exc) {

                    frappe.db.set_value(
                        "Job Record",
                        frm.doc.name,
                        "invoice_status",
                        "Invoice Created"
                    );

                    frappe.msgprint({
                        message: __("Sales Invoice created successfully (Draft)"),
                        indicator: "green"
                    });

                    frappe.set_route("Form", "Sales Invoice", r.message.name);
                }
            }
        });
    }
});

// ============================================
// WORKFLOW FUNCTIONS PER JOB ASSIGNMENT
// ============================================

function setup_job_assignment_workflow_buttons(frm) {
	// Show workflow options per Job Assignment row
	if (!frm.doc.job_assignment || frm.doc.job_assignment.length === 0) {
		return;
	}
	
	// Add a button to show workflow management dialog
	frm.add_custom_button(__('Manage Workflows'), function() {
		show_workflow_management_dialog(frm);
	}, __('Workflow'));
}

function show_workflow_management_dialog(frm) {
	let assignments = frm.doc.job_assignment || [];
	
	if (assignments.length === 0) {
		frappe.msgprint(__('No Job Assignments found. Please add assignments first.'));
		return;
	}
	
	let dialog = new frappe.ui.Dialog({
		title: __('Workflow Management - Job Assignments'),
		fields: [
			{
				fieldtype: 'HTML',
				options: '<div id="workflow-assignments-list"></div>'
			}
		],
		primary_action_label: __('Close'),
		primary_action: function() {
			dialog.hide();
		}
	});
	
	dialog.show();
	
	// Build HTML for each assignment with workflow buttons
	let html = '<div style="padding: 10px;">';
	
	assignments.forEach((assignment, idx) => {
		const assignment_name = assignment.name || assignment.idx;
		const driver_label = assignment.driver_name || assignment.driver || `Assignment ${idx + 1}`;
		const vehicle_label = assignment.vehicle || 'No Vehicle';
		const status = assignment.document_status || 'Pending';
		
		html += `
			<div style="border: 1px solid #d1d8dd; padding: 15px; margin-bottom: 15px; border-radius: 4px;">
				<h4 style="margin-top: 0;">${driver_label} - ${vehicle_label}</h4>
				<p><strong>Status:</strong> ${status}</p>
				<div style="margin-top: 10px;">
		`;
		
		// Collection Note button
		// Only show "Create" button if collection_note doesn't exist
		// If collection_note exists, show "View" link regardless of status
		if (!assignment.collection_note) {
			html += `<button class="btn btn-sm btn-primary" onclick="createCollectionNoteForAssignment('${frm.doc.name}', '${assignment_name}')" style="margin-right: 5px;">Create Collection Note</button>`;
		} else {
			const status_label = assignment.collection_status ? ` (${assignment.collection_status})` : '';
			html += `<a href="/app/collection-note/${assignment.collection_note}" class="btn btn-sm btn-default" style="margin-right: 5px;">View Collection Note${status_label}</a>`;
		}
		
		// Waybill button
		if (!assignment.waybill_reference && (!assignment.collection_note || assignment.collection_status === "Completed")) {
			if (assignment.driver && assignment.vehicle) {
				html += `<button class="btn btn-sm btn-primary" onclick="createWaybillForAssignment('${frm.doc.name}', '${assignment_name}', '${assignment.driver}', '${assignment.vehicle}')" style="margin-right: 5px;">Create Waybill</button>`;
			} else {
				html += `<span class="text-muted" style="margin-right: 5px;">Waybill (Driver/Vehicle required)</span>`;
			}
		} else if (assignment.waybill_reference) {
			html += `<a href="/app/waybill/${assignment.waybill_reference}" class="btn btn-sm btn-default" style="margin-right: 5px;">View Waybill</a>`;
		}
		
		// Delivery Note button
		// Only show "Create" button if delivery_note_record doesn't exist
		// If delivery_note_record exists, show "View" link regardless of status
		if (assignment.waybill_reference && !assignment.delivery_note_record && 
			(assignment.waybill_status === "Arrived at Destination" || assignment.waybill_status === "Delivered")) {
			html += `<button class="btn btn-sm btn-primary" onclick="createDeliveryNoteForAssignment('${frm.doc.name}', '${assignment_name}')" style="margin-right: 5px;">Create Delivery Note</button>`;
		} else if (assignment.delivery_note_record) {
			const status_label = assignment.delivery_status ? ` (${assignment.delivery_status})` : '';
			html += `<a href="/app/delivery-note-record/${assignment.delivery_note_record}" class="btn btn-sm btn-default" style="margin-right: 5px;">View Delivery Note${status_label}</a>`;
		}
		
		// POD button
		// Only show "Create" button if pod_reference doesn't exist
		// If pod_reference exists, show "View" link regardless of status
		if (assignment.delivery_note_record && !assignment.pod_reference && assignment.delivery_status === "Delivered") {
			html += `<button class="btn btn-sm btn-primary" onclick="createPODForAssignment('${frm.doc.name}', '${assignment_name}')" style="margin-right: 5px;">Create POD</button>`;
		} else if (assignment.pod_reference) {
			const status_label = assignment.pod_status ? ` (${assignment.pod_status})` : '';
			html += `<a href="/app/proof-of-delivery/${assignment.pod_reference}" class="btn btn-sm btn-default" style="margin-right: 5px;">View POD${status_label}</a>`;
		}
		
		html += `
				</div>
			</div>
		`;
	});
	
	html += '</div>';
	
	dialog.$wrapper.find('#workflow-assignments-list').html(html);
}

// Global functions for button clicks (called from HTML)
window.createCollectionNoteForAssignment = function(job_record, assignment_name) {
	frappe.route_options = {
		"job_record": job_record,
		"job_assignment_name": assignment_name
	};
	frappe.new_doc("Collection Note");
};

window.createWaybillForAssignment = function(job_record, assignment_name, driver, vehicle) {
	frappe.route_options = {
		"job_record": job_record,
		"job_assignment_name": assignment_name,
		"driver": driver,
		"vehicle": vehicle
	};
	frappe.new_doc("Waybill");
};

window.createDeliveryNoteForAssignment = function(job_record, assignment_name) {
	frappe.route_options = {
		"job_record": job_record,
		"job_assignment_name": assignment_name
	};
	frappe.new_doc("Delivery Note Record");
};

window.createPODForAssignment = function(job_record, assignment_name) {
	frappe.route_options = {
		"job_record": job_record,
		"job_assignment_name": assignment_name
	};
	frappe.new_doc("Proof of Delivery");
};

// ============================================
// POPULATE VOUCHERS FROM JOB ASSIGNMENTS
// ============================================

function check_and_sync_vouchers(frm) {
	// Check if vouchers need to be synced by comparing assignment documents with vouchers
	if (!frm.doc.job_assignment || frm.doc.job_assignment.length === 0) {
		return;
	}
	
	let needs_sync = false;
	let workflow_doctypes = ["Collection Note", "Waybill", "Delivery Note Record", "Proof of Delivery"];
	
	// Collect all workflow documents from assignments
	let assignment_docs = [];
	frm.doc.job_assignment.forEach((assignment) => {
		if (assignment.collection_note) assignment_docs.push(assignment.collection_note);
		if (assignment.waybill_reference) assignment_docs.push(assignment.waybill_reference);
		if (assignment.delivery_note_record) assignment_docs.push(assignment.delivery_note_record);
		if (assignment.pod_reference) assignment_docs.push(assignment.pod_reference);
	});
	
	// Collect workflow vouchers
	let voucher_docs = [];
	(frm.doc.vouchers2 || []).forEach(v => {
		if (workflow_doctypes.includes(v.link_type) && v.voucher_record_link) {
			voucher_docs.push(v.voucher_record_link);
		}
	});
	
	// Check if all assignment documents are in vouchers
	assignment_docs.forEach(doc => {
		if (!voucher_docs.includes(doc)) {
			needs_sync = true;
		}
	});
	
	// Also check if there are extra vouchers that shouldn't be there
	if (voucher_docs.length !== assignment_docs.length) {
		needs_sync = true;
	}
	
	// If sync needed, call the server method
	if (needs_sync) {
		frappe.call({
			method: 'ksa_logistics.ksa_logistics.doctype.job_record.job_record.sync_workflow_vouchers',
			args: { job_record: frm.doc.name },
			callback: function(r) {
				if (r.message && r.message.success) {
					frm.reload_doc();
				}
			}
		});
	}
}


