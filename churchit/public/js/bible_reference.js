// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// Suggests books, chapters and verses while a Bible reference is typed, says when a reference is
// not in the Bible, and shows its text on hover. The fields come from the boot
// (scripture.REFERENCE_FIELDS), or a dialog field marked bible_reference; the book outline is
// fetched once, the first time one of them is typed in.

(function bibleReferenceFields() {
	const base = frappe.ui.form.ControlData.prototype;
	if (base.make_input._bibleReference) return;

	// The passage being typed: "1 Cor", "1 Cor 13" or "1 Cor 13:4". Anything else gets no suggestions.
	const PASSAGE = /^((?:[1-3]\s*)?[a-z][a-z .]*?)\s*(?:(\d+)(?::(\d*))?)?$/i;
	let outline = null;

	function get_outline() {
		outline = outline || frappe.xcall("churchit.scripture.get_reference_outline");
		return outline;
	}

	function is_reference_field(df) {
		const fields = frappe.boot.bible_reference_fields || {};
		return Boolean(df.bible_reference || (fields[df.parent] || []).includes(df.fieldname));
	}

	const squash = (text) => text.toLowerCase().replace(/[\s.]/g, "");

	// Several passages are separated by semicolons; only the last one is being typed.
	const typed_before_passage = (text) =>
		text.includes(";") ? text.slice(0, text.lastIndexOf(";") + 1) + " " : "";
	const current_passage = (text) => text.slice(text.lastIndexOf(";") + 1).trimStart();

	function get_suggestions(books, passage) {
		const found = PASSAGE.exec(passage);
		if (!found) return [];
		const [, typed_book, chapter, verse] = found;
		const key = squash(typed_book);
		const book = books.find((b) => b.names.some((name) => squash(name) === key));
		if (book && chapter && verse !== undefined) return suggest_verses(book, chapter, verse);
		if (book && (chapter || passage.endsWith(" "))) return suggest_chapters(book, chapter);
		if (chapter) return [];
		return books
			.filter((b) => b.names.some((name) => squash(name).startsWith(key)))
			.map((b) => ({ label: b.title, value: b.title + " " }));
	}

	function suggest_chapters(book, typed) {
		return numbers_up_to(book.verses.length, typed).map((chapter) => ({
			label: __("{0} {1} ({2} verses)", [book.title, chapter, book.verses[chapter - 1]]),
			value: `${book.title} ${chapter}`,
		}));
	}

	function suggest_verses(book, chapter, typed) {
		const count = book.verses[chapter - 1];
		return numbers_up_to(count || 0, typed).map((verse) => {
			const reference = `${book.title} ${chapter}:${verse}`;
			return { label: reference, value: reference };
		});
	}

	function numbers_up_to(last, typed) {
		const numbers = Array.from({ length: last }, (_, index) => index + 1);
		return typed ? numbers.filter((number) => String(number).startsWith(typed)) : numbers;
	}

	function check(control) {
		const text = (control.get_input_value() || "").trim();
		if (text === control.bible_reference_checked) return;
		control.bible_reference_checked = text;
		if (!text) return show_problem(control, null);
		frappe
			.xcall("churchit.scripture.check_reference", { text })
			.then((result) => show_problem(control, result.problem));
	}

	function show_problem(control, problem) {
		control.$wrapper.toggleClass("has-error", Boolean(problem));
		control.$input.attr("title", problem ? $("<div>").html(problem).text() : null);
		if (control.in_grid()) return;
		let $problem = control.$wrapper.find(".bible-reference-problem");
		if (!$problem.length) {
			$problem = $('<div class="help-box small text-danger bible-reference-problem"></div>');
			$problem.insertAfter(control.$input.closest(".awesomplete"));
		}
		$problem.html(problem || "").toggle(Boolean(problem));
	}

	const previews = new Map();

	function get_preview(control, text) {
		const args = { text, ...get_preview_source(control) };
		const key = JSON.stringify(args);
		if (!previews.has(key)) {
			previews.set(key, frappe.xcall("churchit.scripture.get_reference_preview", args));
		}
		return previews.get(key);
	}

	// The record's church (on a Church form, the church itself), and a translation the row names.
	function get_preview_source(control) {
		const record = (control.frm && control.frm.doc) || {};
		const row = control.doc || record;
		const church =
			record.doctype === "Church" ? !record.__islocal && record.name : record.church;
		return { church: church || null, translation: row.translation || null };
	}

	function show_preview(control) {
		const text = (control.get_input_value() || "").trim();
		if (!text || control.$wrapper.hasClass("has-error")) return;
		get_preview(control, text).then((preview) => {
			if (preview.problem || !control.$input.is(":hover")) return;
			const content = preview.text
				? frappe.utils.escape_html(preview.text)
				: `<span class="text-muted">${__("The verse text is not available.")}</span>`;
			control.$input
				.popover("dispose")
				.popover({
					trigger: "manual",
					placement: "top",
					container: "body",
					html: true,
					title: frappe.utils.escape_html(preview.reference),
					content,
				})
				.popover("show");
		});
	}

	function attach(control) {
		const awesomplete = new Awesomplete(control.input, {
			minChars: 1,
			maxItems: 12,
			autoFirst: true,
			tabSelect: true,
			sort: false,
			filter: () => true,
			replace(suggestion) {
				this.input.value = typed_before_passage(this.input.value) + suggestion.value;
			},
		});
		control.$input.on("input", () => {
			const passage = current_passage(control.input.value);
			get_outline().then((books) => {
				awesomplete.list = get_suggestions(books, passage);
			});
		});
		// Picking a book goes straight on to its chapters. A grid only stores a value on change.
		control.$input.on("awesomplete-selectcomplete", () =>
			control.$input.trigger("input").trigger("change")
		);
		control.$input.on("blur", () => check(control));
		control.$input.on("mouseenter", () => show_preview(control));
		control.$input.on("mouseleave input", () => control.$input.popover("dispose"));
		if (control.in_grid()) hang_from_grid(control, awesomplete);
	}

	// A grid cell clips what overflows it, so the list hangs from the grid instead, the way
	// Frappe does it for Link fields (grid_row.js).
	function hang_from_grid(control, awesomplete) {
		const $list = $('<div class="awesomplete"></div>').append(awesomplete.ul);
		control.$input.on("focus", () => {
			const $grid = control.$input.closest(".grid-field");
			const cell = control.$input.offset();
			$list.appendTo($grid).css({
				position: "absolute",
				top: cell.top - $grid.offset().top + control.$input.outerHeight() + 4,
				left: cell.left - $grid.offset().left,
				minWidth: "250px",
				width: control.$input.outerWidth(),
			});
		});
	}

	const make_input = base.make_input;
	const patched = function () {
		make_input.call(this);
		if (!this.df.is_filter && is_reference_field(this.df)) attach(this);
	};
	patched._bibleReference = true;
	base.make_input = patched;
})();
