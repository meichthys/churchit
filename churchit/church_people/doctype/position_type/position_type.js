// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Position Type", {
	refresh(frm) {
		if (!frm.is_new() && frappe.model.can_write("Person")) {
			frm.add_custom_button(__("Assign to Person"), () => assign_to_person(frm));
		}
	},
});

function assign_to_person(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Assign {0} to Person", [frm.doc.position]),
		fields: [
			{
				fieldname: "person",
				fieldtype: "Link",
				label: __("Person"),
				options: "Person",
				reqd: 1,
			},
			{
				fieldname: "start_date",
				fieldtype: "Date",
				label: __("Start Date"),
				default: frappe.datetime.get_today(),
			},
			{
				fieldname: "end_date",
				fieldtype: "Date",
				label: __("End Date"),
			},
			{
				fieldname: "notes",
				fieldtype: "Small Text",
				label: __("Notes"),
			},
		],
		primary_action_label: __("Assign"),
		primary_action(values) {
			frappe
				.call({
					method: "churchit.church_people.doctype.position_type.position_type.assign_position_to_person",
					args: {
						position_type: frm.doc.name,
						person: values.person,
						start_date: values.start_date || null,
						end_date: values.end_date || null,
						notes: values.notes || "",
					},
				})
				.then(() => {
					dialog.hide();
					frappe.show_alert({
						message: __("Position assigned to {0}", [values.person]),
						indicator: "green",
					});
					frm.reload_doc();
				});
		},
	});
	dialog.show();
}
