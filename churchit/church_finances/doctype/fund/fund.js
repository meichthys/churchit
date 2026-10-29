// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Fund", {
	onload: function (frm) {
		sort_transactions_by_date(frm);
	},
	refresh: function (frm) {
		if (frm.is_new() || !frm.doc.allow_giving) return;
		frm.add_custom_button(__("Give Link"), () => show_give_link(frm));
	},
});

function sort_transactions_by_date(frm) {
	// Sort descending
	frm.doc.transactions.sort((a, b) => {
		const dateA = new Date(a.date);
		const dateB = new Date(b.date);
		return dateB - dateA;
	});

	frm.refresh_field("transactions");
}

// The /give address that chooses this fund, as a link, a QR code to print, or the text of an NFC tag.
async function show_give_link(frm) {
	const link = await frappe.xcall("churchit.church_finances.doctype.fund.fund.get_give_link", {
		fund: frm.doc.name,
	});
	const safe_url = frappe.utils.escape_html(link.url);
	const dialog = new frappe.ui.Dialog({
		title: __("Give Link"),
		fields: [
			{
				fieldname: "give_link",
				fieldtype: "HTML",
				// The code is black on clear, so it keeps a white ground in the dark theme.
				options: `
					<div class="text-center">
						<img src="${link.qr_code}" alt="${__("QR code")}"
							style="width: 240px; height: 240px; padding: 8px; background: white">
						<p class="small"><a href="${safe_url}" target="_blank">${safe_url}</a></p>
						<p class="small text-muted">${__(
							"Add {0} to the address to fill in an amount. Write the address on an NFC tag for tap to give.",
							["<code>&amp;amount=25</code>"]
						)}</p>
					</div>
				`,
			},
		],
		primary_action_label: __("Download QR Code"),
		primary_action: () => {
			const download = document.createElement("a");
			download.href = link.qr_code;
			download.download = `${frm.doc.name}-give-qr-code.svg`;
			download.click();
		},
		secondary_action_label: __("Copy Link"),
		secondary_action: () => frappe.utils.copy_to_clipboard(link.url),
	});
	dialog.show();
}
