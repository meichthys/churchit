// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Belief", {
	refresh(frm) {
        //Add an 'intro' indicating if a belief is published to the website
        if(frm.doc.publish) {
            frm.set_intro('🌐 This belief is published to the public website', 'blue');
        }
	},
});
