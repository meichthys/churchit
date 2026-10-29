# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Latitude and longitude for addresses, so Frappe's Map view can show them.

A save that moves an address queues a lookup with Nominatim, the OpenStreetMap search, after its commit.
Nominatim allows one request a second and asks for a User-Agent naming the site. A lookup that fails or finds
nothing leaves the coordinates blank (0, which the Map view skips). The second address line is left out of the
search, because a flat or suite number stops Nominatim finding the street.
"""

import time

import frappe
import requests
from frappe.utils import get_url
from frappe.utils.synchronization import filelock

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
SEARCH_FIELDS = ("address_line1", "city", "state", "pincode", "country")
# Nominatim's usage policy: at most one request a second from this server.
SECONDS_BETWEEN_REQUESTS = 1
REQUEST_TIMEOUT_SECONDS = 10
# Addresses looked up by one job of `geocode_missing`.
BATCH = 100


def is_address_lookup_on() -> bool:
	"""True while People Settings lets address text go to the map service."""
	return bool(frappe.db.get_single_value("People Settings", "look_up_addresses"))


def queue_geocode(doc, method=None) -> None:
	"""doc_events on_update of Address: look up its coordinates after the commit, when where it is changed.

	Installs, migrations and tests queue nothing; the patch for addresses saved before this queues those.
	"""
	if frappe.flags.in_install or frappe.flags.in_patch or frappe.flags.in_migrate or frappe.in_test:
		return
	if not is_address_lookup_on() or not any(doc.has_value_changed(field) for field in SEARCH_FIELDS):
		return
	frappe.enqueue(
		geocode,
		queue="long",
		job_id=f"geocode::{doc.name}",
		deduplicate=True,
		enqueue_after_commit=True,
		address=doc.name,
	)


def geocode(address: str) -> None:
	"""Store the coordinates Nominatim finds for *address*, or blanks. `db_set`, so no Address hook runs again."""
	if not is_address_lookup_on() or not frappe.db.exists("Address", address):
		return
	doc = frappe.get_doc("Address", address)
	latitude, longitude = get_coordinates(
		", ".join(filter(None, (doc.get(field) for field in SEARCH_FIELDS)))
	)
	doc.db_set({"latitude": latitude, "longitude": longitude}, update_modified=False)


@frappe.whitelist(methods=["POST"])
def get_address_coordinates(address: str) -> tuple[float, float] | None:
	"""(latitude, longitude) of *address* for a form's map pin, looked up first when it has none.

	None when it has none and address lookups are off, so the form can tell that from a failed lookup.
	A form asks here rather than asking Nominatim itself, so the setting, the lock and the User-Agent hold.
	"""
	frappe.has_permission("Address", doc=address, throw=True)
	if not frappe.db.get_value("Address", address, "latitude"):
		if not is_address_lookup_on():
			return None
		geocode(address)
	return frappe.db.get_value("Address", address, ["latitude", "longitude"])


def get_coordinates(search: str) -> tuple[float, float]:
	"""(latitude, longitude) of the first place Nominatim finds for *search*, or (0, 0).

	A lock shared by the bench keeps every worker to one request a second.
	"""
	with filelock("churchit_nominatim", timeout=60, is_global=True):
		try:
			response = requests.get(
				f"{get_search_base_url()}/search",
				params={"q": search, "format": "jsonv2", "limit": 1},
				headers={"User-Agent": f"Churchit ({get_url()})"},
				timeout=REQUEST_TIMEOUT_SECONDS,
			)
			response.raise_for_status()
			places = response.json()
		except (requests.RequestException, ValueError):
			places = []
		finally:
			time.sleep(SECONDS_BETWEEN_REQUESTS)
	if not places:
		return 0, 0
	return float(places[0]["lat"]), float(places[0]["lon"])


def get_search_base_url() -> str:
	"""Geolocation Settings' own Nominatim server when it names one, else OpenStreetMap's."""
	settings = frappe.get_cached_doc("Geolocation Settings")
	if settings.provider == "Nomatim" and settings.base_url:
		return settings.base_url.rstrip("/")
	return NOMINATIM_URL


def geocode_missing(after: str = "") -> None:
	"""Look up the addresses with no coordinates, a batch at a time in name order, then queue the next batch.

	Each address is committed as it goes, so a job that stops loses nothing.
	"""
	if not is_address_lookup_on():
		return

	addresses = frappe.get_all(
		"Address",
		filters={"latitude": 0, "name": (">", after)},
		order_by="name asc",
		limit=BATCH,
		pluck="name",
	)
	for address in addresses:
		geocode(address)
		frappe.db.commit()
	if len(addresses) == BATCH:
		queue_missing(addresses[-1])


def queue_missing(after: str = "") -> None:
	"""Queue `geocode_missing` from the address after *after*, with time for a full batch."""
	frappe.enqueue(
		geocode_missing,
		queue="long",
		timeout=BATCH * (SECONDS_BETWEEN_REQUESTS + REQUEST_TIMEOUT_SECONDS) + 60,
		enqueue_after_commit=True,
		after=after,
	)
