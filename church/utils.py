import frappe

CHURCH_COLUMN = {
	"fieldname": "church",
	"fieldtype": "Link",
	"label": "Church",
	"options": "Church",
	"width": 150,
}


def set_report_link_titles(columns, data):
	"""Replace hash names with title field values in report data for Link columns."""
	if not data:
		return

	for i, col in enumerate(columns):
		if col.get("fieldtype") != "Link" or not col.get("options"):
			continue

		doctype = col["options"]
		fieldname = col["fieldname"]
		meta = frappe.get_meta(doctype)
		if not meta.title_field:
			continue

		names = {row.get(fieldname) for row in data if row.get(fieldname)}
		if not names:
			continue

		title_map = dict(
			frappe.get_all(
				doctype,
				filters={"name": ("in", list(names))},
				fields=["name", meta.title_field],
				as_list=True,
			)
		)

		# Replace the column with a Data copy so we don't mutate shared constants
		columns[i] = {k: v for k, v in col.items() if k != "options"}
		columns[i]["fieldtype"] = "Data"

		for row in data:
			name = row.get(fieldname)
			if name and name in title_map:
				row[fieldname] = title_map[name]


def setup_web_form_church_field(context):
	"""If only one church exists, default its value and hide the field on web forms."""
	churches = frappe.get_all("Church", fields=["name"], limit=2)
	if len(churches) != 1:
		return
	church = churches[0].name
	for field in context.get("web_form_doc", {}).get("web_form_fields", []):
		if field.fieldname == "church":
			field.default = church
			field.hidden = 1
			break


def resolve_link_titles(rows, doctype):
	"""Replace hash link values with their title field values in-place.

	Discovers Link and Dynamic Link fields automatically from the doctype meta.
	Works for a single doc (pass as a one-element list) or many rows."""
	meta = frappe.get_meta(doctype)
	for df in meta.fields:
		if df.fieldtype == "Link" and df.options:
			linked_meta = frappe.get_meta(df.options)
			if not linked_meta.title_field:
				continue
			names = {row.get(df.fieldname) for row in rows if row.get(df.fieldname)}
			if not names:
				continue
			title_map = dict(
				frappe.get_all(
					df.options,
					filters={"name": ("in", list(names))},
					fields=["name", linked_meta.title_field],
					as_list=True,
				)
			)
			for row in rows:
				value = row.get(df.fieldname)
				if value and value in title_map:
					row[df.fieldname] = title_map[value]

		elif df.fieldtype == "Dynamic Link" and df.options:
			# Group rows by the doctype stored in the type field (df.options)
			by_doctype = {}
			for row in rows:
				linked_dt = row.get(df.options)
				value = row.get(df.fieldname)
				if linked_dt and value:
					by_doctype.setdefault(linked_dt, set()).add(value)
			for linked_dt, names in by_doctype.items():
				linked_meta = frappe.get_meta(linked_dt)
				if not linked_meta.title_field:
					continue
				title_map = dict(
					frappe.get_all(
						linked_dt,
						filters={"name": ("in", list(names))},
						fields=["name", linked_meta.title_field],
						as_list=True,
					)
				)
				for row in rows:
					if row.get(df.options) == linked_dt:
						value = row.get(df.fieldname)
						if value and value in title_map:
							row[df.fieldname] = title_map[value]


def show_church_column(filters):
	"""Return True if include_sub_churches is set, meaning results span multiple churches."""
	return bool(frappe.utils.cint((filters or {}).get("include_sub_churches", 0)))


def get_church_condition(filters, doctype, doc_name_expr, values_dict):
	"""Build a SQL WHERE condition using the Church Subscription child table.

	Args:
		filters: dict of report filters (looks for 'church' and 'include_sub_churches')
		doctype: the doctype being filtered (e.g. "Prayer Request")
		doc_name_expr: SQL expression for the doc name field, e.g. "`tabPrayer Request`.`name`"
		values_dict: dict to update with query parameters

	Returns:
		SQL condition string (including leading AND), or empty string if no restriction.
	"""
	church = filters.get("church") if filters else None
	include_sub = frappe.utils.cint((filters or {}).get("include_sub_churches", 0))
	is_system_manager = "System Manager" in frappe.get_roles()
	esc_dt = frappe.db.escape(doctype)

	def _subscribed_exists(extra_condition=""):
		return f""" AND EXISTS (
			SELECT 1 FROM `tabChurch Subscription` _cs
			WHERE _cs.parent = {doc_name_expr}
			AND _cs.parenttype = {esc_dt}
			AND _cs.parentfield = 'church_subscriptions'
			AND _cs.subscribed = 1
			{extra_condition}
		)"""

	def _subtree_join(church_name):
		lft, rgt = frappe.db.get_value("Church", church_name, ["lft", "rgt"])
		return (
			f"AND _cs.church IN ("
			f"SELECT name FROM `tabChurch` WHERE lft >= {lft} AND rgt <= {rgt})"
		)

	if is_system_manager:
		if not church:
			return ""
		if include_sub:
			return _subscribed_exists(_subtree_join(church))
		else:
			values_dict["_sm_church"] = church
			return _subscribed_exists("AND _cs.church = %(_sm_church)s")

	user_church = frappe.db.get_value("User", frappe.session.user, "church")
	if not user_church:
		return " AND 1=0"

	if church:
		if include_sub:
			# Subtree filter intersected with user's own church
			lft, rgt = frappe.db.get_value("Church", church, ["lft", "rgt"])
			values_dict["_user_church"] = user_church
			return _subscribed_exists(
				f"AND _cs.church IN ("
				f"SELECT name FROM `tabChurch` WHERE lft >= {lft} AND rgt <= {rgt}) "
				f"AND _cs.church = %(_user_church)s"
			)
		else:
			values_dict["_filter_church"] = church
			return _subscribed_exists("AND _cs.church = %(_filter_church)s")
	else:
		values_dict["_user_church"] = user_church
		return _subscribed_exists("AND _cs.church = %(_user_church)s")
