# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

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
