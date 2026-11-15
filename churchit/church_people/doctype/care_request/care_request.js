// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Care Request", {
	refresh(frm) {
		add_suggestion_buttons(frm);
	},
	person(frm) {
		if (!frm.doc.person || frm.doc.caregiver) return;
		// If the person has a current care assignment, pre-fill Caregiver
		// with their assigned deacon. An assignment is current when it has
		// started and has no end date (or the end date is in the future).
		const today = frappe.datetime.nowdate();
		frappe.db
			.get_list("Care Assignment", {
				filters: { person: frm.doc.person, start_date: ["<=", today] },
				fields: ["deacon", "end_date"],
				order_by: "start_date desc",
				limit: 1,
			})
			.then((rows) => {
				if (!rows || !rows.length) return;
				const row = rows[0];
				if (row.deacon && (!row.end_date || row.end_date >= today)) {
					frm.set_value("caregiver", row.deacon);
				}
			});
	},
});

// AI's suggestion (churchit.ai.triage), for Pastoral Care and Church Managers. A Use button fills the
// form unsaved: the person checks it and saves. AI itself never changes the request or assigns it.
function add_suggestion_buttons(frm) {
	churchit.ai.show_suggestion(frm, (suggestion) => ({
		rows: [
			[__("Suggested Category"), suggestion.suggested_type],
			[__("Suggested Urgency"), suggestion.suggested_urgency],
		],
		uses: [
			["category", suggestion.suggested_type, __("Use Category")],
			["urgency", suggestion.suggested_urgency, __("Use Urgency")],
		]
			.filter(([fieldname, value]) => value && value !== frm.doc[fieldname])
			.map(([fieldname, value, label]) => [label, () => frm.set_value(fieldname, value)]),
		note: __(
			"AI suggests and never replies or assigns. Use a suggestion only after you check it."
		),
	}));
}
