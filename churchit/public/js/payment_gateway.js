// Copyright (c) 2026, meichthys and contributors
// For license information, please see license.txt

// The payments app leaves "Gateway Settings" as an unfiltered Link to DocType, so
// the dropdown offers every doctype on the site. Churches reach this form from
// Giving Settings > Payment Gateways, so narrow it to the settings doctypes the
// payments app actually ships (Stripe Settings, PayPal Settings, ...). The name
// filter drops the non-settings doctypes in that module, e.g. GoCardless Mandate.
frappe.ui.form.on("Payment Gateway", {
	setup(frm) {
		frm.set_query("gateway_settings", () => ({
			filters: {
				module: "Payment Gateways",
				name: ["like", "% Settings"],
			},
		}));
	},
});
