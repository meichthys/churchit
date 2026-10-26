// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Room Booking", {
	refresh(frm) {
		show_decision_buttons(frm);
		set_setup_options(frm);
		show_questions_button(frm);
	},
	room(frm) {
		set_setup_options(frm);
		ask_room_questions(frm);
	},
	// A blocked time asks nothing; leaving Blocked asks the room's questions again.
	status(frm) {
		if (frm.doc.status === "Blocked" || !frm.custom_buttons[__("Answer Questions")]) {
			ask_room_questions(frm);
		}
	},
});

function show_decision_buttons(frm) {
	// The server says who approves the room, so an approver with no To Do decides too.
	if (frm.is_new() || !frm.doc.__onload?.is_approver) return;

	const decide = (method, args) => frm.call(method, args).then(() => frm.reload_doc());
	if (frm.doc.status === "Requested") {
		frm.add_custom_button(__("Approve"), () => decide("approve"), __("Decide"));
		frm.add_custom_button(__("Deny"), () => decide("deny"), __("Decide"));
	}
	if (frm.doc.status === "Conflict") {
		frm.add_custom_button(
			__("Keep This Booking"),
			() =>
				frappe.confirm(
					__("Approve this booking and deny the requests it clashes with?"),
					() => decide("resolve_conflict", { action: "keep" })
				),
			__("Resolve")
		);
		frm.add_custom_button(
			__("Share the Room"),
			() => decide("resolve_conflict", { action: "share" }),
			__("Resolve")
		);
	}
}

function set_setup_options(frm) {
	const setups = frm.doc.room
		? frappe.db
				.get_doc("Room", frm.doc.room)
				.then((room) => room.setups.map((row) => row.setup_name))
		: Promise.resolve([]);
	setups.then((names) => {
		frm.set_df_property("setup", "options", names);
		// The Autocomplete reads its options only when it draws its input.
		frm.get_field("setup").set_data(names);
	});
}

function show_questions_button(frm) {
	if (!frm.doc.room || frm.doc.status === "Blocked") return;
	get_room_questions(frm).then((fields) => {
		if (!fields.length) return;
		frm.add_custom_button(__("Answer Questions"), () => open_room_questions(frm, fields));
	});
}

// Answers to the old room's questions go with it, and so does its button.
function ask_room_questions(frm) {
	frm.remove_custom_button(__("Answer Questions"));
	frm.clear_table("answers");
	frm.refresh_field("answers");
	const room = frm.doc.room;
	if (!room || frm.doc.status === "Blocked") return;
	get_room_questions(frm).then((fields) => {
		if (!fields.length || frm.doc.room !== room || frm.doc.status === "Blocked") return;
		frm.add_custom_button(__("Answer Questions"), () => open_room_questions(frm, fields));
		open_room_questions(frm, fields);
	});
}

function get_room_questions(frm) {
	return frappe.xcall(
		"churchit.church_operations.doctype.room_booking.room_booking.get_room_questions",
		{ room: frm.doc.room },
		"GET"
	);
}

// One Answers row for each answer; the server checks them against the room's set again.
function open_room_questions(frm, fields) {
	const dialog = new frappe.ui.Dialog({
		title: __("Room Questions"),
		primary_action_label: __("Done"),
		primary_action() {
			const values = group.get_values();
			if (!values) return;
			frm.clear_table("answers");
			for (const [question, answer] of Object.entries(values)) {
				frm.add_child("answers", { question, answer: String(answer) });
			}
			frm.refresh_field("answers");
			dialog.hide();
		},
	});
	const group = churchit.questions.render(dialog.body, fields);
	const given = {};
	for (const field of fields) {
		const row = (frm.doc.answers || []).find((row) => row.question === field.fieldname);
		if (!row) continue;
		given[field.fieldname] =
			field.fieldtype === "Check" ? cint(row.answer === "Yes") : row.answer;
	}
	group.set_values(given);
	dialog.show();
}
