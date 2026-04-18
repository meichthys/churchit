// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

// Add button to goto `Collection Bank Reconciliation` report
frappe.ui.form.on("Collection", {
	refresh(frm) {
		// Add 'Bank Reconciliation Report' button
		frm.add_custom_button(__('Bank Reconciliation Report'), function () {
			if (frm.is_new()) {
				frappe.show_alert("Save the Collection first!")
				return;
			};
			frappe.set_route("query-report", "Collection Bank Reconciliation", {
				"parent_filter": frm.doc.name
			});
		});
	},

	// Recalculate imbalance when expected_total is changed
	expected_total(frm) {
		update_imbalance(frm);
	},
});

// Keep Collection totals up to date when amounts are changed/added
frappe.ui.form.on("Donation", "amount", function(frm, cdt, cdn) {
    update_collection_total(frm);
    update_fund_totals(frm);
    update_payment_type_totals(frm);
});

// Keep Collection totals up to date when rows are removed from grid
frappe.ui.form.on("Donation", {
    donations_remove: function(frm) {
        update_collection_total(frm);
        update_fund_totals(frm);
        update_payment_type_totals(frm);
    }
});

// Update fund totals when fund field changes
frappe.ui.form.on("Donation", "fund", function(frm, cdt, cdn) {
    update_fund_totals(frm);
});

// Update payment type totals when payment_type field changes
frappe.ui.form.on("Donation", "payment_type", function(frm, cdt, cdn) {
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
    var entered = (entered_total !== undefined) ? entered_total : (frm.doc.total_amount || 0);
    var expected = frm.doc.expected_total || 0;
    frm.set_value("imbalance", entered - expected);
}

// Update fund_totals table based on donations
function update_fund_totals(frm) {
    // Clear existing fund_totals before each update
    frm.clear_table("fund_totals");

    // Calculate totals by fund
    var fund_totals = {};
    frm.doc.donations.forEach(function(donation) {
        if (donation.fund && donation.amount) {
            if (!fund_totals[donation.fund]) {
                fund_totals[donation.fund] = 0;
            }
            fund_totals[donation.fund] += donation.amount;
        }
    });

    // Add rows to fund_totals table
    Object.keys(fund_totals).forEach(function(fund) {
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
    frm.doc.donations.forEach(function(donation) {
        if (donation.payment_type && donation.amount) {
            if (!payment_type_totals[donation.payment_type]) {
                payment_type_totals[donation.payment_type] = 0;
            }
            payment_type_totals[donation.payment_type] += donation.amount;
        }
    });

    // Add rows to payment_type_totals table
    Object.keys(payment_type_totals).forEach(function(payment_type) {
        var row = frm.add_child("payment_type_totals");
        row.payment_type = payment_type;
        row.total = payment_type_totals[payment_type];
    });

    // Refresh the payment_type_totals field to show updated data
    frm.refresh_field("payment_type_totals");
}
