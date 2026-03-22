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
});

// Keep Collection `total_amount` up to date when amounts are changed/added
frappe.ui.form.on("Donation", "amount", function(frm, cdt, cdn) {
    update_collection_total(frm);
    update_fund_totals(frm);
});

// Keep Collection `total_amount` up to date when rows are removed from grid
frappe.ui.form.on("Donation", {
    donations_remove: function(frm) {
        update_collection_total(frm);
        update_fund_totals(frm);
    }
});

// Also update when fund field changes
frappe.ui.form.on("Donation", "fund", function(frm, cdt, cdn) {
    update_fund_totals(frm);
});

// Update Collection `total_amount` with sum of donation amounts
function update_collection_total(frm) {
    var total = 0;
    frm.doc.donations.forEach(function (donation) {
        total += donation.amount || 0;
    });
    frm.set_value("total_amount", total);
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