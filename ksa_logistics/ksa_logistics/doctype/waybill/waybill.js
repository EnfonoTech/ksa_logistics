frappe.ui.form.on('Waybill', {
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
		
		// Add status update button
		if (frm.doc.waybill_status !== "Delivered") {
			frm.add_custom_button(__('Update Status'), function() {
				show_status_dialog(frm);
			});
		}
		
		// Add tracking update button
		frm.add_custom_button(__('Add Tracking'), function() {
			show_tracking_dialog(frm);
		}, __('Actions'));
		
		// Show mode indicator
		if (frm.doc.transport_mode) {
			let color = frm.doc.transport_mode === 'Land' ? 'green' : 
			           frm.doc.transport_mode === 'Air' ? 'orange' : 'blue';
			frm.dashboard.add_indicator(__(frm.doc.transport_mode + ' Transport'), color);
		}
		
		// Toggle field visibility based on mode
		toggle_mode_fields(frm);
	},
	
	job_record: function(frm) {
		if (frm.doc.job_record && !frm.doc.shipper_name) {
			// Get job assignment name - prioritize frm.doc (set in onload) over route_options
			let job_assignment_name = frm.doc.job_assignment_name || null;
			if (!job_assignment_name && frappe.route_options && frappe.route_options.job_assignment_name) {
				job_assignment_name = frappe.route_options.job_assignment_name;
				// Set it on the form so Python code can access it
				frm.set_value('job_assignment_name', job_assignment_name);
			}
			
			// Auto-fetch job details - IMPORTANT: Pass job_assignment_name to get cargo from Job Assignment
			frappe.call({
				method: 'ksa_logistics.ksa_logistics.doctype.waybill.waybill.get_waybill_template',
				args: { 
					job_record: frm.doc.job_record,
					job_assignment_name: job_assignment_name  // This ensures cargo comes from Job Assignment
				},
				callback: function(r) {
					if (r.message) {
						// Set cargo details FIRST (these should come from Job Assignment if job_assignment_name was provided)
						let cargo_fields = ['number_of_packages', 'gross_weight', 'volume_cbm', 'cargo_description', 'hs_code'];
						cargo_fields.forEach(function(field) {
							if (r.message[field] !== undefined && r.message[field] !== null && r.message[field] !== '') {
								frm.set_value(field, r.message[field]);
							}
						});
						
						// Then set other fields
						$.each(r.message, function(key, value) {
							if (!cargo_fields.includes(key) && value && !frm.doc[key]) {
								frm.set_value(key, value);
							}
						});
						frm.refresh_fields();
					}
				}
			});
			
			// Set driver, vehicle from route_options if available
			if (frappe.route_options) {
				if (frappe.route_options.driver && !frm.doc.driver) {
					frm.set_value('driver', frappe.route_options.driver);
				}
				if (frappe.route_options.vehicle && !frm.doc.vehicle) {
					frm.set_value('vehicle', frappe.route_options.vehicle);
				}
			}
		}
	},
	
	transport_mode: function(frm) {
		toggle_mode_fields(frm);
	},
	
	vehicle: function(frm) {
		if (frm.doc.vehicle) {
			frappe.db.get_value('Vehicle', frm.doc.vehicle, 
				['license_plate'], function(r) {
				if (r && r.license_plate) {
					frm.set_value('vehicle_plate_number', r.license_plate);
				}
			});
		}
	},
	
	driver: function(frm) {
		if (frm.doc.driver) {
			frappe.db.get_value('Driver', frm.doc.driver,
				['full_name', 'cell_number'], function(r) {
				if (r) {
					frm.set_value('driver_name', r.full_name);
					frm.set_value('driver_mobile', r.cell_number);
				}
			});
		}
	},
	
	shipper_name: function(frm) {
		if (frm.doc.shipper_name) {
			frappe.db.get_doc('Shipper', frm.doc.shipper_name).then(function(shipper) {
				if (shipper) {
					let address_str = format_shipper_address(shipper);
					frm.set_value('shipper_address', address_str);
				}
			});
		} else {
			frm.set_value('shipper_address', '');
		}
	},
	
	consignee_name: function(frm) {
		if (frm.doc.consignee_name) {
			frappe.db.get_doc('Consignee', frm.doc.consignee_name).then(function(consignee) {
				if (consignee) {
					let address_str = format_consignee_address(consignee);
					frm.set_value('consignee_address', address_str);
				}
			});
		} else {
			frm.set_value('consignee_address', '');
		}
	}
});

