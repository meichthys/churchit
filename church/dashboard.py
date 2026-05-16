import frappe


def extend_bootinfo(bootinfo):
	bootinfo.user_person = (
		frappe.db.get_value("Person", {"user": frappe.session.user}, "name") or ""
	)


def _church_modules() -> list[str]:
	return frappe.get_all("Module Def", filters={"app_name": "church"}, pluck="name")


def _church_doctypes() -> list[str]:
	return frappe.get_all(
		"DocType",
		filters={
			"module": ["in", _church_modules()],
			"istable": 0,
			"issingle": 0,
			"is_virtual": 0,
		},
		pluck="name",
	)


@frappe.whitelist()
def count_docs_created_by_me():
	user = frappe.session.user
	total = 0
	for dt in _church_doctypes():
		try:
			total += frappe.db.count(dt, {"owner": user})
		except Exception:
			continue
	return {"value": total, "fieldtype": "Int"}


@frappe.whitelist()
def count_docs_updated_by_me():
	# modified_by = user AND owner != user — counts edits to docs the user did
	# not author, so creations aren't double-counted as updates.
	user = frappe.session.user
	total = 0
	for dt in _church_doctypes():
		try:
			total += frappe.db.count(dt, {"modified_by": user, "owner": ["!=", user]})
		except Exception:
			continue
	return {"value": total, "fieldtype": "Int"}


@frappe.whitelist()
def count_weekly_attendance():
	last_week = frappe.utils.add_days(frappe.utils.nowdate(), -7)
	count = frappe.db.sql(
		"""
		SELECT COUNT(fa.name)
		FROM `tabFunction Attendance` fa
		INNER JOIN `tabFunction` f ON fa.parent = f.name
		WHERE f.start_date >= %s
		""",
		(last_week,),
	)[0][0]
	return {"value": count or 0, "fieldtype": "Int"}


@frappe.whitelist()
def count_tasks_assigned_to_me():
	user = frappe.session.user
	person_names = frappe.get_all("Person", filters={"user": user}, pluck="name")
	if not person_names:
		return {"value": 0, "fieldtype": "Int"}
	total = frappe.db.count("Church Task", {"assigned_person": ["in", person_names]})
	return {"value": total, "fieldtype": "Int"}
