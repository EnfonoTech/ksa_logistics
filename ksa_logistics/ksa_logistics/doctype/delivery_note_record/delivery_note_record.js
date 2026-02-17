// Helper function for float conversion
function flt(val) {
	return parseFloat(val) || 0;
}

frappe.ui.form.on('Delivery Note Record', {
	onload: function(frm) {
		// Set job_assignment_name from route_options early, before validate runs
		if (frappe.route_options && frappe.route_options.job_assignment_name && !frm.doc.job_assignment_name) {
			frm.set_value('job_assignment_name', frappe.route_options.job_assignment_name);
		}
	},
	
	refresh: function(frm) {
		// Add link to job record
		if (frm.doc.job_record) {
			frm.add_custom_button(__('View Job Record'), function() {
				frappe.set_route("Form", "Job Record", frm.doc.job_record);
			}, __('View'));
		}
		
		// Add complete delivery button
		if (frm.doc.delivery_status === "Out for Delivery") {
			frm.add_custom_button(__('Complete Delivery'), function() {
				complete_delivery(frm);
			});
		}
		
		// Set job_assignment_name from route_options if available
		if (frappe.route_options && frappe.route_options.job_assignment_name && !frm.doc.job_assignment_name) {
			frm.set_value('job_assignment_name', frappe.route_options.job_assignment_name);
		}
		
		// Get job_assignment_name from waybill if not set
		if (!frm.doc.job_assignment_name && frm.doc.waybill) {
			frappe.db.get_value('Waybill', frm.doc.waybill, 'job_assignment_name', function(r) {
				if (r && r.job_assignment_name) {
					frm.set_value('job_assignment_name', r.job_assignment_name);
				}
			});
		}
	},
	
	job_record: function(frm) {
		if (frm.doc.job_record && !frm.doc.consignee_name) {
			frappe.call({
				method: 'ksa_logistics.ksa_logistics.doctype.delivery_note_record.delivery_note_record.get_delivery_details',
				args: { 
					job_record: frm.doc.job_record,
					job_assignment_name: frm.doc.job_assignment_name
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('customer', r.message.customer);
						frm.set_value('consignee_name', r.message.consignee_name);
						frm.set_value('delivery_address', r.message.delivery_address);
						frm.set_value('waybill', r.message.waybill);
						// cargo_description and hs_code come from Job Assignment (via get_delivery_details)
						if (r.message.cargo_description) {
							frm.set_value('cargo_description', r.message.cargo_description);
						}
						if (r.message.hs_code) {
							frm.set_value('hs_code', r.message.hs_code);
						}
					}
				}
			});
		}
	},
	
	job_assignment_name: function(frm) {
		// Refresh details when job_assignment_name changes
		if (frm.doc.job_record) {
			frm.trigger('job_record');
		}
	},
	
	delivery_status: function(frm) {
		if (frm.doc.delivery_status === "Delivered") {
			if (!frm.doc.delivery_completion_time) {
				frm.set_value('delivery_completion_time', frappe.datetime.now_datetime());
			}
		}
	},
	
	consignee_name: function(frm) {
		if (frm.doc.consignee_name) {
			frappe.db.get_doc('Consignee', frm.doc.consignee_name).then(function(consignee) {
				if (consignee) {
					let address_str = format_consignee_address(consignee);
					frm.set_value('delivery_address', address_str);
				}
			});
		} else {
			frm.set_value('delivery_address', '');
		}
	}
});

frappe.ui.form.on('Delivery Item', {
	quantity: function(frm, cdt, cdn) {
		calculate_cbm(frm, cdt, cdn);
		calculate_totals(frm);
	},
	
	weight: function(frm, cdt, cdn) {
		calculate_totals(frm);
	},
	
	length_cm: function(frm, cdt, cdn) {
		calculate_cbm(frm, cdt, cdn);
		calculate_totals(frm);
	},
	
	width_cm: function(frm, cdt, cdn) {
		calculate_cbm(frm, cdt, cdn);
		calculate_totals(frm);
	},
	
	height_cm: function(frm, cdt, cdn) {
		calculate_cbm(frm, cdt, cdn);
		calculate_totals(frm);
	},
	
	volume: function(frm, cdt, cdn) {
		calculate_totals(frm);
	},
	
	delivery_items_remove: function(frm) {
		calculate_totals(frm);
	}
});

function calculate_cbm(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	if (row.length_cm && row.width_cm && row.height_cm) {
		// CBM = (L × W × H) / 1,000,000 (convert cm³ to m³)
		let cbm = (flt(row.length_cm) * flt(row.width_cm) * flt(row.height_cm)) / 1000000.0;
		// Multiply by quantity
		cbm = cbm * flt(row.quantity || 1);
		frappe.model.set_value(cdt, cdn, 'cbm', cbm);
	}
}

function calculate_totals(frm) {
	let total_packages = 0;
	let total_weight = 0;
	let total_volume = 0;
	
	(frm.doc.delivery_items || []).forEach(row => {
		total_packages += flt(row.quantity || 0);
		total_weight += flt(row.weight || 0);
		// Use CBM if calculated, otherwise use volume field
		total_volume += flt(row.cbm || row.volume || 0);
	});
	
	frm.set_value('total_packages', total_packages);
	frm.set_value('total_weight', total_weight);
	frm.set_value('total_volume', total_volume);
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

function complete_delivery(frm) {
	frappe.prompt([
		{
			fieldname: 'receiver_name',
			fieldtype: 'Data',
			label: 'Receiver Name',
			reqd: 1
		},
		{
			fieldname: 'receiver_id',
			fieldtype: 'Data',
			label: 'Receiver ID/Iqama',
			reqd: 1
		}
	], function(values) {
		frm.set_value('receiver_name', values.receiver_name);
		frm.set_value('receiver_id', values.receiver_id);
		frm.set_value('delivery_status', 'Delivered');
		frm.set_value('delivery_completion_time', frappe.datetime.now_datetime());
		
		frappe.msgprint(__('Please capture receiver signature and photos before saving'));
	}, __('Receiver Details'));
}

