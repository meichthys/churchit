// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Bible Translation", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Ready") {
			frm.add_custom_button(__("Read"), () =>
				frappe.set_route("bible", frm.doc.name),
			);
		}
		const is_api = frm.doc.source === "Free Use Bible API";
		if (is_api && frm.doc.status !== "Downloading") {
			const label =
				frm.doc.status === "No Text"
					? __("Download")
					: __("Download Again");
			frm.add_custom_button(label, () =>
				frm.call("download_again").then(() => frm.reload_doc()),
			);
		}
		const notes = {
			Downloading: [
				__(
					"The text is downloading. Reload in a minute to see it ready.",
				),
				"blue",
			],
			Failed: [
				__(
					"The download failed. Check the ID, then click Download Again.",
				),
				"red",
			],
			"No Text": is_api
				? [
						__(
							"The text downloads the first time someone reads this translation. Click Download to get it now.",
						),
						"orange",
					]
				: [
						__(
							"Attach this translation's text to read it in the app.",
						),
						"orange",
					],
		};
		if (notes[frm.doc.status]) frm.set_intro(...notes[frm.doc.status]);
	},
});
