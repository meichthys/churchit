import frappe


def execute():
	"""Add the "Online" Payment Type used by the online giving (/give) page.

	Fresh installs get this from ``after_install._create_payment_types``; this
	patch backfills it for churches that installed before online giving existed.
	"""
	if not frappe.db.exists("Payment Type", "Online"):
		frappe.get_doc({"doctype": "Payment Type", "type": "Online"}).insert(
			ignore_permissions=True
		)
