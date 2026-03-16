frappe.ui.form.on("Bible Reference", {
    import_reference_text: frm => {
        fetch_bible_text(frm);
    },
    church: function(frm) {
        if (frm.doc.church) {
            frappe.db.get_value('Church', frm.doc.church, 'default_bible_translation')
                .then(r => {
                    const value = r && r.message && r.message.default_bible_translation;
                    if (value) frm.set_value('translation', value);
                });
        }
    },
    refresh: async function(frm) {
        frm.add_custom_button('Open in AndBible', async function() {
            const start_verse = await frappe.get_doc("Bible Verse", frm.doc.start_verse);
            if (!start_verse.book || !start_verse.chapter || !start_verse.verse) {
                frappe.msgprint(__('Please make sure reference Start Verse has a Chapter and Verse.'));
                return;
            }

            try {
                // Fetch abbreviation from linked Bible Book record
                const book = await frappe.db.get_doc('Bible Book', start_verse.book);
                const abbreviation = book.abbreviation;

                if (!abbreviation) {
                    frappe.msgprint(__(`No abbreviation found for Book: ${book}.`));
                    return;
                }

                // Construct OSIS reference (e.g., Gen.1.1)
                const osisRef = `${abbreviation}.${start_verse.chapter}.${start_verse.verse}`;

                // Build AndBible deep link
                const url = `https://read.andbible.org/${osisRef}`;

                // Open the link (will launch AndBible if installed)
                window.open(url, '_blank');
            } catch (error) {
                frappe.msgprint(__('Failed to open verse in AndBible.'));
                console.error(error);
            }
        });
        // Set default translation if not set
        if (!frm.doc.translation) {
            const church_name = frm.doc.church;
            const get_translation = church_name
                ? frappe.db.get_value('Church', church_name, 'default_bible_translation')
                    .then(r => r && r.message && r.message.default_bible_translation)
                : frappe.db.get_list('Church', {fields: ['default_bible_translation'], limit: 1})
                    .then(data => data && data.length > 0 && data[0].default_bible_translation);
            get_translation.then(value => { if (value) frm.set_value('translation', value); });
        }
        }
});

async function fetch_bible_text(frm) {
    try {
        if (!frm.doc.translation) {
            frappe.msgprint(__("Please select a Bible Translation before importing reference text."));
            return;
        }

        // Fetch full translation document from DB
        const translation_doc = await frappe.db.get_doc("Bible Translation", frm.doc.translation);
        const translationAbbr = translation_doc.abbreviation;
        const translation_id = await get_translation_id(translationAbbr);

        if (!translation_id) {
            frappe.msgprint(`❌ Translation "${translationAbbr}" not found in bible.helloao.org API.`);
            return;
        }

        // Fetch start and end verse documents
        const start_verse_doc = await get_verse_reference(frm.doc.start_verse);
        const end_verse_doc = frm.doc.end_verse ? await get_verse_reference(frm.doc.end_verse) : null;

        if (!start_verse_doc) {
            frappe.msgprint("❌ Start verse not found.");
            return;
        }

        // Fetch book abbreviation for API
        const start_book_doc = await frappe.db.get_doc("Bible Book", start_verse_doc.book);
        const book_abbrev = await get_book_abbreviation(translation_id, start_book_doc.abbreviation);

        if (!book_abbrev) {
            frappe.msgprint(`❌ Book abbreviation not found for "${start_book_doc.name}" in translation "${translation_id}".`);
            return;
        }

        const start_chapter = parseInt(start_verse_doc.chapter);
        const end_chapter = end_verse_doc ? parseInt(end_verse_doc.chapter) : start_chapter;
        const versesText = [];

        for (let ch = start_chapter; ch <= end_chapter; ch++) {
            const url = `https://bible.helloao.org/api/${encodeURIComponent(translation_id)}/${encodeURIComponent(book_abbrev)}/${ch}.json`;
            const response = await fetch(url);
            if (!response.ok) throw new Error(`Failed to fetch chapter ${ch} (${response.status}) from bible.helloao.org`);
            const data = await response.json();

            // Extract verses from chapter
            const chapterContent = data.chapter.content
                .filter(item => item.type === "verse")
                .map(v => ({
                    number: parseInt(v.number),
                    text: clean_reference_text(v.content)
                }));

            // Filter by verse(s)
            const filtered = chapterContent.filter(v => {
                if (!end_verse_doc && start_chapter === end_chapter) {
                    // Only one verse selected
                    return v.number === start_verse_doc.verse;
                }
                if (ch === start_chapter && v.number < start_verse_doc.verse) return false;
                if (end_verse_doc && ch === end_chapter && v.number > end_verse_doc.verse) return false;
                return true;
            });

            versesText.push(...filtered.map(v => `${v.number}. ${v.text}`));
        }
        if (versesText.length === 0) {
            frappe.msgprint(`⚠️ No text found in ${translation_id} for the specified verse range.
                <br>Please ensure your verses are valid and in the same book.
                <br>Note: Fetching verses in different books is not supported.`);
            return;
        }
        frm.set_value("reference_text", versesText.join(" ").trim());
        frappe.show_alert({ message: `📖 ${translation_id} Bible passage fetched!`, indicator: "green" }, 3);

    } catch (err) {
        console.error(err);
        frappe.msgprint(`❌ Error fetching passage: ${err.message}`);
    }
}

// Flatten nested content arrays into plain text
function clean_reference_text(contentArray) {
    if (!Array.isArray(contentArray)) return contentArray;
    return contentArray
        .map(item => {
            if (typeof item === "string") return item;
            if (item.text) return item.text;
            return "";
        })
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();
}

// Get book abbreviation from HelloAO API
async function get_book_abbreviation(translation_id, book_abbr) {
    const url = `https://bible.helloao.org/api/${encodeURIComponent(translation_id)}/books.json`;
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Failed to fetch book list from bible.helloao.org (${response.status})`);
    const data = await response.json();

    const match = data.books.find(b => b.id === book_abbr || b.shortName === book_abbr);
    return match ? match.id : null;
}

// Fetch a Bible verse document
async function get_verse_reference(name) {
    if (!name) return null;
    try {
        const doc = await frappe.db.get_doc("Bible Verse", name);
        return {
            book: doc.book,       // link to Bible Book
            chapter: parseInt(doc.chapter),
            verse: parseInt(doc.verse)
        };
    } catch {
        console.warn(`⚠️ Bible Verse "${name}" not found.`);
        return null;
    }
}

// Fetch translation ID from HelloAO API
async function get_translation_id(shortname) {
    const response = await fetch('https://bible.helloao.org/api/available_translations.json');
    if (!response.ok) throw new Error(`Failed to fetch translations from bible.helloao.org (${response.status})`);
    const data = await response.json();
    const translation = data.translations.find(t => t.shortName === shortname && t.language === "eng");
    if (!translation) throw new Error(`Translation "${shortname}" not found in bible.helloao.org API.
        It is likely that the version you are trying to use is copyrighted and therefore illegal to
        use freely. We recommend using translations that are not bound by copyright because God's word
        should not be for sale! (see <a href="https://copy.church/initiatives/bibles/" target="_blank">
        https://copy.church/initiatives/bibles/</a> for more details.)`);
    return translation.id;
}
