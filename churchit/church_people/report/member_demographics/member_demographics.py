import frappe


def execute(filters=None):
	return get_columns(), get_data()


def get_columns():
	return [
		{"fieldname": "bucket", "fieldtype": "Data", "label": "Bucket", "width": 200},
		{"fieldname": "male", "fieldtype": "Int", "label": "Male", "width": 100},
		{"fieldname": "female", "fieldtype": "Int", "label": "Female", "width": 100},
		{"fieldname": "other", "fieldtype": "Int", "label": "Other/Unspecified", "width": 140},
		{"fieldname": "total", "fieldtype": "Int", "label": "Total", "width": 100},
	]


def get_data():
	rows = []
	buckets = [
		("0-12 (Children)", 0, 12),
		("13-17 (Teens)", 13, 17),
		("18-29 (Young Adults)", 18, 29),
		("30-44 (Adults)", 30, 44),
		("45-64 (Middle Adults)", 45, 64),
		("65+ (Seniors)", 65, 150),
	]
	for label, lo, hi in buckets:
		row = {"bucket": label, "male": 0, "female": 0, "other": 0, "total": 0}
		results = frappe.db.sql(
			"""
			SELECT COALESCE(p.gender, 'Other') AS gender, COUNT(*) AS cnt
			FROM `tabPerson` p
			JOIN `tabLife Event` le
				ON le.parent = p.name
				AND le.parenttype = 'Person'
				AND le.event_type = 'Birth'
			WHERE p.membership_status = 'Active'
				AND le.date IS NOT NULL
				AND TIMESTAMPDIFF(YEAR, le.date, CURDATE()) BETWEEN %s AND %s
			GROUP BY p.gender
			""",
			(lo, hi),
			as_dict=True,
		)
		for r in results:
			g = (r["gender"] or "").lower()
			if g == "male":
				row["male"] = r["cnt"]
			elif g == "female":
				row["female"] = r["cnt"]
			else:
				row["other"] = r["cnt"]
			row["total"] += r["cnt"]
		rows.append(row)

	unknown = frappe.db.sql(
		"""
		SELECT COALESCE(p.gender, 'Other') AS gender, COUNT(*) AS cnt
		FROM `tabPerson` p
		LEFT JOIN `tabLife Event` le
			ON le.parent = p.name
			AND le.parenttype = 'Person'
			AND le.event_type = 'Birth'
		WHERE p.membership_status = 'Active' AND le.date IS NULL
		GROUP BY p.gender
		""",
		as_dict=True,
	)
	if unknown:
		row = {"bucket": "Unknown Age", "male": 0, "female": 0, "other": 0, "total": 0}
		for r in unknown:
			g = (r["gender"] or "").lower()
			if g == "male":
				row["male"] = r["cnt"]
			elif g == "female":
				row["female"] = r["cnt"]
			else:
				row["other"] = r["cnt"]
			row["total"] += r["cnt"]
		rows.append(row)

	return rows
