import frappe
from frappe.query_builder.functions import Coalesce, Count
from pypika.terms import LiteralValue

from churchit.query import CurDate, TimestampDiff

AGE_BUCKETS = (
	("0-12 (Children)", 0, 12),
	("13-17 (Teens)", 13, 17),
	("18-29 (Young Adults)", 18, 29),
	("30-44 (Adults)", 30, 44),
	("45-64 (Middle Adults)", 45, 64),
	("65+ (Seniors)", 65, 150),
)


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


def _tally(label, counts_by_gender):
	row = {"bucket": label, "male": 0, "female": 0, "other": 0, "total": 0}
	for r in counts_by_gender:
		gender = (r["gender"] or "").lower()
		key = gender if gender in ("male", "female") else "other"
		row[key] = r["cnt"]
		row["total"] += r["cnt"]
	return row


def get_data():
	Person = frappe.qb.DocType("Person")
	LifeEvent = frappe.qb.DocType("Life Event")

	birth_event = (
		(LifeEvent.parent == Person.name)
		& (LifeEvent.parenttype == "Person")
		& (LifeEvent.event_type == "Birth")
	)
	age = TimestampDiff(LiteralValue("YEAR"), LifeEvent.date, CurDate())
	gender_counts = (Coalesce(Person.gender, "Other").as_("gender"), Count("*").as_("cnt"))

	rows = []
	for label, low, high in AGE_BUCKETS:
		counts = (
			frappe.qb.from_(Person)
			.join(LifeEvent)
			.on(birth_event)
			.select(*gender_counts)
			.where((Person.membership_status == "Active") & LifeEvent.date.isnotnull() & age[low:high])
			.groupby(Person.gender)
			.run(as_dict=True)
		)
		rows.append(_tally(label, counts))

	unknown = (
		frappe.qb.from_(Person)
		.left_join(LifeEvent)
		.on(birth_event)
		.select(*gender_counts)
		.where((Person.membership_status == "Active") & LifeEvent.date.isnull())
		.groupby(Person.gender)
		.run(as_dict=True)
	)
	if unknown:
		rows.append(_tally("Unknown Age", unknown))

	return rows
