// Helper function for float conversion
function flt(val) {
	return parseFloat(val) || 0;
}

frappe.ui.form.on('Delivery Note Record', {
	onload: function(frm) {
		// Set from route_options when creating from Job Record workflow
		if (frappe.route_options) {
			if (frappe.route_options.job_assignment_name && !frm.doc.job_assignment_name) {
				frm.set_value('job_assignment_name', frappe.route_options.job_assignment_name);
			}
			if (frappe.route_options.waybill && !frm.doc.waybill) {
				frm.set_value('waybill', frappe.route_options.waybill);
			}
		}
	},
	
	refresh: function(frm) {
		if (frm.doc.waybill) {
			frm.add_custom_button(__('View Waybill'), function() {
				frappe.set_route("Form", "Waybill", frm.doc.waybill);
			}, __('View'));
		}
		if (frm.doc.job_record) {
			frm.add_custom_button(__('View Job Record'), function() {
				frappe.set_route("Form", "Job Record", frm.doc.job_record);
			}, __('View'));
		}
		if (frm.doc.delivery_status === "Out for Delivery") {
			frm.add_custom_button(__('Complete Delivery'), function() {
				complete_delivery(frm);
			});
		}
		if (frappe.route_options && frappe.route_options.job_assignment_name && !frm.doc.job_assignment_name) {
			frm.set_value('job_assignment_name', frappe.route_options.job_assignment_name);
		}
		if (frappe.route_options && frappe.route_options.waybill && frm.doc.waybill && frm.is_new()) {
			fetch_details_from_waybill(frm, frm.doc.waybill);
		}
		toggle_mode_fields(frm);
	},
	
	transport_mode: function(frm) {
		toggle_mode_fields(frm);
	},
	
	waybill: function(frm) {
		if (frm.doc.waybill) {
			fetch_details_from_waybill(frm, frm.doc.waybill);
		}
	},
	
	job_record: function(frm) {
		// When waybill is set, details are filled from waybill; otherwise get from job
		if (frm.doc.waybill) return;
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
						if (r.message.consignee_address) frm.set_value('consignee_address', r.message.consignee_address);
						if (r.message.waybill) frm.set_value('waybill', r.message.waybill);
						if (r.message.cargo_description) frm.set_value('cargo_description', r.message.cargo_description);
						if (r.message.hs_code) frm.set_value('hs_code', r.message.hs_code);
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
					frm.set_value('consignee_address', format_consignee_address(consignee));
				}
			});
		} else {
			frm.set_value('consignee_address', '');
		}
	},
	shipper_name: function(frm) {
		if (frm.doc.shipper_name) {
			frappe.db.get_doc('Shipper', frm.doc.shipper_name).then(function(shipper) {
				if (shipper) {
					var parts = [];
					if (shipper.address_line1) parts.push(shipper.address_line1);
					if (shipper.address_line2) parts.push(shipper.address_line2);
					if (shipper.city) parts.push(shipper.city);
					if (shipper.state) parts.push(shipper.state);
					if (shipper.pincode) parts.push(shipper.pincode);
					if (shipper.country) parts.push(shipper.country);
					frm.set_value('shipper_address', parts.join(', '));
				}
			});
		} else {
			frm.set_value('shipper_address', '');
		}
	}
});

function toggle_mode_fields(frm) {
	var mode = frm.doc.transport_mode;
	if (!mode) return;
	frm.toggle_display('section_break_land', mode === 'Land');
	frm.toggle_display('section_break_air', mode === 'Air');
	frm.toggle_display('section_break_sea', mode === 'Sea');
}

function fetch_details_from_waybill(frm, waybill_name) {
	if (!waybill_name) return;
	frappe.call({
		method: 'ksa_logistics.ksa_logistics.doctype.delivery_note_record.delivery_note_record.get_delivery_details_from_waybill',
		args: { waybill_name: waybill_name },
		callback: function(r) {
			if (r.message) {
				Object.keys(r.message).forEach(function(key) {
					var val = r.message[key];
					if (val !== undefined && val !== null && frm.doc[key] !== val) {
						frm.set_value(key, val);
					}
				});
				frm.refresh_fields();
			}
		}
	});
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

