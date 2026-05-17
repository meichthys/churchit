import frappe


def _church_modules() -> set[str]:
	cached = frappe.cache.get_value("church_modules_set")
	if cached is not None:
		return set(cached)
	modules = frappe.get_all("Module Def", filters={"app_name": "church"}, pluck="name")
	frappe.cache.set_value("church_modules_set", modules, expires_in_sec=300)
	return set(modules)


def log_creation_as_version(doc, method=None):
	# Mirror Frappe's update-tracking for creations so "My Recent Activity"
	# surfaces brand-new church docs (Frappe's built-in Version logger only
	# fires when there's a previous state — i.e. on update, not on insert).
	if doc.doctype == "Version":
		return
	if getattr(doc.meta, "module", None) not in _church_modules():
		return
	frappe.get_doc(
		{
			"doctype": "Version",
			"ref_doctype": doc.doctype,
			"docname": doc.name,
			"data": frappe.as_json({"created_by": doc.owner}, indent=None),
		}
	).insert(ignore_permissions=True)


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
	return {
		"value": count or 0,
		"fieldtype": "Int",
		"route": ["List", "Function"],
		"route_options": {"start_date": [">=", last_week]},
	}


@frappe.whitelist()
def count_tasks_assigned_to_me():
	user = frappe.session.user
	person_names = frappe.get_all("Person", filters={"user": user}, pluck="name")
	if not person_names:
		return {"value": 0, "fieldtype": "Int"}
	total = frappe.db.count("Church Task", {"assigned_person": ["in", person_names]})
	return {
		"value": total,
		"fieldtype": "Int",
		"route": ["List", "Church Task"],
		"route_options": {"assigned_person": ["in", person_names]},
	}
