// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// The merge dialogs of Person and Possible Duplicate: one radio per field where both people have a
// different value, from churchit.church_people.merge.get_merge_choices. get_taken() returns the
// fields to take from the person merged in, for merge_people's take_from_removed.
(function () {
	window.churchit = window.churchit || {};
	churchit.merge_choices = {
		async render($wrapper, keep, remove) {
			// A Link field fires onchange again on blur, for example when the user clicks a radio.
			if ($wrapper.data("keep") === keep && $wrapper.data("remove") === remove) return;
			$wrapper.data({ keep, remove }).empty();
			if (!keep || !remove) return;
			const choices = await frappe.xcall("churchit.church_people.merge.get_merge_choices", {
				keep,
				remove,
			});
			// The user picked another person while this one loaded.
			if ($wrapper.data("keep") !== keep || !choices.fields.length) return;

			const escape = frappe.utils.escape_html;
			const cell = (field, side) => `
				<td><label class="d-flex align-items-start mb-0" style="gap: var(--padding-sm)">
					<input type="radio" name="${field.fieldname}" value="${side}"
						${side === "keep" ? "checked" : ""}>
					<span style="white-space: pre-wrap">${escape(field[side])}</span>
				</label></td>`;
			const rows = choices.fields.map(
				(field) => `<tr>
					<th scope="row">${escape(field.label)}</th>
					${cell(field, "keep")}${cell(field, "remove")}
				</tr>`
			);
			// A form of its own keeps the radio groups apart from those of another dialog.
			$wrapper.html(`
				<p class="text-muted">${__("Both people have these details. Choose the one to keep.")}</p>
				<form><table class="table table-bordered">
					<thead><tr>
						<th></th>
						<th>${escape(choices.keep)} (${escape(keep)})</th>
						<th>${escape(choices.remove)} (${escape(remove)})</th>
					</tr></thead>
					<tbody>${rows.join("")}</tbody>
				</table></form>`);
		},

		get_taken($wrapper) {
			return $wrapper
				.find("input[value=remove]:checked")
				.map((_i, input) => input.name)
				.get();
		},
	};
})();
