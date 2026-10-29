// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// A QR code of a published web form's address, to print on a bulletin or a welcome card.
frappe.ui.form.on("Web Form", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.published) return;
		frm.add_custom_button(__("QR Code"), () => show_qr_code(frm));
	},
});

function show_qr_code(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("QR Code"),
		fields: [
			{
				fieldname: "church",
				fieldtype: "Link",
				options: "Church",
				label: __("Church"),
				description: __(
					"Guests who scan the code fill in the form for this church. Leave it empty for the main church."
				),
				hidden: !frappe.boot.churchit?.multi_church,
				get_query: () => ({ filters: { publish: 1 } }),
				onchange: () => render_qr_code(dialog, frm),
			},
			{ fieldname: "qr_code", fieldtype: "HTML" },
		],
		primary_action_label: __("Download"),
		primary_action: () => download_qr_code(dialog, frm),
	});
	dialog.show();
	render_qr_code(dialog, frm);
}

// The form's new-entry page: Frappe drops the query string when it redirects from the bare route.
function get_form_address(frm, church) {
	const address = `${frappe.urllib.get_base_url()}/${frm.doc.route}/new`;
	return church ? `${address}?church=${encodeURIComponent(church)}` : address;
}

async function render_qr_code(dialog, frm) {
	const address = get_form_address(frm, dialog.get_value("church"));
	const image = await frappe.xcall("frappe.utils.print_format_generator.get_qr_code", {
		value: address,
	});
	dialog.qr_code = image;
	const safe_address = frappe.utils.escape_html(address);
	// The code is black on clear, so it keeps a white ground in the dark theme.
	dialog.fields_dict.qr_code.$wrapper.html(`
		<div class="text-center">
			<img src="${image}" alt="${__("QR code")}"
				style="width: 240px; height: 240px; padding: 8px; background: white">
			<p class="small"><a href="${safe_address}" target="_blank">${safe_address}</a></p>
		</div>
	`);
}

function download_qr_code(dialog, frm) {
	if (!dialog.qr_code) return;
	const link = document.createElement("a");
	link.href = dialog.qr_code;
	link.download = `${frm.doc.route}-qr-code.svg`;
	link.click();
}
