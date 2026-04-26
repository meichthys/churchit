import frappe


def set_report_link_titles(columns, data):
	"""Pre-fetch titles for Link/Dynamic Link columns and attach them to each row.

	Columns stay typed as Link so the cell stays clickable. Each row gets a
	`_<fieldname>_link_title` key whose value is the linked doc's title. The
	companion JS hook in `church_utils.js` reads that key and primes
	`frappe._link_titles` so the desk's Link formatter shows the title."""
	if not data:
		return

	for col in columns:
		fieldtype = col.get("fieldtype")
		fieldname = col.get("fieldname")

		if fieldtype == "Link" and col.get("options"):
			doctype = col["options"]
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

			title_key = f"_{fieldname}_link_title"
			for row in data:
				name = row.get(fieldname)
				title = title_map.get(name) if name else None
				if title and title != name:
					row[title_key] = title

		elif fieldtype == "Dynamic Link" and col.get("options"):
			# `options` here is the row field that holds the target doctype.
			type_field = col["options"]
			by_doctype = {}
			for row in data:
				linked_dt = row.get(type_field)
				value = row.get(fieldname)
				if linked_dt and value:
					by_doctype.setdefault(linked_dt, set()).add(value)

			title_key = f"_{fieldname}_link_title"
			for linked_dt, names in by_doctype.items():
				try:
					linked_meta = frappe.get_meta(linked_dt)
				except Exception:
					continue
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
				for row in data:
					if row.get(type_field) != linked_dt:
						continue
					value = row.get(fieldname)
					title = title_map.get(value) if value else None
					if title and title != value:
						row[title_key] = title


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
