"""AI was used to generate portions of this page"""

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html

from churchit.church_scope import default_church
from churchit.scripture import get_default_translation, get_passage, is_readable

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


def scripture_slide(reference, translation):
	"""A Scripture slide's title and verses, or its reference alone when the viewer may not read the text."""
	translation = translation or get_default_translation()
	if not is_readable(translation):
		return {"title": reference, "content": ""}
	verses = []
	for section in get_passage(reference, translation):
		for verse in section["verses"]:
			lines = escape_html(verse["text"]).replace("\n", "<br>")
			verses.append(f"<sup>{verse['number']}</sup> {lines}")
	return {
		"title": f"{reference} ({translation})",
		"content": f'<p class="slide-scripture">{" ".join(verses)}</p>',
	}


def get_public_slide(slide_type, name) -> dict | None:
	"""The fields `/beliefs` and `/missions` show of a published Belief or Missionary, and a public domain Song, for any viewer."""
	if slide_type == "Belief":
		return frappe.db.get_value(
			"Belief",
			{"name": name, "publish": 1},
			["title", "belief_statement", "bible_references"],
			as_dict=True,
		)
	if slide_type == "Missionary":
		return frappe.db.get_value(
			"Missionary",
			{"name": name, "publish": 1, "sensitive": 0},
			["title", "agency", "country", "photo", "website"],
			as_dict=True,
		)
	if slide_type == "Song":
		song = frappe.db.get_value(
			"Song", {"name": name, "public_domain": 1}, ["title", "copyright", "ccli"], as_dict=True
		)
		if song:
			# church-scope: the slides of the one public domain Song read above.
			song["slides"] = frappe.get_all(
				"Slide",
				filters={"parenttype": "Song", "parent": name},
				fields=["content", "background_image"],
				order_by="idx",
			)
			for slide in song["slides"]:
				# A guest cannot open a private file, and its name is not public.
				if (slide.background_image or "").startswith("/private/"):
					slide.background_image = None
		return song
	return None


def song_slides(song, church) -> list[dict]:
	"""One slide for each of a Song's slides, then its copyright with the CCLI numbers of *church*."""
	slides = [
		{
			"title": "",
			"content": slide.get("content") or "",
			"background_image": slide.get("background_image"),
		}
		for slide in song.get("slides")
	]
	credits = []
	if song.get("copyright"):
		credits.append(f"<p>{escape_html(song.get('copyright'))}</p>")
	if song.get("ccli"):
		license_number = frappe.db.get_value("Church", church, "ccli_license_number") if church else None
		line = _("CCLI Song # {0}").format(song.get("ccli"))
		if license_number:
			line = _("CCLI Song # {0}, CCLI License # {1}").format(song.get("ccli"), license_number)
		credits.append(f"<p>{escape_html(line)}</p>")
	return [*slides, {"title": escape_html(song.get("title")), "content": "".join(credits)}]


def record_slides(row, church) -> list[dict]:
	"""A record's slides: the whole record to a reader of it, else only its public fields.

	A Song with no fields picked shows its own slides.
	"""
	record = None
	if frappe.db.exists(row.slide_type, row.slide):
		record = frappe.get_doc(row.slide_type, row.slide)
		if frappe.has_permission(row.slide_type, "read", doc=record):
			record.apply_fieldlevel_read_permissions()
		else:
			record = get_public_slide(row.slide_type, row.slide)
	if not record:
		return [{"title": "", "content": f"<p>{_('This slide is not public')}</p>"}]

	field_configs = _parse_display_fields(row.display_fields)
	if field_configs:
		title, content = _build_content_from_selected_fields(
			record, frappe.get_meta(row.slide_type), field_configs
		)
		return [{"title": title or row.slide, "content": content}]
	if row.slide_type == "Song":
		return song_slides(record, church)
	return [{"title": record.get_title() if isinstance(record, Document) else record.title, "content": ""}]


def get_context(context):
	context.no_header = 1
	context.no_sidebar = 1
	context.no_breadcrumbs = 1

	if frappe.form_dict.get("song"):
		song = frappe.get_doc("Song", frappe.form_dict.get("song"))
		frappe.has_permission("Song", "read", doc=song, throw=True)
		song.apply_fieldlevel_read_permissions()
		context.sermon_title = escape_html(song.title)
		context.prepared_by = escape_html(song.authors or "")
		context.slides = song_slides(song, default_church())
		return

	name = frappe.form_dict.get("name")
	if not name:
		frappe.throw(_("Please specify a sermon name"), frappe.exceptions.ValidationError)

	sermon = frappe.get_doc("Sermon", name)
	if not sermon.publish and not frappe.has_permission("Sermon", doc=sermon):
		frappe.throw(_("This sermon is not available."), frappe.PermissionError)

	# get(): the published-field scan would read church as a field of every slide doctype.
	# A shared sermon, and every record on a single-church site, stores no church.
	church = sermon.get("church") or default_church()
	slides = []
	for row in sermon.get("slides", []):
		# get(): the published-field scan reads an attribute named notes as Missionary notes.
		slide_data = {"idx": row.idx, "slide_type": row.slide_type, "notes": row.get("notes") or ""}
		if row.scripture:
			slides.append({**slide_data, **scripture_slide(row.scripture, row.translation)})
		else:
			first, *rest = record_slides(row, church)
			slides.append({**slide_data, **first})
			slides.extend({**slide_data, "notes": "", **slide} for slide in rest)

	prepared_by_name = ""
	if sermon.prepared_by:
		prepared_by_name = frappe.get_doc("Person", sermon.prepared_by).get_title()

	context.sermon_title = sermon.title or sermon.name
	context.prepared_by = prepared_by_name
	context.slides = slides
