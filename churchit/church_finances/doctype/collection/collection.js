// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Collection", {
	setup(frm) {
		// Gifts are entered after the service, so offer today's and then the latest past services first.
		frm.set_query("function", () => ({
			filters: [["start_date", "<=", frappe.datetime.get_today()]],
		}));
		// An empty filter set makes the picker say "Filtered by: ." with nothing named.
		frm.set_query("fund", "donations", () => {
			const filters = get_fund_filters(frm);
			return Object.keys(filters).length ? { filters } : {};
		});

		// A focused link cell shows an Open Link arrow that hides again on blur, so a Tab onto the arrow
		// dropped the focus out of the row. Keep the arrows out of the Tab order of this grid.
		const table = frm.fields_dict.donations.$wrapper;
		table.on("focusin", () =>
			table.find(".link-btn a").attr("tabindex", -1),
		);
	},

	onload(frm) {
		if (frm.is_new()) set_default_fund(frm);
	},

	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.docstatus === 1 && !frm.doc.__onload?.email_receipts) {
			const href = "/desk/giving-settings#messages_tab";
			const link = `<a href="${href}">${__("Giving Settings")}</a>`;
			frm.dashboard.add_comment(
				__(
					"Givers aren't emailed a receipt. Turn on Email Receipts in {0}.",
					[link],
				),
				"blue",
				true,
			);
		}
		frm.add_custom_button(
			__("Bank Reconciliation Report"),
			() =>
				frappe.set_route(
					"query-report",
					"Collection Bank Reconciliation",
					{
						parent_filter: frm.doc.name,
					},
				),
			__("View"),
		);
	},

	// Statements count gifts by this date, so a collection entered later takes its service's day.
	function(frm) {
		if (!frm.is_new() || !frm.doc.function) return;
		frappe.db
			.get_value("Function", frm.doc.function, [
				"start_date",
				"start_time",
			])
			.then(({ message }) => {
				if (!message || !message.start_date) return;
				frm.set_value(
					"date",
					`${message.start_date} ${message.start_time || "00:00:00"}`,
				);
			});
	},

	// Recalculate imbalance when expected_total is changed
	expected_total(frm) {
		update_imbalance(frm);
	},
});

// A collection takes gifts only into its own church's funds or shared ones (Collection.validate).
function get_fund_filters(frm) {
	const church_name =
		church.is_multi_church() &&
		(frm.doc.church || frappe.boot.churchit.church);
	return church_name ? { church: ["in", [church_name, ""]] } : {};
}

// Giving Settings' Default Fund starts the first row, and a row added later when none is above it.
function set_default_fund(frm) {
	frappe.db
		.get_single_value("Giving Settings", "default_fund")
		.then((fund) =>
			fund
				? frappe.db.get_list("Fund", {
						filters: { name: fund, ...get_fund_filters(frm) },
					})
				: [],
		)
		.then((funds) => {
			frm.default_fund = funds.length ? funds[0].name : null;
			(frm.doc.donations || []).forEach((row) => {
				if (!row.fund && frm.default_fund)
					frappe.model.set_value(
						row.doctype,
						row.name,
						"fund",
						frm.default_fund,
					);
			});
		});
}

// Keep Collection totals up to date when amounts are changed/added
frappe.ui.form.on("Donation", "amount", function (frm, cdt, cdn) {
	update_collection_total(frm);
	update_fund_totals(frm);
	update_payment_type_totals(frm);
});

frappe.ui.form.on("Donation", {
	// Most gifts in one collection share a fund and a payment type, so a new row starts like the one above.
	donations_add(frm, cdt, cdn) {
		const previous = frm.doc.donations[locals[cdt][cdn].idx - 2];
		const values = {};
		const fund = previous ? previous.fund : frm.default_fund;
		if (fund) values.fund = fund;
		if (previous && previous.payment_type && !previous.is_non_cash)
			values.payment_type = previous.payment_type;
		frappe.model.set_value(cdt, cdn, values);
	},

	// Keep Collection totals up to date when rows are removed from grid
	donations_remove: function (frm) {
		update_collection_total(frm);
		update_fund_totals(frm);
		update_payment_type_totals(frm);
	},

	// A non-cash gift has no amount and needs a description, which only the row editor shows.
	is_non_cash(frm, cdt, cdn) {
		if (!locals[cdt][cdn].is_non_cash) return;
		frappe.model.set_value(cdt, cdn, "amount", 0);
		frm.fields_dict.donations.grid.grid_rows_by_docname[cdn].show_form();
	},
});

// Update fund totals when fund field changes
frappe.ui.form.on("Donation", "fund", function (frm, cdt, cdn) {
	update_fund_totals(frm);
});

// Update payment type totals when payment_type field changes
frappe.ui.form.on("Donation", "payment_type", function (frm, cdt, cdn) {
	update_payment_type_totals(frm);
});

// Update Collection `total_amount` with sum of donation amounts, then recalculate imbalance
function update_collection_total(frm) {
	var total = 0;
	frm.doc.donations.forEach(function (donation) {
		total += donation.amount || 0;
	});
	frm.set_value("total_amount", total);
	update_imbalance(frm, total);
}

// Update imbalance as the difference between entered total and expected total
function update_imbalance(frm, entered_total) {
	var entered =
		entered_total !== undefined ? entered_total : frm.doc.total_amount || 0;
	var expected = frm.doc.expected_total || 0;
	frm.set_value("imbalance", entered - expected);
}

// Update fund_totals table based on donations
function update_fund_totals(frm) {
	// Clear existing fund_totals before each update
	frm.clear_table("fund_totals");

	// Calculate totals by fund
	var fund_totals = {};
	frm.doc.donations.forEach(function (donation) {
		if (donation.fund && donation.amount) {
			if (!fund_totals[donation.fund]) {
				fund_totals[donation.fund] = 0;
			}
			fund_totals[donation.fund] += donation.amount;
		}
	});

	// Add rows to fund_totals table
	Object.keys(fund_totals).forEach(function (fund) {
		var row = frm.add_child("fund_totals");
		row.fund = fund;
		row.total = fund_totals[fund];
	});

	// Refresh the fund_totals field to show updated data
	frm.refresh_field("fund_totals");
}

// Update payment_type_totals table based on donations
function update_payment_type_totals(frm) {
	// Clear existing payment_type_totals before each update
	frm.clear_table("payment_type_totals");

	// Calculate totals by payment type
	var payment_type_totals = {};
	frm.doc.donations.forEach(function (donation) {
		if (donation.payment_type && donation.amount) {
			if (!payment_type_totals[donation.payment_type]) {
				payment_type_totals[donation.payment_type] = 0;
			}
			payment_type_totals[donation.payment_type] += donation.amount;
		}
	});

	// Add rows to payment_type_totals table
	Object.keys(payment_type_totals).forEach(function (payment_type) {
		var row = frm.add_child("payment_type_totals");
		row.payment_type = payment_type;
		row.total = payment_type_totals[payment_type];
	});

	// Refresh the payment_type_totals field to show updated data
	frm.refresh_field("payment_type_totals");
}
