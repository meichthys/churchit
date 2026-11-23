// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// The photo of the paper card above the form, so a person can check an AI draft against it or copy
// the card by hand (Copy by Hand on the Connection Card Photo).
frappe.ui.form.on("Connection Card", {
	refresh: show_card_photo,
	card_photo: show_card_photo,
});

function show_card_photo(frm) {
	const doctype = "Connection Card Photo";
	frm.dashboard.parent.find(".card-photo-section").remove();
	if (!frm.doc.card_photo || !frappe.model.can_read(doctype)) return;

	const name = frm.doc.card_photo;
	frappe.db.get_value(doctype, name, "photo").then(({ message }) => {
		const url = message?.photo;
		if (!url || frm.doc.card_photo !== name) return;
		const src = encodeURI(url);
		frm.dashboard.parent.find(".card-photo-section").remove();
		frm.dashboard.add_section(
			`<a href="${src}" target="_blank" rel="noopener"><img src="${src}"
				alt="${frappe.utils.escape_html(__("Card photo"))}"
				style="max-width: 100%; max-height: 24rem; object-fit: contain;"></a>
			<p class="text-muted small">${frappe.utils.escape_html(
				__("Click the photo to open it at full size."),
			)}</p>`,
			__("Card Photo"),
			"custom card-photo-section",
		);
		frm.dashboard.show();
	});
}
