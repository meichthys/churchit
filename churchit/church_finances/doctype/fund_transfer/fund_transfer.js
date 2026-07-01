// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fund Transfer', {
    from_fund: function(frm) {
        // Dynamically filter 'to_fund' to exclude the selected 'from_fund'
        frm.set_query('to_fund', () => ({
            filters: [
                ['name', '!=', frm.doc.from_fund]
            ]
        }));

        // Clear to_fund if it's the same as from_fund
        if (frm.doc.to_fund === frm.doc.from_fund) {
            frm.set_value('to_fund', null);
        }
    },

});
