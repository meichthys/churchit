// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Bulletin", {
	setup(frm) {
		frm.set_query("prayer_request", "prayer_requests", () => ({
			filters: { is_private: 0, status: ["not in", ["Answered", "Archived", "Closed"]] },
		}));
	},

	onload(frm) {
		if (frm.is_new()) {
			fill_defaults(frm, { sections: true });
		}
	},

	refresh(frm) {
		if (frm.doc.publish) {
			frm.set_intro(__("Members can download this bulletin from the portal."), "blue");
		}
		if (!frm.is_new()) {
			frm.add_custom_button(__("Print Bulletin"), () => frm.print_doc());
		}
	},

	function(frm) {
		if (frm.doc.function) {
			fill_defaults(frm, { sections: frm.is_new() });
		}
	},
});

function fill_defaults(frm, { sections }) {
	frappe
		.call({
			method: "churchit.church_communications.doctype.bulletin.bulletin.get_defaults",
			args: { function: frm.doc.function },
		})
		.then((r) => {
			const defaults = r.message;
			for (const [field, value] of Object.entries(defaults)) {
				if (field === "prayer_requests" || (!sections && field.startsWith("show_")))
					continue;
				frm.set_value(field, value);
			}
			if (!frm.doc.function) return;
			frm.clear_table("prayer_requests");
			defaults.prayer_requests.forEach((row) => frm.add_child("prayer_requests", row));
			frm.refresh_field("prayer_requests");
		});
}
