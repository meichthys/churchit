// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Church Task", {
	onload(frm) {
		// The Work Orders connection of an asset or room opens a new task with only the link set.
		if (frm.is_new() && (frm.doc.asset || frm.doc.room)) {
			frm.set_value("task_type", "Work Order");
		}
	},
});
