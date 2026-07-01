// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fund', {
    onload: function(frm) {
        sort_transactions_by_date(frm);
    }
});

function sort_transactions_by_date(frm) {
    // Sort descending
    frm.doc.transactions.sort((a, b) => {
        const dateA = new Date(a.date);
        const dateB = new Date(b.date);
        return dateB - dateA;
    });

    frm.refresh_field('transactions');
}
