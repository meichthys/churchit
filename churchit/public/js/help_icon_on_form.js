// Use jQuery since we cannot use a wildcard doctype
$(document).on("form-refresh", function (e, frm) {
	if (frm && frm.meta && frm.meta.documentation) {
		frm.page.add_action_icon(
			"help",
			() => window.open(frm.meta.documentation, "_blank"),
			"",
			__("Documentation"),
		);
	}

	if (frm) add_tour_menu_item(frm);
});

// Frappe 16.54 lists no form tours in boot info, so one request per page load finds them all.
let tour_names_by_doctype;

function get_tour_names_by_doctype() {
	tour_names_by_doctype ||= frappe.db
		.get_list("Form Tour", {
			fields: ["name", "reference_doctype"],
			filters: { ui_tour: 0, reference_doctype: ["is", "set"] },
			order_by: "name asc",
			limit: 1000,
		})
		.then((tours) => {
			const names = {};
			tours.forEach(
				(tour) => (names[tour.reference_doctype] ||= tour.name),
			);
			return names;
		});

	return tour_names_by_doctype;
}

// A tour is found by its reference doctype, because its name can differ (Budget for Church Budget).
async function add_tour_menu_item(frm) {
	const tour_name = (await get_tour_names_by_doctype())[frm.doctype];
	if (!tour_name) return;

	frm.page.add_menu_item(__("Take the Tour"), () =>
		frm.tour.init({ tour_name }).then(() => frm.tour.start()),
	);
}
