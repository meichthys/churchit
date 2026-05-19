frappe.ui.form.on("Bible Reference", {
    import_reference_text: function(frm) {
        if (!frm.doc.translation) {
            frappe.msgprint(__("Please select a Bible Translation before importing reference text."));
            return;
        }
        frappe.call({
            method: "church.church_study.bible_api.fetch_reference_text",
            args: { bible_reference: frm.doc.name },
            freeze: true,
            freeze_message: __("Fetching passage…"),
        }).then(r => {
            if (r && !r.exc) {
                frm.reload_doc();
                frappe.show_alert({ message: __("Passage fetched."), indicator: "green" }, 3);
            }
        });
    },
    refresh: async function(frm) {
        if (!frm.is_new() && church.bible_memory.can_assign()) {
            frm.add_custom_button(__('Assign to User for Memorization'), () => {
                church.bible_memory.open_assign_dialog([frm.doc.name], 'user');
            });
            frm.add_custom_button(__('Assign to Group for Memorization'), () => {
                church.bible_memory.open_assign_dialog([frm.doc.name], 'group');
            });
        }

        frm.add_custom_button('Open in AndBible', async function() {
            const start_verse = await frappe.get_doc("Bible Verse", frm.doc.start_verse);
            if (!start_verse.book || !start_verse.chapter || !start_verse.verse) {
                frappe.msgprint(__('Please make sure reference Start Verse has a Chapter and Verse.'));
                return;
            }

            try {
                const book = await frappe.db.get_doc('Bible Book', start_verse.book);
                const abbreviation = book.abbreviation;

                if (!abbreviation) {
                    frappe.msgprint(__(`No abbreviation found for Book: ${book}.`));
                    return;
                }

                const osisRef = `${abbreviation}.${start_verse.chapter}.${start_verse.verse}`;
                const url = `https://read.andbible.org/${osisRef}`;
                window.open(url, '_blank');
            } catch (error) {
                frappe.msgprint(__('Failed to open verse in AndBible.'));
                console.error(error);
            }
        });

        if (!frm.doc.translation) {
            frappe.db.get_list('Church', {fields: ['default_bible_translation'], limit: 1})
                .then(data => {
                    const value = data && data.length > 0 && data[0].default_bible_translation;
                    if (value) frm.set_value('translation', value);
                });
        }
    }
});

