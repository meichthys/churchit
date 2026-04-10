import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Church", "options": "Church", "width": 250},
		{"fieldname": "people", "fieldtype": "Int", "label": "People", "width": 100},
		{"fieldname": "families", "fieldtype": "Int", "label": "Families", "width": 100},
	]


def get_data():
	conditions = ""
	values = {}

	# Church Managers and Church Users can see all churches (scoping is on records, not churches)
	# System Manager also unrestricted

	return frappe.db.sql(
		f"""
		SELECT
			`tabChurch`.name,
			COUNT(DISTINCT cs_p.parent) as people,
			COUNT(DISTINCT cs_f.parent) as families
		FROM `tabChurch`
		LEFT JOIN `tabChurch Subscription` cs_p
			ON cs_p.church = `tabChurch`.name
			AND cs_p.parenttype = 'Person'
			AND cs_p.parentfield = 'church_subscriptions'
			AND cs_p.subscribed = 1
		LEFT JOIN `tabChurch Subscription` cs_f
			ON cs_f.church = `tabChurch`.name
			AND cs_f.parenttype = 'Family'
			AND cs_f.parentfield = 'church_subscriptions'
			AND cs_f.subscribed = 1
		WHERE 1=1
			{conditions}
		GROUP BY `tabChurch`.name
		ORDER BY `tabChurch`.name
		""",
		values,
		as_dict=True,
	)
