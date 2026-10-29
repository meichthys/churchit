# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _

from churchit.church_ministries import kiosk

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/check-in-kiosk"
		raise frappe.Redirect

	frappe.only_for(kiosk.KIOSK_ROLE, message=True)
	context.no_cache = 1
	context.title = _("Check In")
	context.church_name = frappe.db.get_value("Church", kiosk.get_church(), "church_name")
