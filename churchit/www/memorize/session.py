# Copyright (c) 2026, meichthys and contributors

import json

import frappe
from frappe import _

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/memorize"
		raise frappe.Redirect

	item_name = frappe.form_dict.get("item")
	mode = (frappe.form_dict.get("mode") or "type").lower()
	if mode not in ("type", "blur"):
		frappe.throw(_("Invalid mode"))
	if not item_name:
		frappe.throw(_("Missing item"))

	item = frappe.get_doc("Bible Memory Item", item_name)
	if item.user != frappe.session.user:
		frappe.throw(_("Not allowed"), frappe.PermissionError)

	ref = frappe.get_doc("Bible Reference", item.bible_reference)
	if not ref.reference_text:
		from churchit.church_study.bible_api import fetch_reference_text

		fetch_reference_text(ref.name)
		ref.reload()

	word_mistakes_raw = item.word_mistakes
	if isinstance(word_mistakes_raw, dict):
		word_mistakes_raw = json.dumps(word_mistakes_raw)
	elif not word_mistakes_raw:
		word_mistakes_raw = "{}"

	context.no_cache = 1
	context.no_sidebar = 1
	context.no_breadcrumbs = 1
	context.no_header = 1
	context.item_name = item.name
	context.progress = item.progress or 0
	context.memorized = int(item.memorized or 0)
	context.reference_label = ref.reference or ref.name
	context.reference_text = ref.reference_text or ""
	context.word_mistakes_json = word_mistakes_raw
	context.mode = mode
