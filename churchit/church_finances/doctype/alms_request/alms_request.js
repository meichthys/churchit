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
		// One submitted expense per request, for whoever keeps the books, once it has an amount to pay
		if (
			!frm.is_new() &&
			!(frm.doc.__onload || {}).is_paid &&
			frm.doc.amount > 0 &&
			frappe.model.can_create("Expense")
		) {
			frm.add_custom_button(__("Create Expense"), () => create_expense(frm), __("Actions"));
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
			!(frm.doc.__onload || {}).is_paid &&
			!frm.creating_expense &&
			frappe.model.can_create("Expense")
		) {
			frappe.confirm(__("Record this gift as an Expense now?"), () => create_expense(frm));
		}
	},
});

function create_expense(frm) {
	if (frm.doc.expense_type) return call_create_expense(frm);

	frappe.prompt(
		{
			fieldname: "expense_type",
			fieldtype: "Link",
			options: "Expense Type",
			label: __("Expense Type"),
			reqd: 1,
		},
		({ expense_type }) => {
			// This save asks nothing in after_save: the expense follows it
			frm.creating_expense = true;
			frm.set_value("expense_type", expense_type);
			frm.save().then(() => {
				frm.creating_expense = false;
				if (!frm.is_dirty()) call_create_expense(frm);
			});
		},
		__("Create Expense"),
		__("Create")
	);
}

function call_create_expense(frm) {
	frappe.call({
		method: "churchit.church_finances.doctype.alms_request.alms_request.create_expense",
		args: { alms_request_name: frm.doc.name },
		callback: (r) => {
			frm.reload_doc();
			frappe.show_alert({
				message: __("Expense {0} is created and submitted.", [
					frappe.utils.get_form_link("Expense", r.message, true),
				]),
				indicator: "green",
			});
		},
	});
}

// Benevolence case notes are Person Notes on the recipient, or on a Family's primary contact.
// The server says whether the user may read or add a Benevolence note.
function add_case_note_buttons(frm) {
	const onload = frm.doc.__onload || {};
	if (frm.is_new() || !frm.doc.recipient || !onload.can_read_case_notes) return;
	frm.add_custom_button(
		__("Case Notes"),
		async () => {
			const person = await get_case_note_person(frm);
			frappe.set_route("List", "Person Note", { person, category: "Benevolence" });
		},
		__("View")
	);
	if (!onload.can_add_case_notes) return;
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
		__("Actions")
	);
}

async function get_case_note_person(frm) {
	if (frm.doc.recipient_type === "Person") return frm.doc.recipient;
	const { message } = await frappe.db.get_value("Family", frm.doc.recipient, "primary_contact");
	return message?.primary_contact || frm.doc.requestor;
}
