# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Queue the lookup of coordinates for every address saved before addresses had them.

One background job at a time works through the addresses, one a second, so the Map view fills in slowly.
Migrate adds the coordinate fields after the patches, so the patch adds them first for the job to find.
"""

import json

import frappe
from frappe.modules.utils import sync_customizations_for_doctype

from churchit.church_people.geocoding import queue_missing


def execute():
	folder = frappe.get_app_path("churchit", "church_customizations", "custom")
	with open(f"{folder}/address.json") as file:
		sync_customizations_for_doctype(json.load(file), folder, "address.json")
	frappe.clear_cache(doctype="Address")
	queue_missing()
