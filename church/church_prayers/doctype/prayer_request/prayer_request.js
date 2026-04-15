// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on('Prayer Request', {
    refresh(frm) {
        if (frm.doc.is_private) {
            frm.set_intro('⚠️ This prayer request is marked as private and should not be shared with the full church body.', 'yellow');
        }
    },
    onload: function(frm) {
        // Filter recipient_type to DocTypes in the church app
        church.set_church_doctype_query(frm, 'recipient_type');

        if (frm.is_new()) {
            // Pre-populate the requestor field with the current user's name
            frappe.db.get_value('Person', {'portal_user': frappe.session.user}, 'name')
                .then(r => {
                    if (r && r.message) {
                        frm.set_value('requestor', r.message.name);
                    }
                });
            // Set default status
            if (!frm.doc.status) {
                frappe.db.get_value('Prayer Request Status', {status: 'Requested'}, 'name')
                    .then(r => {
                        if (r && r.message) {
                            frm.set_value('status', r.message.name);
                        }
                    });
            }
        }
    }
});