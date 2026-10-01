// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.pages["bible"].on_page_load = function (wrapper) {
	wrapper.bible_reader = new BibleReader(wrapper);
};

// The route is the reader's position (/desk/bible/BSB/JHN/3), so links, reloads and Back all work.
frappe.pages["bible"].on_page_show = function (wrapper) {
	wrapper.bible_reader.show_route();
};

class BibleReader {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Bible"),
			single_column: true,
		});
		this.translation_field = this.add_picker("translation", __("Translation"), () =>
			this.open(this.translation_field.get_value(), this.book.id, this.chapter)
		);
		this.book_field = this.add_picker("book", __("Book"), () =>
			this.open(this.translation.name, this.book_field.get_value(), 1)
		);
		this.chapter_field = this.add_picker("chapter", __("Chapter"), () =>
			this.open(this.translation.name, this.book.id, this.chapter_field.get_value())
		);
		this.page.set_secondary_action(__("Previous"), () => this.step(-1));
		this.page.set_primary_action(__("Next"), () => this.step(1));
		this.$text = $('<div class="bible-reader-text"></div>').appendTo(this.page.main);
		this.translations = frappe.xcall("churchit.scripture.get_readable_translations");
		this.books = {};
	}

	add_picker(fieldname, label, change) {
		return this.page.add_field({ fieldname, label, fieldtype: "Select", change });
	}

	open(translation, book, chapter) {
		frappe.set_route("bible", translation, book, String(chapter));
	}

	async show_route() {
		const request = (this.request = Symbol());
		const [, translation, book, chapter] = frappe.get_route();
		const translations = await this.translations;
		if (!translations.length) {
			this.$text.html(
				`<p class="text-muted">${__("No Bible translation is ready to read yet.")}</p>`
			);
			return;
		}
		const chosen =
			translations.find((option) => option.name === translation) || translations[0];
		const books = await this.get_books(chosen.name);
		if (request !== this.request) return;
		this.translation = chosen;
		this.book = books.find((option) => option.id === book) || books[0];
		this.chapter = Math.min(Math.max(cint(chapter), 1), this.book.chapters);
		this.set_pickers(translations, books);
		const items = await frappe.xcall("churchit.scripture.get_chapter", {
			translation: chosen.name,
			book: this.book.id,
			chapter: this.chapter,
		});
		if (request === this.request) this.render(items);
	}

	get_books(translation) {
		this.books[translation] ||= frappe.xcall("churchit.scripture.get_books", { translation });
		return this.books[translation];
	}

	set_pickers(translations, books) {
		const numbers = Array.from({ length: this.book.chapters }, (_, index) =>
			String(index + 1)
		);
		this.set_options(
			this.translation_field,
			translations.map((option) => ({ label: option.translation, value: option.name })),
			this.translation.name
		);
		this.set_options(
			this.book_field,
			books.map((option) => ({ label: option.name, value: option.id })),
			this.book.id
		);
		this.set_options(this.chapter_field, numbers, String(this.chapter));
		this.page.set_title(`${this.book.name} ${this.chapter}`);
	}

	set_options(field, options, value) {
		// set_input, unlike set_value, leaves the change handler alone.
		field.df.options = options;
		field.set_input(value);
	}

	async step(direction) {
		const books = await this.get_books(this.translation.name);
		const chapters = books.flatMap((book) =>
			Array.from({ length: book.chapters }, (_, index) => [book.id, index + 1])
		);
		const here = chapters.findIndex(
			([book, chapter]) => book === this.book.id && chapter === this.chapter
		);
		const target = chapters[here + direction];
		if (target) this.open(this.translation.name, ...target);
	}

	render(items) {
		// A line break ends a paragraph; headings and subtitles stand between paragraphs.
		const escape = frappe.utils.escape_html;
		const html = items.map((item) => {
			if (item.type === "heading") return `</p><h3>${escape(item.text)}</h3><p>`;
			if (item.type === "hebrew_subtitle")
				return `</p><p class="bible-subtitle">${escape(item.text)}</p><p>`;
			if (item.type === "line_break") return "</p><p>";
			if (item.type === "verse")
				return `<span class="bible-verse"><sup>${item.number}</sup>${escape(
					item.text
				)} </span>`;
			return "";
		});
		const title = `<h2>${escape(this.book.name)} ${this.chapter}</h2>`;
		this.$text
			.attr("dir", this.translation.text_direction || "ltr")
			.html(`${title}<p>${html.join("")}</p>`);
	}
}
