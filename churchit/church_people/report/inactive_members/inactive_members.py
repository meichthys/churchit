import frappe

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 220},
		{"fieldname": "membership_date", "fieldtype": "Date", "label": "Member Since", "width": 120},
		{"fieldname": "last_attended", "fieldtype": "Date", "label": "Last Attended", "width": 120},
		{"fieldname": "days_absent", "fieldtype": "Int", "label": "Days Absent", "width": 100},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": "Phone", "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": "Email", "width": 200},
	]


def get_data(filters=None):
	threshold_days = (filters or {}).get("threshold_days", 60)
	return frappe.db.sql(
		"""
		SELECT
			p.name,
			p.primary_phone,
			p.email,
			(
				SELECT le.date
				FROM `tabLife Event` le
				WHERE le.parent = p.name
					AND le.event_type = 'Membership'
				ORDER BY le.date ASC
				LIMIT 1
			) AS membership_date,
			(
				SELECT MAX(f.start_date)
				FROM `tabFunction Attendance` fa
				JOIN `tabFunction` f ON f.name = fa.parent
				WHERE fa.person = p.name
					AND fa.attendance_type IN ('Confirmed', 'Checked-In', 'Assumed')
			) AS last_attended,
			DATEDIFF(
				CURDATE(),
				COALESCE(
					(
						SELECT MAX(f.start_date)
						FROM `tabFunction Attendance` fa
						JOIN `tabFunction` f ON f.name = fa.parent
						WHERE fa.person = p.name
							AND fa.attendance_type IN ('Confirmed', 'Checked-In', 'Assumed')
					),
					(
						SELECT le.date
						FROM `tabLife Event` le
						WHERE le.parent = p.name
							AND le.event_type = 'Membership'
						ORDER BY le.date ASC
						LIMIT 1
					)
				)
			) AS days_absent
		FROM `tabPerson` p
		WHERE p.membership_status = 'Active'
		HAVING days_absent > %s OR last_attended IS NULL
		ORDER BY days_absent DESC
		""",
		(threshold_days,),
		as_dict=True,
	)
