// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Belief", {
	refresh(frm) {
		//Add an 'intro' indicating if a belief is published to the website
		if (frm.doc.publish) {
			frm.set_intro("🌐 This belief is published to the public website", "blue");
		}
	},
});
