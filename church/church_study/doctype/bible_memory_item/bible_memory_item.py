# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class BibleMemoryItem(Document):
	def before_insert(self):
		if not self.user:
			self.user = frappe.session.user

	def validate(self):
		duplicate = frappe.db.exists(
			"Bible Memory Item",
			{
				"user": self.user,
				"bible_reference": self.bible_reference,
				"name": ("!=", self.name or ""),
			},
		)
		if duplicate:
			frappe.throw(_("This passage is already in your memory list."))

	@frappe.whitelist()
	def record_mistake(self, word_index):
		self._require_self()
		mistakes = self._load_word_mistakes()
		key = str(int(word_index))
		mistakes[key] = mistakes.get(key, 0) + 1
		self.word_mistakes = json.dumps(mistakes)
		self.progress = max(0, (self.progress or 0) - 2)
		self.save(ignore_permissions=False)
		return {"progress": self.progress, "word_mistakes": mistakes}

	@frappe.whitelist()
	def complete_session(self, mode, mistakes=0, correct_word_indices=None):
		self._require_self()
		if mode not in ("type", "blur"):
			frappe.throw(_("Invalid mode for completion"))

		mistakes = int(mistakes or 0)
		correct_word_indices = self._parse_indices(correct_word_indices)

		if mode == "blur":
			bonus = 5
			self.progress = min(99, (self.progress or 0) + bonus)
		else:
			wm = self._load_word_mistakes()
			for idx in correct_word_indices:
				k = str(int(idx))
				if k in wm:
					wm[k] = max(0, wm[k] - 1)
					if wm[k] == 0:
						del wm[k]
			self.word_mistakes = json.dumps(wm)

			bonus = 50 if mistakes == 0 else (10 if mistakes < 3 else 0)
			self.progress = min(100, (self.progress or 0) + bonus)

			if mistakes == 0:
				self.times_memorized = (self.times_memorized or 0) + 1
			if self.progress >= 100 and not self.memorized:
				self.memorized = 1
				self.memorized_on = today()

		self.save(ignore_permissions=False)

		session = frappe.get_doc(
			{
				"doctype": "Memory Session",
				"bible_memory_item": self.name,
				"user": self.user,
				"mode": "Type" if mode == "type" else "Blur",
				"mistakes": mistakes if mode == "type" else 0,
				"progress_delta": bonus,
				"completed": 1,
			}
		)
		session.insert(ignore_permissions=False)

		return {
			"progress": self.progress,
			"memorized": int(self.memorized or 0),
			"memorized_on": str(self.memorized_on) if self.memorized_on else None,
			"times_memorized": self.times_memorized or 0,
			"word_mistakes": self._load_word_mistakes(),
			"bonus": bonus,
		}

	def _require_self(self):
		if self.user != frappe.session.user:
			frappe.throw(_("Not allowed"), frappe.PermissionError)

	def _load_word_mistakes(self):
		if not self.word_mistakes:
			return {}
		if isinstance(self.word_mistakes, dict):
			return dict(self.word_mistakes)
		try:
			return json.loads(self.word_mistakes)
		except (ValueError, TypeError):
			return {}

	@staticmethod
	def _parse_indices(raw):
		if raw is None or raw == "":
			return []
		if isinstance(raw, str):
			try:
				raw = json.loads(raw)
			except (ValueError, TypeError):
				return []
		if not isinstance(raw, list):
			return []
		out = []
		for v in raw:
			try:
				out.append(int(v))
			except (TypeError, ValueError):
				continue
		return out


@frappe.whitelist()
def record_mistake(name, word_index):
	"""Module-level wrapper for BibleMemoryItem.record_mistake"""
	doc = frappe.get_doc("Bible Memory Item", name)
	return doc.record_mistake(word_index)


@frappe.whitelist()
def complete_session(name, mode, mistakes=0, correct_word_indices=None):
	"""Module-level wrapper for BibleMemoryItem.complete_session"""
	doc = frappe.get_doc("Bible Memory Item", name)
	return doc.complete_session(mode, mistakes, correct_word_indices)
