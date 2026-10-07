import frappe
from frappe import _

from churchit.church_people.member_access import RECIPIENT_DOCTYPES, get_recipient_filters
from churchit.church_website.menu import get_route
from churchit.church_website.published_fields import published_field_map


@frappe.whitelist(allow_guest=False)
def get_published_fields(doctype: str | None = None):
	"""Where the website shows each field, as ``{doctype: {fieldname: [source, …]}}``.

	*doctype* narrows the answer to that doctype's fields, which is what a
	browser still running a cached copy of the badge script asks for.
	"""
	frappe.only_for(["Church Manager", "System Manager"])
	published = published_field_map()
	return published.get(doctype, {}) if doctype else published


@frappe.whitelist(allow_guest=False)
def get_recipient_doctypes():
	"""The doctypes a prayer or alms request may name as its recipient."""
	return [{"name": doctype} for doctype in RECIPIENT_DOCTYPES]


@frappe.whitelist(allow_guest=False)
def get_published_web_page(url: str | None):
	"""The published Web Page a navbar/footer link points at, or None.

	Only site-relative links can name a Web Page; www/ pages and external links
	have nothing to un-publish.
	"""
	frappe.only_for(["Church Manager", "System Manager"])
	route = get_route(url)
	if not route:
		return None
	return frappe.db.get_value(
		"Web Page", {"route": route, "published": 1}, ["name", "title", "route"], as_dict=True
	)


@frappe.whitelist(allow_guest=False)
def search_church_recipient(doctype: str, txt: str | None):
	"""Names of the records a member may pray for or ask alms for, as ``[{name, label}]``.

	Runs past DocPerms on purpose: a member reads only their own Person, and a
	name and a title are all this returns.
	"""
	filters = get_recipient_filters(doctype)
	title_field = frappe.get_meta(doctype).title_field or "name"
	or_filters = [["name", "like", f"%{txt}%"], [title_field, "like", f"%{txt}%"]] if txt else None
	return frappe.get_all(
		doctype,
		filters=filters,
		or_filters=or_filters,
		fields=["name", f"{title_field} as label"],
		order_by=f"{title_field} asc",
		limit=20,
	)
