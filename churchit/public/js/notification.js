// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// Outside developer mode a shipped notification that is off cannot be turned on, only a copy of it.
frappe.ui.form.on("Notification", {
	refresh(frm) {
		if (
			!frm.doc.is_standard ||
			frm.doc.enabled ||
			frappe.boot.developer_mode
		)
			return;
		frm.set_intro(
			__(
				"This notification ships with the app, so you cannot turn it on or change it here. To use it, click the ... menu, then Duplicate. Tick Enabled on the copy and save it.",
			),
			"blue",
		);
	},
});
