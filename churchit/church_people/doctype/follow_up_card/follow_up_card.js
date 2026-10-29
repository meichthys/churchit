// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Follow-up Card", {
	refresh(frm) {
		render_contact_details(frm);
		if (frm.is_new() || frm.doc.status !== "Open" || !frm.has_perm("write")) return;

		for (const step of frm.doc.__onload?.steps || []) {
			if (step === frm.doc.step) continue;
			frm.add_custom_button(step, () => save_with(frm, { step }), __("Move To"));
		}
		frm.add_custom_button(__("Snooze"), () => snooze(frm));
		frm.add_custom_button(__("Close"), () => close_card(frm));
	},
});

function render_contact_details(frm) {
	const contact = frm.doc.__onload?.contact;
	if (!contact) {
		frm.get_field("contact_details").$wrapper.empty();
		return;
	}
	const phone = contact.phone
		? `<a href="tel:${encodeURIComponent(contact.phone)}">${frappe.utils.escape_html(
				contact.phone
		  )}</a>`
		: __("No phone number on file");
	const email = contact.email
		? `<a href="mailto:${encodeURIComponent(contact.email)}">${frappe.utils.escape_html(
				contact.email
		  )}</a>`
		: __("No email address on file");
	frm.get_field("contact_details").$wrapper.html(`
		<p class="text-muted small">${__("Contact Details")}</p>
		<p>${phone}<br>${email}</p>`);
}

function save_with(frm, values) {
	frm.set_value(values).then(() => frm.save());
}

function snooze(frm) {
	frappe.prompt(
		{
			fieldname: "snoozed_until",
			fieldtype: "Date",
			label: __("Snooze Until"),
			default: frappe.datetime.add_days(frappe.datetime.get_today(), 7),
			reqd: 1,
		},
		(values) => save_with(frm, values),
		__("Snooze Card"),
		__("Snooze")
	);
}

function close_card(frm) {
	frappe.prompt(
		{
			fieldname: "outcome",
			fieldtype: "Small Text",
			label: __("Outcome"),
			description: __("What happened, for whoever reads this card later."),
			default: frm.doc.outcome,
		},
		(values) => save_with(frm, { status: "Closed", outcome: values.outcome || "" }),
		__("Close Card"),
		__("Close")
	);
}
