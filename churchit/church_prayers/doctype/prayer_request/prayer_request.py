# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document

from churchit.church_people.doctype.note_category.note_category import PASTORAL_ROLES
from churchit.church_people.member_access import pin_to_members_own_person, validate_members_recipient
from churchit.church_prayers.prayer_access import (
	PRAYER_REQUEST,
	PRAYER_TEAM_ROLE,
	get_community_filters,
	get_open_request_filters,
)
from churchit.utils import resolve_link_titles

PRAYER_TEAM_NOTIFICATION = "New Prayer Request for the Prayer Team"
PRAYER_TEAM_SUBJECT = "{% if doc.urgent %}Urgent{% else %}New{% endif %} prayer request: {{ doc.title }}"
PRAYER_TEAM_MESSAGE = """<p>{% if doc.urgent %}<strong>Urgent.</strong> {% endif %}A new prayer request was added{% if church_name(doc) %} at {{ church_name(doc) | e }}{% endif %}.</p>

<ul>
  <li><strong>Title:</strong> {{ doc.title | e }}</li>
  {% if doc.requestor %}<li><strong>From:</strong> {{ frappe.db.get_value("Person", doc.requestor, "full_name") | e }}</li>{% elif doc.owner == "Guest" %}<li><strong>From:</strong> A guest on the website</li>{% endif %}
  {% if doc.recipient_name %}<li><strong>For:</strong> {{ doc.recipient_name | e }}</li>{% endif %}
  <li><strong>Type:</strong> {{ doc.type | e }}</li>
  <li><strong>Visibility:</strong> {{ doc.visibility }}</li>
</ul>

<p style="white-space: pre-line">{{ doc.request | e }}</p>

{% if doc.approved_for_list %}<p><a href="{{ frappe.utils.get_url("/community-prayer-requests/" ~ doc.name) }}">Pray for this request on Community Prayer Requests</a></p>
{% else %}<p>It waits for approval before it shows on Community Prayer Requests.</p>
{% endif %}<p>Staff can <a href="{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}">open it in the desk</a>.</p>
"""
PRIVATE_NOTIFICATION = "New Private Prayer Request"
PRIVATE_SUBJECT = "{% if doc.urgent %}Urgent{% else %}New{% endif %} private prayer request"
# The request stays out of the email: only the care team and Church Managers read a Private one.
PRIVATE_MESSAGE = """<p>{% if doc.urgent %}<strong>Urgent.</strong> {% endif %}A new private prayer request was added{% if church_name(doc) %} at {{ church_name(doc) | e }}{% endif %}.</p>

<p><a href="{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}">Open the request</a> to read it.</p>
"""


class PrayerRequest(Document):
	def before_insert(self):
		if not self.status:
			self.status = frappe.db.get_value("Prayer Request Status", {"status": "Requested"}, "name")
		# The web form saves with ignore_permissions, so Frappe keeps the permlevel 1 default for a guest.
		if frappe.session.user == "Guest":
			self.approved_for_list = 0

	def validate(self):
		self.validate_public_church()
		pin_to_members_own_person(self, "requestor")
		validate_members_recipient(self)
		# Resolve the display name for the dynamic recipient link using the linked
		# doctype's title_field (e.g. full_name for Person). Stored so it can be
		# shown in web form list views, which cannot resolve Dynamic Link titles.
		# See: https://github.com/frappe/frappe/issues/27330
		if self.recipient and self.recipient_type:
			meta = frappe.get_meta(self.recipient_type)
			title_field = meta.title_field or "name"
			self.recipient_name = (
				frappe.db.get_value(self.recipient_type, self.recipient, title_field) or self.recipient
			)
		else:
			self.recipient_name = None

	def validate_public_church(self):
		"""Keep a website request to a church the site actually offers.

		The anonymous web form carries the church of the page that took it, which
		is the only signal a guest gives; cleared here, `ensure_church` settles it.
		"""
		if frappe.session.user != "Guest" or not self.church:
			return
		if not frappe.db.get_value("Church", self.church, "publish"):
			self.church = None

	def has_webform_permission(self):
		"""Community Prayer Requests reads past the DocPerms: a member opens what that page lists them."""
		if frappe.session.user == "Guest":
			return False
		filters, or_filters = get_open_request_filters()
		filters = {"name": self.name, **get_community_filters(), **filters}
		return bool(frappe.get_all(PRAYER_REQUEST, filters=filters, or_filters=or_filters, limit=1))


def get_list_context(context):
	context.filters = {"owner": frappe.session.user}
	context.order_by = "modified desc"

	def get_list(doctype, txt, filters, limit_start, limit_page_length=20, **kwargs):
		from frappe.www.list import get_list as default_get_list

		rows = default_get_list(doctype, txt, filters, limit_start, limit_page_length, **kwargs)
		resolve_link_titles(rows, doctype)
		return rows

	context.get_list = get_list
	return context


def create_new_prayer_request_notifications() -> None:
	"""Insert the Notifications that tell the prayer team and the care team of a new request, once each.

	They are not standard, because production cannot enable a shipped one, and a church may change them.
	The prayer team hears only of a request approved for the list, so a guest's request waits for moderation.
	"""
	staff = [{"receiver_by_role": role} for role in PASTORAL_ROLES]
	notifications = (
		{
			"name": PRAYER_TEAM_NOTIFICATION,
			"subject": PRAYER_TEAM_SUBJECT,
			"condition": 'doc.visibility != "Private"',
			"recipients": [
				{"receiver_by_role": PRAYER_TEAM_ROLE, "condition": "doc.approved_for_list"},
				*staff,
			],
			"message": PRAYER_TEAM_MESSAGE,
		},
		{
			"name": PRIVATE_NOTIFICATION,
			"subject": PRIVATE_SUBJECT,
			"condition": 'doc.visibility == "Private"',
			"recipients": staff,
			"message": PRIVATE_MESSAGE,
		},
	)
	for notification in notifications:
		if frappe.db.exists("Notification", notification["name"]):
			continue
		frappe.get_doc(
			{
				"doctype": "Notification",
				"document_type": PRAYER_REQUEST,
				"event": "New",
				"condition_type": "Python",
				"channel": "Email",
				"enabled": 1,
				"is_standard": 0,
				"send_system_notification": 1,
				"message_type": "HTML",
				**notification,
			}
		).insert(ignore_permissions=True)
