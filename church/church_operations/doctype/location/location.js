// Copyright (c) 2026, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Location", {
	parent_location(frm) {
		if (frm.doc.parent_location && !frm.doc.address) {
			frappe.db.get_value("Location", frm.doc.parent_location, "address").then(({ message }) => {
				if (message && message.address) {
					frm.set_value("address", message.address);
				}
			});
		}
	},

	address(frm) {
		if (!frm.doc.address) return;

		frappe.db.get_doc("Address", frm.doc.address).then((addr) => {
			const parts = [
				addr.address_line1,
				addr.address_line2,
				addr.city,
				addr.state,
				addr.pincode,
				addr.country,
			].filter(Boolean);

			if (!parts.length) return;

			const query = encodeURIComponent(parts.join(", "));
			fetch(`https://nominatim.openstreetmap.org/search?q=${query}&format=json&limit=1`, {
				headers: { "Accept-Language": "en" },
			})
				.then((r) => r.json())
				.then((results) => {
					if (!results.length) {
						frappe.msgprint(__("Address could not be geocoded."));
						return;
					}
					const { lat, lon } = results[0];
					const geojson = JSON.stringify({
						type: "FeatureCollection",
						features: [
							{
								type: "Feature",
								geometry: {
									type: "Point",
									coordinates: [parseFloat(lon), parseFloat(lat)],
								},
								properties: {},
							},
						],
					});
					frm.set_value("geolocation", geojson);
				});
		});
	},
});
