// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Giving Settings", {
	refresh(frm) {
		// A gateway row links to the payments app's Payment Gateway, which is missing without the app.
		const is_payments_on = frm.doc.__onload?.is_payments_on;
		frm.set_df_property("gateways", "read_only", is_payments_on ? 0 : 1);
		const notes = [];
		if (!is_payments_on) {
			notes.push(
				__(
					"Online payments are off, because the Payments app is not installed on this site. Gifts on the Give page, sign-up payments and form payments need it. The {0} tells how to install it.",
					[`<a href="/app/manual%3A-finances">${__("Finances manual")}</a>`]
				)
			);
		}
		if (lock_shared_settings(frm)) {
			notes.push(
				__(
					"These settings apply to every church. Only someone who works across every church can change them. Add or change the rows of your own church under Payment Gateways and Wording Per Church."
				)
			);
		}
		frm.set_intro(notes.join("<br><br>"), is_payments_on ? "blue" : "orange");
	},
});

// The tables whose rows each serve the church they name (giving_settings.CHURCH_TABLES).
const CHURCH_TABLES = ["gateways", "church_wording"];

// The server refuses what a church may not change (church_access.refuse_changing_shared_settings):
// a user who does not work across every church changes only their own church's rows.
function lock_shared_settings(frm) {
	if (frm.doc.__onload?.has_every_church !== false) return false;
	for (const df of frm.meta.fields) {
		if (!CHURCH_TABLES.includes(df.fieldname))
			frm.set_df_property(df.fieldname, "read_only", 1);
	}
	for (const table of CHURCH_TABLES) {
		frm.set_query("church", table, () => ({
			filters: { name: ["in", frappe.boot.churchit.churches] },
		}));
	}
	return true;
}
