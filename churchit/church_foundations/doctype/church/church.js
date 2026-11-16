// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Church", {
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
