// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Church", {
	onload(frm) {
		// A new Address takes Personal as its type and no title, which suit a person but not the
		// church. The quick entry puts a field's default back over route options, so set them on it.
		const address = frm.fields_dict.address;
		address.new_doc = () => {
			frappe.ui.form
				.make_quick_entry("Address", (doc) =>
					address.set_value(doc.name),
				)
				.then((quick_entry) => {
					if (!quick_entry.fields_dict) return; // Address opened as a full form
					quick_entry.set_values({
						address_title: frm.doc.church_name,
						address_type: "Office",
					});
				});
			return false;
		};
	},
	refresh(frm) {
		if (frm.doc.publish) {
			frm.set_intro(
				"🌐 This church is published to the public website",
				"blue",
			);
		}

		// Whether AI is in use, under Keep This Church Away From AI (churchit.ai.opt_outs).
		const ai_state = frm.doc.__onload?.ai_state;
		frm.get_field("ai_status").$wrapper.html(
			ai_state
				? `<p class="text-muted small">${frappe.utils.escape_html(ai_state)}</p>`
				: "",
		);
	},
});
