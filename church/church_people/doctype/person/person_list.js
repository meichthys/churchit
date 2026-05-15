frappe.listview_settings["Person"] = {
	onload(listview) {
		listview.page.add_action_item(__("Check In"), () => bulk_check_in(listview));
	},
};

function bulk_check_in(listview) {
	const selected = listview.get_checked_items();
	if (!selected.length) {
		frappe.msgprint(__("Select at least one person."));
		return;
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Check In"),
		fields: [
			{
				fieldtype: "Link",
				fieldname: "function",
				label: __("Function"),
				options: "Function",
				reqd: 1,
			},
		],
		primary_action_label: __("Check In"),
		primary_action(values) {
			frappe.call({
				method: "church.church_ministries.doctype.function_check_in.function_check_in.check_in_persons",
				args: {
					function_name: values.function,
					persons: selected.map((p) => p.name),
				},
				callback(r) {
					if (!r.exc) {
						frappe.show_alert({
							message: __("{0} person(s) checked in.", [selected.length]),
							indicator: "green",
						});
						dialog.hide();
						listview.refresh();
					}
				},
			});
		},
	});
	dialog.show();
}
