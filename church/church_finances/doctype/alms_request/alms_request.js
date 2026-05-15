// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on('Alms Request', {
    recipient_type: function(frm) {
        // Dynamically update the Recipient field description based on the Recipient Type that is selected
        if (frm.doc.recipient_type) {
            frm.set_df_property('recipient', 'description', `Alms are requested for this ${frm.doc.recipient_type}.`);
        }
    },
    refresh(frm) {
        // Add a custom button that creates an Expense from the Alms Request
        if (!frm.is_new()) {
            frm.add_custom_button(__('Create Expense'), function () {
                if (frm.doc.associated_expense) {
                    frappe.db.get_value('Expense', frm.doc.associated_expense, 'title').then(r => {
                        const title = r.message.title || frm.doc.associated_expense;
                        frappe.confirm(
                            `An expense (<a href="/app/expense/${frm.doc.associated_expense}" target="_blank">${title}</a>) already exists for this alms request. Create another?`,
                            function() {
                                frappe.call({
                                    method: 'church.church_finances.doctype.alms_request.alms_request.create_expense',
                                    args: { alms_request_name: frm.doc.name },
                                    callback: function () { frm.reload_doc(); }
                                });
                            }
                        );
                    });
                } else {
                    frappe.call({
                        method: 'church.church_finances.doctype.alms_request.alms_request.create_expense',
                        args: { alms_request_name: frm.doc.name },
                        callback: function () { frm.reload_doc(); }
                    });
                }
            });
        }
    },
    onload: function(frm) {
        // Pre-populate the requestor field with the current user's name
        if (frm.is_new()) {
            frappe.db.get_value('Person', {'user': frappe.session.user}, 'name')
                .then(r => {
                    if (r && r.message) {
                        frm.set_value('requestor', r.message.name);
                    }
                });
        }
    },
    after_save: function(frm) {
        // Prompt user to create an expense when status is set to "Distributed"
        if (frm.doc.status === 'Distributed' && !frm.doc.associated_expense) {
            frappe.confirm(
                'Would you like to create an associated expense?',
                function() {
                    frappe.call({
                        method: 'church.church_finances.doctype.alms_request.alms_request.create_expense',
                        args: {
                            alms_request_name: frm.doc.name
                        },
                        callback: function () {
                            frm.reload_doc();
                        }
                    });
                }
            );
        }
    }
});



