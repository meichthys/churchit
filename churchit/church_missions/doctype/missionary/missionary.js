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
	},

	// Same nominatim geocoding pattern as Location.address (church_operations/doctype/location/location.js).
	// Only fills an empty pin, so a manually placed one is never overwritten.
	country(frm) {
		if (!frm.doc.country || frm.doc.geolocation) return;

		const query = encodeURIComponent(frm.doc.country);
		fetch(`https://nominatim.openstreetmap.org/search?q=${query}&format=json&limit=1`, {
			headers: { "Accept-Language": "en" },
		})
			.then((r) => r.json())
			.then((results) => {
				if (!results.length || frm.doc.geolocation) return;
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
	},
});
