// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Prayer Request", {
	refresh(frm) {
		if (frm.doc.visibility === "Private") {
			frm.set_intro(
				__("This request is private. Do not share it with the prayer team or the church."),
				"yellow"
			);
		} else if (frm.doc.visibility === "Prayer Team") {
			frm.set_intro(
				__("Only the prayer team may see this request. Do not share it with the church."),
				"blue"
			);
		}
		add_suggestion_buttons(frm);
	},
	onload: function (frm) {
		// Filter recipient_type to DocTypes in the church app
		church.set_church_doctype_query(frm, "recipient_type");

		if (frm.is_new()) {
			// Pre-populate the requestor field with the current user's name
			frappe.db.get_value("Person", { user: frappe.session.user }, "name").then((r) => {
				if (r && r.message) {
					frm.set_value("requestor", r.message.name);
				}
			});
			// Set default status
			if (!frm.doc.status) {
				frappe.db
					.get_value("Prayer Request Status", { status: "Requested" }, "name")
					.then((r) => {
						if (r && r.message) {
							frm.set_value("status", r.message.name);
						}
					});
			}
		}
	},
});

// AI's suggestion (churchit.ai.triage), for Pastoral Care and Church Managers. A Use button fills the
// form unsaved and the person saves; the suggested wording is only copied, so the request keeps its
// own text. An unclear answer leaves Suggested as Urgent unticked, so Use Urgency only marks urgent.
function add_suggestion_buttons(frm) {
	churchit.ai.show_suggestion(frm, (suggestion) => {
		const uses = [
			["type", suggestion.suggested_type, __("Use Type")],
			["urgent", suggestion.suggested_urgent ? 1 : null, __("Use Urgency")],
		]
			.filter(([fieldname, value]) => value && value !== frm.doc[fieldname])
			.map(([fieldname, value, label]) => [label, () => frm.set_value(fieldname, value)]);
		if (suggestion.public_wording) {
			uses.push([
				__("Copy Wording"),
				() => frappe.utils.copy_to_clipboard(suggestion.public_wording),
			]);
		}
		return {
			rows: [
				[__("Suggested Type"), suggestion.suggested_type],
				[__("Suggested as Urgent"), suggestion.suggested_urgent ? __("Yes") : null],
				[__("Flags"), (suggestion.suggested_flags || "").split("\n").join(", ")],
				[__("Suggested Wording"), suggestion.public_wording],
			],
			uses,
			note: __(
				"AI never replies to a prayer request and can miss a risk. Read every request."
			),
		};
	});
}
