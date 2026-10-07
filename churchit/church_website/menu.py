# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Keeps the website menu in step with which Web Pages are published."""

import frappe
from frappe import _
from frappe.utils import escape_html


def sync_web_page(page, method=None):
	"""Put a Web Page on the menu when it is published, and take its links down when it is not.

	Only a change to *Published* counts, so a page the church took off the menu
	stays off while it is edited.
	"""
	if not page.has_value_changed("published"):
		return
	if page.published:
		add_to_menu(page)
	else:
		remove_from_menu(page)


def add_to_menu(page):
	"""Append the page to the website menu unless a menu item already links to it."""
	settings = frappe.get_doc("Website Settings")
	if any(get_route(row.url) == page.route for row in settings.top_bar_items):
		return
	settings.append("top_bar_items", {"label": page.title, "url": f"/{page.route}"})
	settings.save()
	frappe.msgprint(
		_("Added {0} to the website menu.").format(frappe.bold(escape_html(page.title))),
		indicator="green",
		alert=True,
	)


def remove_from_menu(page, method=None):
	"""Remove every menu and footer link to the page."""
	settings = frappe.get_doc("Website Settings")
	links = [
		row for row in settings.top_bar_items + settings.footer_items if get_route(row.url) == page.route
	]
	if not links:
		return
	for row in links:
		settings.remove(row)
	settings.save()
	frappe.msgprint(
		_("Removed {0} from the website menu.").format(frappe.bold(escape_html(page.title))),
		indicator="green",
		alert=True,
	)


def get_route(url):
	"""The route a site-relative link points at, or None for an external link or the site root."""
	if not url or not url.startswith("/"):
		return None
	return url.lstrip("/").split("?")[0].split("#")[0].rstrip("/") or None
