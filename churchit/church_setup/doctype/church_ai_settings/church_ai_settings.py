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
from churchit.church_scope import allowed_churches

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


def refuse_for_some_churches(message: str) -> None:
	"""A Church Manager restricted to some churches would decide for churches they cannot see."""
	roles = frappe.get_roles()
	if "System Manager" in roles or ("Church Manager" in roles and allowed_churches() is None):
		return
	frappe.throw(message, frappe.PermissionError)
