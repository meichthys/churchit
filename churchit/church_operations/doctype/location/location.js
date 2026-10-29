// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Location", {
	parent_location(frm) {
		if (frm.doc.parent_location && !frm.doc.address) {
			frappe.db
				.get_value("Location", frm.doc.parent_location, "address")
				.then(({ message }) => {
					if (message && message.address) {
						frm.set_value("address", message.address);
					}
				});
		}
	},

	address(frm) {
		if (!frm.doc.address) return;

		// The server looks the address up, so People Settings can turn it off.
		frappe
			.xcall("churchit.church_people.geocoding.get_address_coordinates", {
				address: frm.doc.address,
			})
			.then((coordinates) => {
				// No answer while address lookups are off.
				if (!coordinates) return;
				const [latitude, longitude] = coordinates;
				if (!latitude && !longitude) {
					frappe.msgprint(__("Address could not be geocoded."));
					return;
				}
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
