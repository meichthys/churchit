frappe.ui.form.on("Missionary Support Schedule", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(
				__("Recalculate"),
				() => {
					frm.call("recalculate").then((r) => {
						if (!r.exc) {
							frm.reload_doc();
							frappe.show_alert({
								message: __("Recalculated successfully"),
								indicator: "green",
							});
						}
					});
				},
				__("Actions")
			);
		}
	},
});
