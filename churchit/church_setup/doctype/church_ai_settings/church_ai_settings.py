# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from churchit.ai.flow_models import queue_agent_sync
from churchit.ai.manual_knowledge import queue_sync
from churchit.ai.private_doctypes import RECOMMENDED
from churchit.ai.switch import close_mcp
from churchit.ai.triage import CHOICE_DOCTYPES, FEATURES, is_desk_user
from churchit.church_scope import allowed_churches, is_multi_church
from churchit.church_setup.doctype.church_ai_suggestion.church_ai_suggestion import SUGGESTION_DOCTYPE

# Checks that only a System Manager or a Church Manager of every church may turn on; anyone who
# may write the settings may turn them off.
TURN_ON_FIELDS = ("enabled",)
ACKNOWLEDGMENT_FIELDS = ("acknowledged", "acknowledged_by", "acknowledged_on")


class ChurchAISettings(Document):
	"""The master AI switch (churchit.ai.switch.is_ai_on) and the doctypes that Flow knowledge may not
	read (churchit.ai.flow_switch)."""

	@property
	def blocked_doctypes(self) -> set[str]:
		"""The doctypes in Blocked from Flow Knowledge."""
		return {row.document_type for row in self.blocked_knowledge_doctypes}

	@property
	def private_doctypes(self) -> set[str]:
		"""The doctypes in Only for Local or Zero Retention Models (churchit.ai.private_doctypes)."""
		return {row.document_type for row in self.get("private_model_doctypes") or []}

	def validate(self):
		before = self.get_doc_before_save()
		turned_on = [
			field for field in TURN_ON_FIELDS if self.get(field) and not (before and before.get(field))
		]
		if turned_on:
			refuse_for_some_churches(
				_("Only a System Manager or a Church Manager of every church can turn AI on.")
			)
		if before and before.blocked_doctypes - self.blocked_doctypes:
			refuse_for_some_churches(
				_(
					"Only a System Manager or a Church Manager of every church can remove a DocType from "
					"Blocked from Flow Knowledge."
				)
			)
		if before and before.private_doctypes - self.private_doctypes:
			self.check_removed_private_doctypes(before.private_doctypes - self.private_doctypes)
		self.validate_reviewers(before)
		if "enabled" in turned_on:
			self.stamp_acknowledgment()
		elif self.enabled:
			# Only turning AI on stamps who did it; a save over REST cannot rewrite the stamp.
			for fieldname in ACKNOWLEDGMENT_FIELDS:
				self.set(fieldname, before.get(fieldname))
		else:
			self.acknowledged = 0
			self.acknowledged_by = None
			self.acknowledged_on = None

	def check_removed_private_doctypes(self, removed: set[str]):
		"""Only a manager of every church loosens the list, and removing a recommended doctype warns."""
		refuse_for_some_churches(
			_(
				"Only a System Manager or a Church Manager of every church can remove a DocType from "
				"Only for Local or Zero Retention Models."
			)
		)
		if recommended := sorted(removed & set(RECOMMENDED)):
			frappe.msgprint(
				_(
					"Churchit recommends keeping {0} in Only for Local or Zero Retention Models. Churchit's "
					"own AI features can now send these records to a model labelled No training."
				).format(", ".join(_(doctype) for doctype in recommended)),
				_("Recommended DocType Removed"),
				indicator="orange",
			)

	def validate_reviewers(self, before):
		"""Only a manager of every church changes the suggestions or their reviewers, and each new or
		changed reviewer is a desk user who reads the reviewed doctypes of their church."""
		reviewers = {(row.church or None, row.user) for row in self.triage_reviewers}
		previous = {(row.church or None, row.user) for row in before.triage_reviewers} if before else set()
		turned_on = self.suggest_request_triage and not (before and before.suggest_request_triage)
		if turned_on or reviewers != previous:
			refuse_for_some_churches(
				_(
					"Only a System Manager or a Church Manager of every church can change the suggestions on "
					"new requests or their reviewers."
				)
			)
		churches = [row.church or None for row in self.triage_reviewers]
		for row in self.triage_reviewers:
			if (row.church or None, row.user) not in previous:
				check_reviewer(row, churches.count(row.church or None) > 1)
			elif not is_desk_user(row.user):
				frappe.msgprint(
					_(
						"{0} is no longer an enabled desk user, so nobody reviews the new requests of {1}."
					).format(frappe.bold(row.user), frappe.bold(row.church or _("your church"))),
					_("Choose Another Reviewer"),
					indicator="orange",
				)

	def stamp_acknowledgment(self):
		if not self.acknowledged:
			frappe.throw(_("Tick {0} to turn AI on.").format(_(self.meta.get_label("acknowledged"))))
		self.acknowledged_by = frappe.session.user
		self.acknowledged_on = now_datetime()

	def on_update(self):
		before = self.get_doc_before_save()
		if before and before.enabled and not self.enabled and close_mcp():
			self.add_comment("Info", _("Turning AI off closed Frappe's MCP server in System Settings."))
		if self.enabled and not (before and before.enabled):
			queue_agent_sync()
			queue_sync()


def check_reviewer(row, is_repeated: bool) -> None:
	"""Refuse a reviewer row that names no church on a site with several churches, repeats a church,
	or names a user who cannot review that church's new requests."""
	if is_multi_church() and not row.church:
		frappe.throw(_("Row {0}: choose the church that {1} reviews.").format(row.idx, frappe.bold(row.user)))
	if is_repeated:
		frappe.throw(_("Row {0}: each church has one reviewer.").format(row.idx))
	if not is_desk_user(row.user):
		frappe.throw(_("Row {0}: {1} is not an enabled desk user.").format(row.idx, frappe.bold(row.user)))
	for doctype in (*FEATURES, SUGGESTION_DOCTYPE):
		record = frappe.new_doc(doctype)
		record.church = row.church
		if not frappe.has_permission(doctype, "read", doc=record, user=row.user):
			frappe.throw(
				_(
					"Row {0}: {1} cannot read the {2} records of this church, so they cannot review them."
				).format(row.idx, frappe.bold(row.user), _(doctype))
			)
	for doctype in CHOICE_DOCTYPES:
		if not frappe.has_permission(doctype, "select", user=row.user):
			frappe.throw(
				_("Row {0}: {1} cannot select a {2}, so their suggestions cannot name one.").format(
					row.idx, frappe.bold(row.user), _(doctype)
				)
			)


def refuse_for_some_churches(message: str) -> None:
	"""A Church Manager restricted to some churches would decide for churches they cannot see."""
	roles = frappe.get_roles()
	if "System Manager" in roles or ("Church Manager" in roles and allowed_churches() is None):
		return
	frappe.throw(message, frappe.PermissionError)
