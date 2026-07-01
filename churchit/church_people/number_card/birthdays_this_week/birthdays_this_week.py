import frappe


@frappe.whitelist()
def get_count():
	return frappe.db.sql(
		"""
		SELECT COUNT(*)
		FROM `tabPerson` p
		JOIN `tabLife Event` le
			ON le.parent = p.name
			AND le.parenttype = 'Person'
			AND le.event_type = 'Birth'
		WHERE le.date IS NOT NULL
			AND WEEK(le.date, 1) = WEEK(CURDATE(), 1)
			AND MONTH(le.date) = MONTH(CURDATE())
		"""
	)[0][0]
