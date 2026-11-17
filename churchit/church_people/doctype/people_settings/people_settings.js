// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("People Settings", {
	refresh(frm) {
		// The server refuses the save (church_access.refuse_changing_shared_settings); this says so up front.
		if (frm.doc.__onload?.has_every_church !== false) return;
		frm.disable_form();
		frm.set_intro(
			__(
				"People Settings apply to every church. Only someone who works across every church can change them."
			),
			"blue"
		);
	},
});
