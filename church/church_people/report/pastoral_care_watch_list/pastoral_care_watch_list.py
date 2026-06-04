import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 240},
		{"fieldname": "reason", "fieldtype": "Data", "label": "Reason", "width": 200},
		{"fieldname": "last_event_date", "fieldtype": "Date", "label": "Last Event", "width": 110},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": "Phone", "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": "Email", "width": 200},
	]


def get_data(filters=None):
	window_days = (filters or {}).get("window_days", 30)
	rows = []

	recent_visits = frappe.db.sql(
		"""
		SELECT v.person AS person, MAX(v.visit_date) AS last_event_date
		FROM `tabVisitation Log` v
		WHERE v.visit_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
			AND v.follow_up_needed = 1
		GROUP BY v.person
		""",
		(window_days,),
		as_dict=True,
	)
	for r in recent_visits:
		r["reason"] = "Visitation follow-up needed"
		rows.append(r)

	active_prayer_persons = frappe.db.sql(
		"""
		SELECT DISTINCT pr.requestor AS person, MAX(pr.creation) AS last_event_date
		FROM `tabPrayer Request` pr
		WHERE COALESCE(pr.status, '') NOT IN ('Answered', 'Archived', 'Closed')
			AND pr.urgent = 1
			AND pr.requestor IS NOT NULL
		GROUP BY pr.requestor
		""",
		as_dict=True,
	)
	for r in active_prayer_persons:
		r["reason"] = "Urgent prayer request open"
		rows.append(r)

	for row in rows:
		person = frappe.db.get_value("Person", row.get("person"), ["primary_phone", "email"], as_dict=True) or {}
		row["primary_phone"] = person.get("primary_phone")
		row["email"] = person.get("email")
	return rows
