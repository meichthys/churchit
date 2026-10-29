// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Missionary", {
	refresh(frm) {
		//Add an 'intro' indicating if a missionary is published to the website
		if (frm.doc.sensitive && frm.doc.publish) {
			frm.set_intro(
				"🚨 This missionary is marked as sensitive and is published \
                to the public website. Make sure sensitive content is not being \
                leaked to the public!",
				"red"
			);
		} else if (frm.doc.sensitive) {
			frm.set_intro(
				"⚠️ This missionary is marked as sensitive. \
                be careful not to disclose sensitive information.",
				"yellow"
			);
		} else if (frm.doc.publish) {
			frm.set_intro("🌐 This missionary is published to the public website", "blue");
		}

		const grid = frm.fields_dict.people.grid;
		// Frappe prepends custom buttons; append so "Add row" stays first.
		grid.add_custom_button(__("Add Family"), () => {
			frappe.prompt(
				{
					fieldtype: "Link",
					fieldname: "family",
					label: __("Family"),
					options: "Family",
					reqd: 1,
				},
				(values) => add_family(frm, values.family),
				__("Add Family"),
				__("Add")
			);
		}).appendTo(grid.grid_buttons);
	},

	// The server looks the country up, so People Settings can turn it off, as for Location.address.
	// Only fills an empty pin, so a manually placed one is never overwritten.
	country(frm) {
		if (!frm.doc.country || frm.doc.geolocation) return;

		frappe
			.xcall(
				"churchit.church_missions.doctype.missionary.missionary.get_country_coordinates",
				{
					country: frm.doc.country,
				}
			)
			.then(([latitude, longitude]) => {
				if ((!latitude && !longitude) || frm.doc.geolocation) return;
				const geojson = JSON.stringify({
					type: "FeatureCollection",
					features: [
						{
							type: "Feature",
							geometry: { type: "Point", coordinates: [longitude, latitude] },
							properties: {},
						},
					],
				});
				frm.set_value("geolocation", geojson);
			});
	},
});

function add_family(frm, family) {
	frm.call("add_family", { family }).then(async (r) => {
		const added = r.message || [];
		// Rows from the server carry Person IDs; fetch titles so the grid shows names.
		await Promise.all(added.map((person) => frappe.utils.fetch_link_title("Person", person)));
		frm.refresh_field("people");
		// Syncing the server's copy leaves a saved form looking unchanged.
		if (added.length) frm.dirty();
		frappe.show_alert({
			message: added.length
				? __("{0} family member(s) added", [added.length])
				: __("Everyone in this family is already listed"),
			indicator: added.length ? "green" : "blue",
		});
	});
}