function toggle_mode_fields(frm) {
	let mode = frm.doc.transport_mode;
	
	// Land fields
	frm.toggle_display('section_break_land', mode === 'Land');
	frm.toggle_reqd('vehicle', mode === 'Land');
	frm.toggle_reqd('driver', mode === 'Land');
	
	// Air fields
	frm.toggle_display('section_break_air', mode === 'Air');
	frm.toggle_reqd('airline', mode === 'Air');
	frm.toggle_reqd('flight_number', mode === 'Air');
	frm.toggle_reqd('departure_airport', mode === 'Air');
	frm.toggle_reqd('arrival_airport', mode === 'Air');
	
	// Sea fields
	frm.toggle_display('section_break_sea', mode === 'Sea');
	frm.toggle_reqd('shipping_line', mode === 'Sea');
	frm.toggle_reqd('vessel_name', mode === 'Sea');
	frm.toggle_reqd('port_of_loading', mode === 'Sea');
	frm.toggle_reqd('port_of_discharge', mode === 'Sea');
}

function show_status_dialog(frm) {
	let d = new frappe.ui.Dialog({
		title: __('Update Waybill Status'),
		fields: [
			{
				fieldname: 'status',
				fieldtype: 'Select',
				label: 'Status',
				options: [
					'Prepared',
					'Dispatched',
					'In Transit',
					'Arrived at Destination',
					'Out for Delivery',
					'Delivered'
				],
				reqd: 1
			},
			{
				fieldname: 'location',
				fieldtype: 'Data',
				label: 'Current Location'
			},
			{
				fieldname: 'remarks',
				fieldtype: 'Small Text',
				label: 'Remarks'
			}
		],
		primary_action_label: __('Update'),
		primary_action: function(values) {
			frappe.call({
				method: 'ksa_logistics.ksa_logistics.doctype.waybill.waybill.update_waybill_status',
				args: {
					waybill_name: frm.doc.name,
					status: values.status,
					location: values.location,
					remarks: values.remarks
				},
				callback: function(r) {
					if (r.message && r.message.success) {
						frappe.show_alert({
							message: r.message.message,
							indicator: 'green'
						});
						frm.reload_doc();
					}
				}
			});
			d.hide();
		}
	});
	d.show();
}

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

function show_tracking_dialog(frm) {
	let d = new frappe.ui.Dialog({
		title: __('Add Tracking Update'),
		fields: [
			{
				fieldname: 'status',
				fieldtype: 'Select',
				label: 'Status',
				options: [
					'Dispatched',
					'In Transit',
					'Checkpoint Passed',
					'Arrived',
					'Delay',
					'Issue'
				],
				reqd: 1
			},
			{
				fieldname: 'location',
				fieldtype: 'Data',
				label: 'Location',
				reqd: 1
			},
			{
				fieldname: 'remarks',
				fieldtype: 'Small Text',
				label: 'Remarks'
			}
		],
		primary_action_label: __('Add'),
		primary_action: function(values) {
			let row = frm.add_child('tracking_history');
			row.timestamp = frappe.datetime.now_datetime();
			row.status = values.status;
			row.location = values.location;
			row.remarks = values.remarks;
			row.updated_by = frappe.session.user;
			
			frm.refresh_field('tracking_history');
			frm.save();
			d.hide();
		}
	});
	d.show();
}

