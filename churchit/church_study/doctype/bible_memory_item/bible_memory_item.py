# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from urllib.parse import quote

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html, today

from churchit.scripture import format_reference

ASSIGNING_ROLES = {"Church Manager", "System Manager", "Administrator"}


class BibleMemoryItem(Document):
	def before_insert(self):
		if not self.user:
			self.user = frappe.session.user

	def validate(self):
		self.bible_reference = format_reference(self.bible_reference)
		duplicate = frappe.db.exists(
			"Bible Memory Item",
			{
				"user": self.user,
				"bible_reference": self.bible_reference,
				"translation": self.translation,
				"name": ("!=", self.name or ""),
			},
		)
		if duplicate:
			frappe.throw(_("This passage is already in your memory list."))

		# Remove Memorized status if progress falls below 100%
		if (self.progress or 0) < 100 and self.memorized:
			self.memorized = 0
			self.memorized_on = None

	def on_trash(self):
		frappe.db.delete("Memory Session", {"bible_memory_item": self.name})

	@frappe.whitelist()
	def record_mistake(self, word_index: int):
		self._require_self()
		mistakes = self._load_word_mistakes()
		key = str(int(word_index))
		mistakes[key] = mistakes.get(key, 0) + 1
		self.word_mistakes = json.dumps(mistakes)
		self.progress = max(0, (self.progress or 0) - 2)
		self.save(ignore_permissions=False)
		return {"progress": self.progress, "word_mistakes": mistakes}

	@frappe.whitelist()
	def complete_session(
		self, mode: str, mistakes: int = 0, correct_word_indices: str | list[int] | None = None
	):
		self._require_self()
		if mode not in ("type", "blur"):
			frappe.throw(_("Invalid mode for completion"))

		mistakes = int(mistakes or 0)
		correct_word_indices = self._parse_indices(correct_word_indices)

		if mode == "blur":
			current = self.progress or 0
			bonus = 0 if current >= 100 else 5
			self.progress = min(99, current + bonus) if current < 100 else 100
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
def assign_memory(
	reference: str, translation: str, users: str | list[str] | None = None, group: str | None = None
):
	"""Add a passage to the memory list of each user, and of each group member with a portal login.

	Only managers may assign, and a user who already has the passage is skipped.
	"""
	# Before the group is read: its members' names come back in the result.
	if not set(frappe.get_roles()) & ASSIGNING_ROLES:
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	users = as_list(users)
	missing_users = []
	if group:
		group_users, missing_users = get_group_users(group)
		users += group_users
	if not users:
		frappe.throw(_("Choose a user, or a group with members who have a portal login."))

	reference = format_reference(reference)
	created = skipped = 0
	for user in dict.fromkeys(users):
		if frappe.db.exists(
			"Bible Memory Item", {"user": user, "bible_reference": reference, "translation": translation}
		):
			skipped += 1
			continue
		assigned_by = frappe.session.user if frappe.session.user != user else None
		frappe.get_doc(
			{
				"doctype": "Bible Memory Item",
				"user": user,
				"bible_reference": reference,
				"translation": translation,
				"assigned_by": assigned_by,
			}
		).insert(ignore_permissions=True)
		created += 1
	return {"created": created, "skipped": skipped, "missing_users": missing_users}


def get_group_users(group):
	"""The portal logins of a group's members, and a link to each member who has none."""
	frappe.has_permission("Group", doc=group, throw=True)
	GroupMember = frappe.qb.DocType("Group Member")
	# church-scope: the members of one group the caller may read
	Person = frappe.qb.DocType("Person")
	members = (
		frappe.qb.from_(GroupMember)
		.join(Person)
		.on(Person.name == GroupMember.person)
		.select(Person.name, Person.full_name, Person.user)
		.where((GroupMember.parent == group) & (GroupMember.parenttype == "Group"))
		.run(as_dict=True)
	)
	missing = [
		f'<a href="/app/person/{quote(member.name)}">{escape_html(member.full_name or member.name)}</a>'
		for member in members
		if not member.user
	]
	return [member.user for member in members if member.user], missing


def as_list(value):
	"""A JSON list, one value or nothing, as a list."""
	if isinstance(value, str):
		return frappe.parse_json(value) if value.startswith("[") else [value]
	return list(value or [])


@frappe.whitelist()
def record_mistake(name: str, word_index: int):
	"""Module-level wrapper for BibleMemoryItem.record_mistake"""
	doc = frappe.get_doc("Bible Memory Item", name)
	return doc.record_mistake(word_index)


@frappe.whitelist()
def complete_session(
	name: str, mode: str, mistakes: int = 0, correct_word_indices: str | list[int] | None = None
):
	"""Module-level wrapper for BibleMemoryItem.complete_session"""
	doc = frappe.get_doc("Bible Memory Item", name)
	return doc.complete_session(mode, mistakes, correct_word_indices)
