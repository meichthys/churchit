// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt


frappe.ui.form.on('Function', {
	onload(frm) {
		church.set_church_doctype_query(frm, 'association_type', 'associations');
		church.set_church_doctype_query(frm, 'item_type', 'schedule');
	},

	refresh: function(frm) {
		// Customize the Sign-Up Items grid: hide my_quantity (irrelevant on Function)
		// and the description column; show quantity_needed and quantity_signed_up.
		const grid = frm.fields_dict.table_cxhh && frm.fields_dict.table_cxhh.grid;
		if (grid) {
			grid.update_docfield_property("quantity_needed", "in_list_view", 1);
			grid.update_docfield_property("quantity_signed_up", "in_list_view", 1);
			grid.update_docfield_property("my_quantity", "in_list_view", 0);
			grid.update_docfield_property("description", "in_list_view", 0);
			grid.set_column_disp("my_quantity", false);
			grid.set_column_disp("description", false);
			// Force re-evaluation of which columns are visible — by default the grid
			// caches `visible_columns` and won't pick up our docfield property changes.
			grid.reset_grid();
		}

		// Populate the virtual quantity_signed_up column for each Sign-Up Item row.
		populate_signed_up_totals(frm);

		// Add template-fill functionality if we have a template specified and this is a new form
		if (frm.is_new() && frm.doc.type) {
			frappe.db.get_value('Function Type', frm.doc.type, 'template_function').then(r => {
				if (!r.message?.template_function) return;
				// Add 	Fill from Template` button if template exists
				frm.add_custom_button(__('Fill from Template'), function() {
					frappe.call({
						method: 'church.church_ministries.doctype.function.function.apply_template',
						args: {
							source_name: r.message.template_function,
							target_doc: frm.doc
						},
						callback: function(r) {
							if (!r.message) return;
							Object.keys(r.message).forEach(fieldname => {
								frm.set_value(fieldname, r.message[fieldname]);
							});

							// Fetch link titles for person IDs so the attendance grid
							// displays names instead of IDs (e.g. "John Smith" not "PRSN-0011")
							const personIds = [...new Set(
								(r.message.attendance || []).map(a => a.person).filter(Boolean)
							)];
							if (personIds.length) {
								Promise.all(personIds.map(id => frappe.utils.fetch_link_title('Person', id)))
									.then(() => frm.refresh_field('attendance'));
							}

							frappe.msgprint({
								message: __('Template applied successfully'),
								indicator: 'green',
								alert: true
							});
						}
					});
				});
			});
		}

		// Allow booking a room for this saved function (the Room Booking links back to it)
		if (!frm.is_new()) {
			frm.add_custom_button(__('Book a Room'), function() {
				let start_dt = null, end_dt = null;
				if (frm.doc.start_date) {
					const stime = frm.doc.all_day ? '00:00:00' : (frm.doc.start_time || '00:00:00');
					start_dt = frm.doc.start_date + ' ' + stime;
					const edate = frm.doc.end_date || frm.doc.start_date;
					const etime = frm.doc.all_day ? '23:59:59' : frm.doc.end_time;
					if (etime) {
						end_dt = edate + ' ' + etime;
					}
					// Room Booking requires end > start; default to a 1-hour slot otherwise
					if (!end_dt || end_dt <= start_dt) {
						end_dt = frappe.datetime.add_to_date(start_dt, { hours: 1 });
					}
				}
				frappe.new_doc('Room Booking', {
					function: frm.doc.name,
					purpose: frm.doc.function_name || frm.doc.type,
					start_datetime: start_dt,
					end_datetime: end_dt,
				});
			}, __('Create'));
		}

		// Add Sign Ups buttons if sign-ups are enabled, there are items, or there are linked sign-ups
		if (!frm.is_new()) {
			const has_items = frm.doc.table_cxhh && frm.doc.table_cxhh.length > 0;

			frappe.db.count('Function Sign-Up', {
				filters: { function: frm.doc.name }
			}).then(count => {
				if (frm.doc.allow_sign_ups || has_items || count > 0) {
					frm.add_custom_button(__('Show Signed-Up Items'), function() {
						frappe.set_route('query-report', 'Function Sign-Up Items', {
							function: frm.doc.name
						});
					}, __('Sign Ups'));

					frm.add_custom_button(__('Show Signed-Up People'), function() {
						frappe.set_route('list', 'Function Sign-Up', {
							function: frm.doc.name
						});
					}, __('Sign Ups'));
				}
			});
		}
	},


	type: function(frm) {
		// Refresh form to re-evaluate button visibility
		frm.trigger('refresh');
	},
});

// Set default attendance_type on new attendance child rows
frappe.ui.form.on('Function Attendance', {
	attendance_add(frm, cdt, cdn) {
		frappe.db.get_value("Function Attendance Type", { type: "Confirmed" }, "name").then(r => {
			if (r.message?.name) {
				frappe.model.set_value(cdt, cdn, "attendance_type", r.message.name);
			}
		});
	}
});

function populate_signed_up_totals(frm) {
	if (frm.is_new() || !frm.doc.name || !(frm.doc.table_cxhh || []).length) return;
	frappe.call({
		method:
			"church.church_ministries.doctype.function_sign_up.function_sign_up.get_function_item_totals",
		args: { function: frm.doc.name },
		callback: function (r) {
			if (!r.message) return;
			(frm.doc.table_cxhh || []).forEach((row) => {
				const data = r.message[row.item];
				if (!data) return;
				row.quantity_signed_up = data.quantity_signed_up;
			});
			frm.refresh_field("table_cxhh");
		},
	});
}
