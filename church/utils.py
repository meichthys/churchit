import frappe


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
