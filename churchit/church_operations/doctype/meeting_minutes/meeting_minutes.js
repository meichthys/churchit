// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Meeting Minutes", {
	setup(frm) {
		frm.set_df_property("audio_recording", "options", {
			restrictions: { allowed_file_types: ["audio/*"] },
		});
	},
	refresh(frm) {
		render_audio_player(frm);
	},
	audio_recording(frm) {
		render_audio_player(frm);
	},
	function(frm) {
		if (!frm.doc.function) return;
		frappe.db.get_doc("Function", frm.doc.function).then((fn) => {
			const attendance = fn.attendance || [];
			if (!attendance.length) {
				frappe.show_alert({
					message: __("No attendees found on that function."),
					indicator: "orange",
				});
				return;
			}
			// Merge: add anyone not already in the attendees table
			const existing = new Set((frm.doc.attendees || []).map((r) => r.person));
			let added = 0;
			attendance.forEach((row) => {
				if (row.person && !existing.has(row.person)) {
					const child = frm.add_child("attendees");
					child.person = row.person;
					added++;
				}
			});
			if (added) {
				frm.refresh_field("attendees");
				frappe.show_alert({
					message: __("{0} attendee(s) added from function.", [added]),
					indicator: "green",
				});
			} else {
				frappe.show_alert({
					message: __("All function attendees are already listed."),
					indicator: "blue",
				});
			}
		});
	},
});

function render_audio_player(frm) {
	const wrapper = frm.get_field("audio_player").$wrapper;
	if (!frm.doc.audio_recording) {
		wrapper.empty();
		return;
	}
	const src = frappe.utils.escape_html(frm.doc.audio_recording);
	wrapper.html(`<audio controls preload="none" style="width: 100%" src="${src}"></audio>`);
}
