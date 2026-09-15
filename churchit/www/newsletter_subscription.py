# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _

from churchit.church_communications.newsletter import get_subscription_status

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/newsletter-subscription"
		raise frappe.Redirect

	context.no_cache = 1
	context.title = _("Newsletter Subscription")
	context.update(get_subscription_status())
