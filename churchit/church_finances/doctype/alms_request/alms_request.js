// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Alms Request", {
	recipient_type: function (frm) {
		// Dynamically update the Recipient field description based on the Recipient Type that is selected
		if (frm.doc.recipient_type) {
			frm.set_df_property(
				"recipient",
				"description",
				`Alms are requested for this ${frm.doc.recipient_type}.`
			);
		}
	},
	refresh(frm) {
		// One expense per request, for whoever keeps the books
		if (!frm.is_new() && !frm.doc.associated_expense && frappe.model.can_create("Expense")) {
			frm.add_custom_button(__("Create Expense"), function () {
				frappe.call({
					method: "churchit.church_finances.doctype.alms_request.alms_request.create_expense",
					args: { alms_request_name: frm.doc.name },
					callback: function () {
						frm.reload_doc();
					},
				});
			});
		}
		add_case_note_buttons(frm);
	},
	onload: function (frm) {
		// Pre-populate the requestor field with the current user's name
		if (frm.is_new()) {
			frappe.db.get_value("Person", { user: frappe.session.user }, "name").then((r) => {
				if (r && r.message) {
					frm.set_value("requestor", r.message.name);
				}
			});
		}
	},
	after_save: function (frm) {
		// Prompt user to create an expense when status is set to "Distributed"
		if (
			frm.doc.status === "Distributed" &&
			!frm.doc.associated_expense &&
			frappe.model.can_create("Expense")
		) {
			frappe.confirm("Would you like to create an associated expense?", function () {
				frappe.call({
					method: "churchit.church_finances.doctype.alms_request.alms_request.create_expense",
					args: {
						alms_request_name: frm.doc.name,
					},
					callback: function () {
						frm.reload_doc();
					},
				});
			});
		}
	},
});

// Benevolence case notes are Person Notes on the recipient, or on a Family's primary contact.
// The note's category decides who reads it, so Church Finance, which reads no Person Note, gets no button.
function add_case_note_buttons(frm) {
	if (frm.is_new() || !frm.doc.recipient || !frappe.model.can_read("Person Note")) return;
	const group = __("Case Notes");
	frm.add_custom_button(
		__("View Case Notes"),
		async () => {
			const person = await get_case_note_person(frm);
			frappe.set_route("List", "Person Note", { person, category: "Benevolence" });
		},
		group
	);
	if (!frappe.model.can_create("Person Note")) return;
	frm.add_custom_button(
		__("Add Case Note"),
		async () => {
			const note = frappe.model.get_new_doc("Person Note");
			note.person = await get_case_note_person(frm);
			note.category = "Benevolence";
			const set_category_query = (dialog) => {
				dialog.fields_dict.category.get_query = () => ({
					query: "churchit.church_people.notes.search_categories_to_add",
				});
			};
			frappe.ui.form.make_quick_entry("Person Note", null, set_category_query, note, true);
		},
		group
	);
}

async function get_case_note_person(frm) {
	if (frm.doc.recipient_type === "Person") return frm.doc.recipient;
	const { message } = await frappe.db.get_value("Family", frm.doc.recipient, "primary_contact");
	return message?.primary_contact || frm.doc.requestor;
}
