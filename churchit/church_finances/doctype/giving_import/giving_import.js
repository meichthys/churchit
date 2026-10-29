// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// An import keeps no records. Data Import's log links each row here, so open the Collection it went into.
frappe.ui.form.on("Giving Import", {
	refresh(frm) {
		frappe.set_route("Form", "Collection", frm.doc.name);
	},
});
