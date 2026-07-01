"""AI was used to generate portions of this page"""

import json

import frappe

# Disable caching for sermon presentation page to ensure users always see up-to-date content
no_cache = 1
allow_guest = True


def _parse_display_fields(raw):
	"""Parse display_fields stored as JSON or legacy comma-separated."""
	if not raw:
		return []
	try:
		parsed = json.loads(raw)
		if isinstance(parsed, list):
			return parsed
	except (json.JSONDecodeError, TypeError):
		return [{"fieldname": f.strip(), "show_label": 1, "is_title": 0} for f in raw.split(",") if f.strip()]
	return []


def _render_field(val, df, show_label):
	"""Render a single field value as HTML for the presentation."""
	label = df.label if df else "Field"
	fieldtype = df.fieldtype if df else "Data"

	if fieldtype in ("Text Editor", "HTML"):
		prefix = f"<p><strong>{label}:</strong></p>" if show_label else ""
		return prefix + val

	if fieldtype == "Attach Image":
		img = f'<img src="{val}" alt="{label}" style="max-width:80%;max-height:50vh;border-radius:8px;">'
		return f"<p><strong>{label}:</strong></p>{img}" if show_label else img

	if fieldtype == "Attach":
		link = f'<a href="{val}" target="_blank">{val}</a>'
		return f"<p><strong>{label}:</strong> {link}</p>" if show_label else f"<p>{link}</p>"

	if fieldtype == "Check":
		text = "Yes" if val else "No"
		return f"<p><strong>{label}:</strong> {text}</p>" if show_label else f"<p>{text}</p>"

	return f"<p><strong>{label}:</strong> {val}</p>" if show_label else f"<p>{val}</p>"


def _build_content_from_selected_fields(linked_doc, meta, field_configs):
	"""Build slide title and content HTML from explicitly selected fields."""
	fields_by_name = {df.fieldname: df for df in meta.fields}
	title = ""
	parts = []

	for config in field_configs:
		fieldname = config.get("fieldname") if isinstance(config, dict) else config
		show_label = config.get("show_label", 1) if isinstance(config, dict) else 1
		is_title = config.get("is_title", 0) if isinstance(config, dict) else 0

		val = getattr(linked_doc, fieldname, None)
		if val is None:
			continue

		if is_title:
			title = str(val)
		else:
			parts.append(_render_field(val, fields_by_name.get(fieldname), show_label))

	return title, "\n".join(parts)


def get_context(context):
	name = frappe.form_dict.get("name")
	if not name:
		frappe.throw("Please specify a sermon name", frappe.exceptions.ValidationError)

	sermon = frappe.get_doc("Sermon", name)
	if not sermon.publish and not frappe.has_permission("Sermon", doc=sermon):
		frappe.throw("This sermon is not available.", frappe.PermissionError)

	slides = []
	for row in sermon.get("slides", []):
		slide_data = {
			"idx": row.idx,
			"slide_type": row.slide_type,
			"slide_name": row.slide,
			"notes": row.notes or "",
			"content": "",
			"title": row.slide,
		}

		try:
			linked_doc = frappe.get_doc(row.slide_type, row.slide)
			field_configs = _parse_display_fields(row.display_fields)
			meta = frappe.get_meta(row.slide_type)

			if field_configs:
				title, slide_data["content"] = _build_content_from_selected_fields(
					linked_doc, meta, field_configs
				)
				if title:
					slide_data["title"] = title
			else:
				slide_data["title"] = linked_doc.get_title() if hasattr(linked_doc, "get_title") else row.slide
				slide_data["content"] = ""
		except Exception:
			slide_data["content"] = f"<p>Could not load {row.slide_type}: {row.slide}</p>"

		slides.append(slide_data)

	prepared_by_name = ""
	if sermon.prepared_by:
		prepared_by_name = frappe.get_doc("Person", sermon.prepared_by).get_title()

	context.sermon_title = sermon.title or sermon.name
	context.prepared_by = prepared_by_name
	context.slides = slides
	context.no_header = 1
	context.no_sidebar = 1
	context.no_breadcrumbs = 1
