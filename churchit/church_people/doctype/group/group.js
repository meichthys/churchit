// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Group", {
	refresh(frm) {
		const grid = frm.fields_dict.members.grid;
		// Frappe prepends custom buttons; append so "Add row" stays first.
		grid.add_custom_button(__("Email Group"), () => email_members(frm, false)).appendTo(
			grid.grid_buttons
		);
		grid.add_custom_button(__("Email Selected"), () => email_members(frm, true)).appendTo(
			grid.grid_buttons
		);

		if (!frm.is_new() && frappe.model.can_create("Church Email")) {
			frm.add_custom_button(
				__("Send Church Email"),
				() =>
					frappe.new_doc("Church Email", {
						send_to: "Group",
						group: frm.doc.name,
						church: frm.doc.church,
					}),
				__("Actions")
			);
		}

		if (!frm.is_new() && frappe.model.can_create("Function")) {
			frm.add_custom_button(
				__("Set Up Meetings"),
				() =>
					frappe.new_doc("Function", {
						function_name: frm.doc.group_name,
						group: frm.doc.name,
						type: "Group Meeting",
						auto_repeat: 1,
						church: frm.doc.church,
					}),
				__("Actions")
			);
		}
	},

	group_type(frm) {
		// A copy the user can change: the server copies nothing, as an unticked box looks unset.
		if (!frm.doc.group_type) return;
		frappe.db
			.get_value("Group Type", frm.doc.group_type, [
				"public",
				"show_in_portal",
				"requires_approval",
				"capacity",
			])
			.then(({ message }) => message && frm.set_value(message));
	},
});

function email_members(frm, selected_only) {
	const grid = frm.fields_dict.members.grid;
	const rows = selected_only ? grid.get_selected_children() : frm.doc.members || [];
	const persons = rows.map((r) => r.person).filter(Boolean);

	if (!persons.length) {
		frappe.msgprint(
			selected_only
				? __("Please select at least one member.")
				: __("No members in this group.")
		);
		return;
	}

	frappe.call({
		method: "churchit.contacts.get_emails_for",
		args: {
			parenttype: "Person",
			parents: persons,
		},
		callback(r) {
			const { emails = [], missing = [] } = r.message || {};

			if (missing.length) {
				frappe.msgprint({
					title: __("Missing Email Addresses"),
					indicator: "orange",
					message:
						__(
							"⚠️ The following members have no email address and will not be included:"
						) +
						"<ul>" +
						missing.map((n) => `<li>${n}</li>`).join("") +
						"</ul>",
				});
			}

			window.location.href = "mailto:" + emails.join(",");
		},
	});
}
