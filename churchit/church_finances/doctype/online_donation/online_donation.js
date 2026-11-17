// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Online Donation", {
	setup(frm) {
		// A gift goes only to its church's funds or shared ones (OnlineDonation.validate).
		frm.set_query("fund", () => {
			const church_name =
				church.is_multi_church() && (frm.doc.church || frappe.boot.churchit.church);
			// An empty filter set makes the picker say "Filtered by: ." with nothing named.
			return church_name ? { filters: { church: ["in", [church_name, ""]] } } : {};
		});
	},

	refresh(frm) {
		if (frm.doc.status !== "Pending" || !frappe.user.has_role("Church Finance")) return;
		frm.add_custom_button(__("Record Charged Gift"), () =>
			frm.call("record_charged_gift").then(() => frm.reload_doc())
		);
	},
});
