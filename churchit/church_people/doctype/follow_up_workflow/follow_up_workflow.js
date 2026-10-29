// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// What each trigger's "Which" names, so its picker opens the right list. The server sets it again on save.
const VALUE_TYPES = {
	"Connection Card": "Connection Card Interest",
	"First Check-In": "Function Type",
	"Life Event Added": "Life Event Type",
	"Membership Type Becomes": "Membership Type",
	"Member Status Becomes": "Member Status",
	"On Smart List": "Report",
	"Signed Up": "Function Type",
	"Form Submitted": "Question Set",
	"Step Reached": "Follow-up Workflow",
	"Card Closed": "Follow-up Workflow",
};

frappe.ui.form.on("Follow-up Workflow", {
	setup(frm) {
		frm.set_query("value", "triggers", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			if (VALUE_TYPES[row.trigger] === "Follow-up Workflow") {
				const filters = { name: ["!=", doc.name] };
				if (doc.church) filters.church = doc.church;
				return { filters };
			}
			if (row.trigger !== "On Smart List") return {};
			return { query: "churchit.church_people.smart_lists.search_smart_lists" };
		});
	},
	refresh(frm) {
		if (!frm.doc.kanban_board) return;
		frm.add_custom_button(__("Open Board"), () =>
			frappe.set_route("List", "Follow-up Card", "Kanban", frm.doc.kanban_board)
		);
	},
});

frappe.ui.form.on("Follow-up Trigger", {
	trigger(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, {
			value_type: VALUE_TYPES[locals[cdt][cdn].trigger] || "",
			value: "",
			step: "",
		});
	},
});
