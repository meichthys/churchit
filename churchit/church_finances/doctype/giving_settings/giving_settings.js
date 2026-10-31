// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Giving Settings", {
	refresh(frm) {
		// A gateway row links to the payments app's Payment Gateway, which is missing without the app.
		const is_payments_on = frm.doc.__onload?.is_payments_on;
		frm.set_df_property("gateways", "read_only", is_payments_on ? 0 : 1);
		if (!is_payments_on) {
			frm.set_intro(
				__(
					"Online payments are off, because the Payments app is not installed on this site. Gifts on the Give page, sign-up payments and form payments need it. The {0} tells how to install it.",
					[`<a href="/app/manual%3A-finances">${__("Finances manual")}</a>`]
				),
				"orange"
			);
		}
	},
});
