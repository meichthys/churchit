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


def get_church_scope(church, include_sub_churches):
	"""Return list of church names: just the one church, or the full subtree if include_sub_churches is set.

	For non-System Managers, the result is intersected with the user's permitted churches.
	"""
	if not include_sub_churches:
		return [church]

	churches = frappe.db.sql_list(
		"""
		SELECT child.name
		FROM `tabChurch` child
		INNER JOIN `tabChurch` parent
			ON child.lft >= parent.lft AND child.rgt <= parent.rgt
		WHERE parent.name = %s
		ORDER BY child.lft
		""",
		church,
	)

	if "System Manager" not in frappe.get_roles():
		permitted = set(
			frappe.db.sql_list(
				"""
				SELECT for_value FROM `tabUser Permission`
				WHERE user = %s AND allow = 'Church'
				""",
				frappe.session.user,
			)
		)
		churches = [c for c in churches if c in permitted]

	return churches


def build_in_clause(values):
	"""Return a safely escaped SQL IN clause string, e.g. ('A', 'B')."""
	escaped = [frappe.db.escape(v) for v in values]
	return "(" + ", ".join(escaped) + ")"


def get_church_condition(filters, church_field_expr, values_dict):
	"""Build a SQL condition for church filtering and update values_dict with any needed parameters.

	Handles three cases:
	1. church + include_sub_churches: IN clause with descendants (intersected with permissions)
	2. church only: equals clause for the single church
	3. No church selected: User Permission subquery for non-System Managers, no restriction for System Managers

	Args:
		filters: dict of report filters (looks for 'church' and 'include_sub_churches')
		church_field_expr: SQL expression for the church field, e.g. "`tabPerson`.church"
		values_dict: dict to update with query parameters

	Returns:
		SQL condition string (including leading AND), or empty string if no restriction.
	"""
	church = filters.get("church") if filters else None
	include_sub_churches = frappe.utils.cint((filters or {}).get("include_sub_churches", 0))

	if church:
		if include_sub_churches:
			churches = get_church_scope(church, include_sub_churches=True)
			if not churches:
				return " AND 1=0"
			in_clause = build_in_clause(churches)
			return f" AND {church_field_expr} IN {in_clause}"
		else:
			values_dict["church"] = church
			return f" AND {church_field_expr} = %(church)s"
	else:
		if "System Manager" not in frappe.get_roles():
			values_dict["user"] = frappe.session.user
			return f""" AND {church_field_expr} IN (
				SELECT for_value FROM `tabUser Permission`
				WHERE user = %(user)s AND allow = 'Church'
			)"""
		return ""
