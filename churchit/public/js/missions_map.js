// Renders the missionary map on the public /missions page. A loaded-everywhere
// script guarded by path, since Web Page content has no per-page script hook.
// Leaflet comes from church_website/context.py on this path.
(function () {
	const path = window.location.pathname.replace(/\/$/, "");
	if (path !== "/missions") return;

	const mapEl = document.getElementById("missions-map");
	if (!mapEl) return;

	const FALLBACK_PHOTO = "/assets/frappe/images/default-avatar.png";

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
				? __("1 missionary not shown for their safety")
				: __("{0} missionaries not shown for their safety", [hiddenCount]);
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
			args: churchit.with_church({}),
		})
		.then((r) => {
			const { markers = [], hidden_count: hiddenCount = 0 } = r.message || {};
			showHiddenNotice(hiddenCount);
			if (!markers.length) return;

			const points = markers.map((marker) => {
				L.marker([marker.latitude, marker.longitude], {
					icon: markerIcon(marker.photo),
					title: marker.title,
					alt: marker.title,
				})
					.on("add", (event) => {
						// a pin is a Tab stop that opens its popup, so it is a named button
						const pin = event.target.getElement();
						pin.setAttribute("role", "button");
						pin.setAttribute("aria-label", marker.title);
					})
					.addTo(map)
					.bindPopup(popupContent(marker));
				return [marker.latitude, marker.longitude];
			});

			if (points.length > 1) {
				// a pin stands 50px above its point, so the top needs the room
				map.fitBounds(points, {
					paddingTopLeft: [30, 60],
					paddingBottomRight: [30, 30],
					maxZoom: 6,
				});
			} else {
				map.setView(points[0], 5);
			}
		});
})();
