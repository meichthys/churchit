import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "full_name", "fieldtype": "Data", "label": "Name", "width": 200},
		{"fieldname": "family_name", "fieldtype": "Data", "label": "Family", "width": 150},
		{"fieldname": "roles", "fieldtype": "Data", "label": "Roles", "width": 250},
		{"fieldname": "membership_status", "fieldtype": "Link", "label": "Member Status", "options": "Member Status", "width": 120},
		{"fieldname": "birthday", "fieldtype": "Date", "label": "Birthday", "width": 120},
		{"fieldname": "is_member", "fieldtype": "Check", "label": "Member", "width": 80},
		{"fieldname": "is_baptized", "fieldtype": "Check", "label": "Baptized", "width": 80},
	]


def get_data(filters=None):
	filters = filters or {}
	conditions = ""
	values = {}

	if filters.get("person_name"):
		conditions += " AND full_name LIKE %(person_name)s"
		values["person_name"] = f"%{filters['person_name']}%"

	if filters.get("is_member"):
		conditions += " AND is_member = 1"

	if filters.get("is_baptized"):
		conditions += " AND is_baptized = 1"

	if filters.get("family"):
		conditions += " AND family = %(family)s"
		values["family"] = filters["family"]

	if filters.get("role"):
		conditions += """ AND name IN (
			SELECT parent FROM `tabPosition`
			WHERE position = %(role)s
				AND (end_date IS NULL OR end_date >= CURDATE())
		)"""
		values["role"] = filters["role"]

	return frappe.db.sql(
		f"""
		SELECT
			`tabPerson`.name, full_name, is_member, membership_status,
			is_baptized, `tabPerson`.family, `tabFamily`.family_name, birthday,
			GROUP_CONCAT(DISTINCT `tabPosition Type`.position ORDER BY `tabPosition Type`.position SEPARATOR ', ') as roles
		FROM `tabPerson`
		LEFT JOIN `tabFamily` ON `tabFamily`.name = `tabPerson`.family
		LEFT JOIN `tabPosition` ON `tabPosition`.parent = `tabPerson`.name
			AND `tabPosition`.parenttype = 'Person'
			AND (`tabPosition`.end_date IS NULL OR `tabPosition`.end_date >= CURDATE())
		LEFT JOIN `tabPosition Type` ON `tabPosition Type`.name = `tabPosition`.position
		WHERE 1=1
			{conditions}
		GROUP BY `tabPerson`.name
		ORDER BY full_name
		""",
		values,
		as_dict=True,
	)
