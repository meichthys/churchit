// Renders the missionary map on the public /missions page. A loaded-everywhere
// script guarded by path, like portal_groups.js, since Web Page content has no
// per-page script hook.
(function () {
	const path = window.location.pathname.replace(/\/$/, "");
	if (path !== "/missions") return;

	const mapEl = document.getElementById("missions-map");
	if (!mapEl) return;

	const FALLBACK_PHOTO = "/assets/frappe/images/default-avatar.png";

	// The desk bundle carries leaflet.css; the website bundle does not.
	const link = document.createElement("link");
	link.rel = "stylesheet";
	link.href = "/assets/frappe/js/lib/leaflet/leaflet.css";
	document.head.appendChild(link);

	function markerIcon(photo) {
		return L.divIcon({
			className: "missions-map-pin",
			html: `<img src="${photo || FALLBACK_PHOTO}" alt="" />`,
			iconSize: [50, 50],
			iconAnchor: [25, 50],
			popupAnchor: [0, -46],
		});
	}

	function popupContent(marker) {
		const el = document.createElement("div");
		el.className = "missions-map-popup";
		el.innerHTML = `
			<div class="missions-map-popup-title">${frappe.utils.escape_html(marker.title)}</div>
			${
				marker.country
					? `<div class="missions-map-popup-country">${frappe.utils.escape_html(
							marker.country
					  )}</div>`
					: ""
			}
		`;
		return el;
	}

	function showHiddenNotice(hiddenCount) {
		if (!hiddenCount) return;
		const label =
			hiddenCount === 1
				? "1 missionary not shown for their safety"
				: `${hiddenCount} missionaries not shown for their safety`;
		const notice = document.createElement("div");
		notice.className = "missions-map-notice";
		notice.innerHTML = `<span class="missions-map-pill">${label}</span>`;
		mapEl.insertAdjacentElement("afterend", notice);
	}

	const map = L.map(mapEl, { scrollWheelZoom: false, worldCopyJump: true }).setView([20, 0], 2);
	const { url, options } = frappe.utils.map_defaults.tiles.default_tile;
	L.tileLayer(url, options).addTo(map);

	frappe
		.call({
			method: "churchit.church_missions.doctype.missionary.missionary.get_public_map_markers",
			type: "GET",
		})
		.then((r) => {
			const { markers = [], hidden_count: hiddenCount = 0 } = r.message || {};
			showHiddenNotice(hiddenCount);
			if (!markers.length) return;

			const points = markers.map((marker) => {
				L.marker([marker.latitude, marker.longitude], { icon: markerIcon(marker.photo) })
					.addTo(map)
					.bindPopup(popupContent(marker));
				return [marker.latitude, marker.longitude];
			});

			if (points.length > 1) {
				map.fitBounds(points, { padding: [30, 30], maxZoom: 6 });
			} else {
				map.setView(points[0], 5);
			}
		});
})();
