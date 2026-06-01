import frappe


@frappe.whitelist()
def get_count():
	return frappe.db.sql(
		"""
		SELECT COUNT(*)
		FROM `tabPerson`
		WHERE anniversary IS NOT NULL
			AND WEEK(anniversary, 1) = WEEK(CURDATE(), 1)
			AND MONTH(anniversary) = MONTH(CURDATE())
			AND is_head_of_household = 1
		"""
	)[0][0]
