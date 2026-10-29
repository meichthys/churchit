# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.church_communications.doctype.communication_consent.communication_consent import EMAIL, SMS
from churchit.church_communications.sending import check_placeholders, send
from churchit.church_people.followup import STEP_REACHED
from churchit.church_people.group_api import add_member
from churchit.church_scope import refuse_another_churches_record

SEND_EMAIL = "Send Email"
SEND_TEXT = "Send Text"
ADD_TO_GROUP = "Add to Group"
ADD_TAG = "Add Tag"
# The fields each action needs. The form asks for them, but Frappe does not check mandatory_depends_on.
REQUIRED_FIELDS = {
	SEND_EMAIL: ("purpose", "email_template"),
	SEND_TEXT: ("purpose", "message"),
	ADD_TO_GROUP: ("group",),
	ADD_TAG: ("tag",),
}
# The names a message may use besides the person's own.
CONTEXT = ("step",)


class FollowupAction(Document):
	"""Something the workflow does by itself when a card opens, reaches a step or closes. Its parent validates it."""

	def validate_action(self, workflow: Document):
		for fieldname in REQUIRED_FIELDS.get(self.action, ()):
			if not self.get(fieldname):
				frappe.throw(
					_("Row {0}: {1} needs a {2}.").format(
						self.idx, _(self.action), _(self.meta.get_label(fieldname))
					)
				)
		if self.run_on != STEP_REACHED:
			self.step = None
		elif self.step and self.step not in workflow.steps_in_order():
			frappe.throw(
				_("Row {0}: {1} is not a step of this workflow.").format(self.idx, frappe.bold(self.step))
			)
		self.validate_message()
		if self.action == ADD_TO_GROUP:
			refuse_another_churches_record(workflow, "Group", self.group)

	def validate_message(self):
		"""A message may use only the person's names and {{ step }}, so it does not fail when it is sent."""
		if self.action == SEND_TEXT:
			check_placeholders(self.message, _("Row {0}: Text Message").format(self.idx), extra=CONTEXT)
		elif self.action == SEND_EMAIL:
			template = frappe.get_doc("Email Template", self.email_template)
			message = template.response_html if template.use_html else template.response
			for label, content in ((_("Subject"), template.subject), (_("Message"), message)):
				check_placeholders(
					content,
					_("Row {0}: {1} of {2}").format(self.idx, label, self.email_template),
					extra=CONTEXT,
				)

	def run(self, card: Document, key: str, step: str) -> bool:
		"""Do this action for *card*'s person at *step* and return False when there was nothing to do.

		A message goes once for each *key*, and only to a person who allows it.
		"""
		context = {"step": step}
		if self.action == SEND_EMAIL:
			sent = send(
				[card.person],
				EMAIL,
				self.purpose,
				card,
				key=key,
				template=self.email_template,
				context=context,
			)
			return bool(sent)
		if self.action == SEND_TEXT:
			return bool(
				send([card.person], SMS, self.purpose, card, key=key, text=self.message, context=context)
			)
		if self.action == ADD_TO_GROUP:
			return self.add_to_group(card.person)
		return self.add_tag(card.person)

	def add_to_group(self, person: str) -> bool:
		# A second job for the same group waits here, then finds the member this one adds.
		group = frappe.get_doc("Group", self.group, for_update=True)
		if any(member.person == person for member in group.members):
			return False
		add_member(group, person)
		return True

	def add_tag(self, person: str) -> bool:
		"""Tag *person* the way `DocTags.add` does, which checks write on the Person as the saver, a guest too.

		The Tag Link insert refuses a Tag that does not exist, and `run_action` then undoes `_user_tags`.
		"""
		# Read under a lock: a second job tagging this person waits here, then sees this tag.
		tags = (frappe.db.get_value("Person", person, "_user_tags", for_update=True) or "").split(",")
		if self.tag in tags:
			return False
		tags = ",".join(filter(None, [*tags, self.tag]))
		frappe.db.set_value("Person", person, "_user_tags", tags, update_modified=False)
		frappe.get_doc(
			{
				"doctype": "Tag Link",
				"document_type": "Person",
				"document_name": person,
				"title": frappe.db.get_value("Person", person, "full_name"),
				"tag": self.tag,
			}
		).insert(ignore_permissions=True)
		return True
