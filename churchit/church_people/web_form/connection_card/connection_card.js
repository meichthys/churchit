// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ready(function () {
	hide_honeypot(frappe.web_form.fields_dict.website);
	show_interests_as_checkboxes(frappe.web_form.fields_dict.interests);
	fit_household_to_a_phone(frappe.web_form.fields_dict.household_members);
});

// Only robots fill in the Website box. The stylesheet moves it off screen; this keeps
// it away from the keyboard, screen readers and autofill.
function hide_honeypot(field) {
	field.$wrapper.attr("aria-hidden", "true");
	field.$input.attr({ tabindex: "-1", autocomplete: "off" });
}

// A guest ticks boxes instead of adding table rows. Frappe lists the interests a guest
// may pick as the options of the table's Interest column, and sends the grid's rows.
function show_interests_as_checkboxes(field) {
	const column = field.df.fields.find((df) => df.fieldname === "interest");
	const interests = (column.options || "").split("\n").filter(Boolean).sort();
	if (!interests.length) {
		field.$wrapper.hide();
		return;
	}

	const $choices = $('<div class="connection-card-interests">').appendTo(field.grid.wrapper);
	for (const interest of interests) {
		$('<label class="connection-card-interest">')
			.append($('<input type="checkbox">').val(interest), document.createTextNode(interest))
			.appendTo($choices);
	}
	$choices.on("change", () => {
		field.df.data = $choices
			.find("input:checked")
			.map((index, input) => ({ interest: input.value }))
			.get();
	});
}

// A new row opens as a form, which fits a phone better than four columns in a row. Frappe lists
// the relationship types as the options of the Relationship column itself, so a guest needs no
// right to read them, and a select offers them as a list.
function fit_household_to_a_phone(field) {
	const grid = field.grid;
	const column = field.df.fields.find((df) => df.fieldname === "relationship");
	grid.update_docfield_property("relationship", "fieldtype", "Select");
	grid.update_docfield_property("relationship", "options", ["", ...JSON.parse(column.options)]);
	grid.update_docfield_property("name", "hidden", 1);
	grid.wrapper.find(".grid-add-row").on("click", () => {
		grid.grid_rows[grid.grid_rows.length - 1].toggle_view(true);
	});
}
