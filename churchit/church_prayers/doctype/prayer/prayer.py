# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Count
from frappe.utils import getdate

from churchit.church_prayers.prayer_access import PRAYER_REQUEST
from churchit.church_scope import refuse_another_churches_parent


class Prayer(Document):
	def validate(self):
		refuse_another_churches_parent(
			self, "person", _("{0} belongs to another church, so only that church can record their prayers.")
		)
		self.refuse_requests_the_user_cannot_read()
		# Locked before the topic rows are written, so two prayers for one request wait for each other.
		lock_requests(get_prayed_requests(self) | get_prayed_requests(self.get_doc_before_save()))

	def refuse_requests_the_user_cannot_read(self):
		"""A new topic changes the request's count, so the user must be able to open the request."""
		if self.flags.ignore_permissions:
			return
		added = get_prayed_requests(self) - get_prayed_requests(self.get_doc_before_save())
		for name in sorted(added):
			if not frappe.has_permission(PRAYER_REQUEST, "read", doc=name):
				frappe.throw(
					_("You cannot pray for a prayer request that you cannot open."), frappe.PermissionError
				)

	def before_save(self):
		full_name = frappe.db.get_value("Person", self.person, "full_name") if self.person else None
		self.title = get_prayer_title(full_name, self.date)

	def on_update(self):
		recount_prayers(get_prayed_requests(self) | get_prayed_requests(self.get_doc_before_save()))

	def on_trash(self):
		lock_requests(get_prayed_requests(self))

	def after_delete(self):
		recount_prayers(get_prayed_requests(self))


def get_prayer_title(full_name: str | None, date: datetime | str | None) -> str:
	"""Who prayed and on which day, such as 'James Wilson, 2026-10-20'. Lists and links show it.

	The day is ISO, as in a Collection's title, so a stored title keeps its meaning when the date format changes.
	"""
	day = str(getdate(date)) if date else None
	return ", ".join(part for part in (full_name, day) if part)


def get_prayed_requests(prayer: Prayer | None) -> set[str]:
	"""The Prayer Requests that the topics of *prayer* name."""
	if not prayer:
		return set()
	return {row.topic for row in prayer.topics if row.topic_type == PRAYER_REQUEST and row.topic}


def lock_requests(requests: set[str]) -> None:
	for name in sorted(requests):
		frappe.db.get_value(PRAYER_REQUEST, name, "name", for_update=True)


def recount_prayers(requests: set[str]) -> None:
	"""Store on each request how many Prayers name it, without moving it up the lists."""
	# church-scope: a count of the prayers for one request, whoever recorded them
	Topic = frappe.qb.DocType("Prayer Topic")
	lock_requests(requests)
	for name in sorted(requests):
		# A locking read, because a plain one answers from a snapshot older than the lock.
		count = (
			frappe.qb.from_(Topic)
			.select(Count(Topic.parent).distinct())
			.where(
				(Topic.parenttype == "Prayer") & (Topic.topic_type == PRAYER_REQUEST) & (Topic.topic == name)
			)
			.for_update()
			.run()[0][0]
		)
		frappe.db.set_value(PRAYER_REQUEST, name, "prayer_count", count, update_modified=False)
