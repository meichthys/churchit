# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.exceptions import ValidationError
from frappe.utils import (
	add_days,
	add_months,
	add_years,
	get_datetime,
	get_first_day_of_week,
	getdate,
	now,
	today,
)

from churchit.church_finances.doctype.collection.collection import ONLINE_PAYMENT_TYPE, add_single_donation
from churchit.church_finances.doctype.fund.fund import add_transaction, format_amount
from churchit.church_finances.doctype.online_donation import online_donation
from churchit.church_finances.report.fund_transactions_by_date import fund_transactions_by_date
from churchit.church_summary.metrics import record_week
from churchit.patches.v1_0 import (
	date_collection_ledger_rows,
	remove_donation_acknowledgment_notification,
	retitle_collections,
)
from churchit.tests.helpers import RollbackEachTest, ensure_root_church, make_function, make_person


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


class TestCollection(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.fund = (
			frappe.get_doc({"doctype": "Fund", "fund": "_Test Collection Fund"})
			.insert(ignore_permissions=True)
			.name
		)
		self.payment_type = _ensure("Payment Type", {"type": "Cash"}, {"type": "Cash"})

	def _make_collection(self, amount=200, expected_total=None, date=None):
		collection = frappe.get_doc(
			{
				"doctype": "Collection",
				"date": date or now(),
				"expected_total": amount if expected_total is None else expected_total,
			}
		)
		collection.append(
			"donations",
			{"payment_type": self.payment_type, "fund": self.fund, "amount": amount},
		)
		return collection.insert(ignore_permissions=True)

	def make_giver(self, first_name, email):
		person = make_person(first_name, "_Test Receipt")
		person.append("emails", {"email_address": email, "is_primary": 1})
		return person.save(ignore_permissions=True).name

	def submit_with_receipts(self, rows, switch=1, **values):
		"""Submit a collection of (person, amount) rows and return the emails it sent."""
		frappe.db.set_single_value("Giving Settings", "email_receipts", switch)
		collection = frappe.get_doc(
			{
				"doctype": "Collection",
				"date": "2030-04-07 09:00:00",
				"expected_total": sum(amount for _person, amount in rows),
				**values,
			}
		)
		for person, amount in rows:
			collection.append(
				"donations",
				{"payment_type": self.payment_type, "fund": self.fund, "person": person, "amount": amount},
			)
		collection.insert(ignore_permissions=True)
		with (
			patch("frappe.sendmail") as sendmail,
			patch("churchit.church_finances.doctype.collection.collection.can_send_email", return_value=True),
		):
			collection.submit()
		return sendmail.call_args_list

	def test_a_submit_emails_each_giver_one_receipt_with_their_total(self):
		anna = self.make_giver("_Test Anna", "_test_receipt_anna@example.com")
		ben = self.make_giver("_Test Ben", "_test_receipt_ben@example.com")

		calls = self.submit_with_receipts([(anna, 30), (ben, 20), (anna, 12.5), (None, 5)])

		sent = {call.kwargs["recipients"][0]: call.kwargs for call in calls}
		self.assertEqual(set(sent), {"_test_receipt_anna@example.com", "_test_receipt_ben@example.com"})
		self.assertEqual(len(calls), 2)
		self.assertIn(format_amount(42.5), sent["_test_receipt_anna@example.com"]["message"])
		self.assertIn("_Test Anna", sent["_test_receipt_anna@example.com"]["message"])
		self.assertIn("Sunday, April 7, 2030", sent["_test_receipt_ben@example.com"]["message"])

	def test_no_receipts_while_the_setting_is_off(self):
		anna = self.make_giver("_Test Anna", "_test_receipt_off@example.com")

		self.assertEqual(self.submit_with_receipts([(anna, 30)], switch=0), [])

	def test_the_form_gets_the_receipts_switch_to_draw_its_note(self):
		for switch in (0, 1):
			frappe.db.set_single_value("Giving Settings", "email_receipts", switch)
			collection = frappe.new_doc("Collection")
			collection.run_method("onload")

			self.assertEqual(bool(collection.get_onload("email_receipts")), bool(switch))

	def test_an_imported_batch_sends_no_receipts(self):
		anna = self.make_giver("_Test Anna", "_test_receipt_import@example.com")

		self.assertEqual(self.submit_with_receipts([(anna, 30)], import_batch="_Test Batch"), [])

	def test_an_online_gift_sends_no_second_receipt(self):
		_ensure("Payment Type", {"type": ONLINE_PAYMENT_TYPE}, {"type": ONLINE_PAYMENT_TYPE})
		anna = self.make_giver("_Test Anna", "_test_receipt_online@example.com")
		frappe.db.set_single_value("Giving Settings", "email_receipts", 1)

		with patch("frappe.sendmail") as sendmail:
			add_single_donation(ensure_root_church(), self.fund, 25, "online", person=anna)

		sendmail.assert_not_called()

	def test_totals_and_breakdowns_computed(self):
		collection = self._make_collection(amount=200)
		self.assertEqual(collection.total_amount, 200)
		self.assertEqual(collection.imbalance, 0)
		self.assertEqual({f.fund: f.total for f in collection.fund_totals}, {self.fund: 200})
		self.assertEqual(
			{p.payment_type: p.total for p in collection.payment_type_totals},
			{self.payment_type: 200},
		)

	def test_imbalance_computed_from_expected_total(self):
		collection = self._make_collection(amount=200, expected_total=250)
		self.assertEqual(collection.imbalance, -50)

	def test_imbalance_blocks_submit(self):
		collection = self._make_collection(amount=200, expected_total=250)
		with self.assertRaises(ValidationError):
			collection.submit()

	def test_the_imbalance_message_shows_the_amount_in_the_site_currency(self):
		collection = self._make_collection(amount=200, expected_total=1450)
		with self.assertRaises(ValidationError) as raised:
			collection.submit()
		self.assertIn(format_amount(-1250), str(raised.exception))

	def test_submit_and_cancel_alert_the_change_and_warn_only_of_a_negative_balance(self):
		collection = self._make_collection(amount=1500)
		frappe.local.message_log = []
		collection.submit()
		[alert] = frappe.get_message_log()
		self.assertTrue(alert["alert"])
		self.assertIn(f"fund increased by {format_amount(1500)}", alert["message"])
		self.assertNotIn("$", alert["message"].replace(format_amount(1500), ""))

		refund = self._make_collection(amount=-1600)
		frappe.local.message_log = []
		refund.submit()
		alert, warning = frappe.get_message_log()
		self.assertIn(f"fund decreased by {format_amount(1600)}", alert["message"])
		self.assertEqual(warning["indicator"], "orange")
		self.assertIn(format_amount(-100), warning["message"])

		frappe.local.message_log = []
		collection.cancel()
		alert, warning = frappe.get_message_log()
		self.assertIn(f"fund decreased by {format_amount(1500)}", alert["message"])
		self.assertIn(format_amount(-1600), warning["message"])

	def test_a_gift_into_a_fund_in_deficit_gives_no_warning(self):
		add_transaction(self.fund, -500, "Expense", "_TEST-DEFICIT", now())
		collection = self._make_collection(amount=100)
		frappe.local.message_log = []
		collection.submit()

		self.assertEqual([message.get("indicator") for message in frappe.get_message_log()], ["green"])

	def test_a_fund_whose_rows_net_to_zero_gets_no_message(self):
		collection = frappe.get_doc({"doctype": "Collection", "date": now(), "expected_total": 0})
		for amount in (0.1, 0.2, -0.3):
			collection.append(
				"donations", {"payment_type": self.payment_type, "fund": self.fund, "amount": amount}
			)
		collection.insert(ignore_permissions=True)
		frappe.local.message_log = []
		# The desk submits the stored rows, and their float sum is not exactly zero.
		frappe.get_doc("Collection", collection.name).submit()

		self.assertEqual(frappe.get_message_log(), [])

	def test_an_online_gift_shows_the_giver_no_fund_message(self):
		_ensure("Payment Type", {"type": ONLINE_PAYMENT_TYPE}, {"type": ONLINE_PAYMENT_TYPE})
		add_transaction(self.fund, -500, "Expense", "_TEST-DEFICIT", now())
		frappe.local.message_log = []
		frappe.msgprint("Thank you")
		frappe.set_user("Guest")

		add_single_donation(ensure_root_church(), self.fund, 40, "Online gift")

		self.assertEqual([message["message"] for message in frappe.get_message_log()], ["Thank you"])
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), -460)

	def test_submit_increases_fund_balance(self):
		self._make_collection(amount=200).submit()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), 200)

	def test_cancel_reverses_fund_balance(self):
		collection = self._make_collection(amount=200)
		collection.submit()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), 200)
		collection.cancel()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), 0)

	def ledger(self, **filters):
		rows = frappe.get_all(
			"Financial Transaction",
			{"parenttype": "Fund", **filters},
			["parent", "amount"],
			order_by="parent",
		)
		return [(row.parent, row.amount) for row in rows]

	def test_each_fund_gets_one_ledger_row_and_no_version(self):
		second = frappe.get_doc({"doctype": "Fund", "fund": "_Test Collection Second Fund"}).insert(
			ignore_permissions=True
		)
		funds = (self.fund, second.name)
		versions = {
			fund: frappe.db.count("Version", {"ref_doctype": "Fund", "docname": fund}) for fund in funds
		}
		self._make_collection(amount=7).submit()
		collection = frappe.get_doc({"doctype": "Collection", "date": now(), "expected_total": 180})
		for fund, amount in ((self.fund, 100), (second.name, 30), (self.fund, 50)):
			collection.append(
				"donations", {"payment_type": self.payment_type, "fund": fund, "amount": amount}
			)
		collection.insert(ignore_permissions=True).submit()

		self.assertEqual(self.ledger(source=collection.name), sorted([(self.fund, 150), (second.name, 30)]))
		for fund in funds:
			self.assertEqual(
				frappe.db.count("Version", {"ref_doctype": "Fund", "docname": fund}), versions[fund]
			)
			self.assertEqual(
				frappe.db.get_value("Fund", fund, "balance"),
				sum(amount for _fund, amount in self.ledger(parent=fund)),
			)

		collection.cancel()
		self.assertEqual(self.ledger(source=collection.name), [])
		self.assertEqual(self.ledger(parent=self.fund), [(self.fund, 7)])
		self.assertEqual([frappe.db.get_value("Fund", fund, "balance") for fund in funds], [7, 0])

	def ledger_dates(self, from_date, to_date):
		filters = {"from_date": from_date, "to_date": to_date}
		return [row.date for row in fund_transactions_by_date.execute(filters)[1] if row.amount == 321]

	def test_a_collection_entered_late_shows_in_its_own_month(self):
		last_month = add_months(getdate(), -1).replace(day=15)
		self._make_collection(amount=321, date=f"{last_month} 10:00:00").submit()

		self.assertEqual(self.ledger_dates(last_month, last_month), [get_datetime(f"{last_month} 10:00:00")])
		self.assertEqual(self.ledger_dates(getdate(), getdate()), [])

	def test_an_old_collection_queues_a_recount_of_its_week(self):
		old = add_days(get_first_day_of_week(today()), -10)
		with patch.object(frappe, "enqueue") as enqueue:
			collection = self._make_collection(date=f"{old} 10:00:00")
			collection.submit()
			collection.cancel()

		week_start = get_first_day_of_week(old)
		self.assertEqual(enqueue.call_count, 2)
		self.assertEqual(enqueue.call_args.args, (record_week,))
		self.assertEqual(
			enqueue.call_args.kwargs,
			{
				"week_start": week_start,
				"job_id": f"weekly_metrics_{week_start}",
				"deduplicate": True,
				"enqueue_after_commit": True,
			},
		)

	def test_a_collection_of_this_week_or_last_week_leaves_the_recount_to_the_daily_job(self):
		last_week = add_days(get_first_day_of_week(today()), -7)
		with patch.object(frappe, "enqueue") as enqueue:
			self._make_collection().submit()
			self._make_collection(date=f"{last_week} 10:00:00").submit()
		enqueue.assert_not_called()

	def save_as_a_person(self, collection, date):
		collection.flags.ignore_permissions = False
		collection.date = date
		frappe.local.message_log = []
		collection.save()
		return [message["message"] for message in frappe.get_message_log()]

	def test_a_date_far_from_today_warns_but_saves(self):
		collection = self._make_collection()
		long_ago = add_days(add_years(today(), -1), -1)

		[ahead] = self.save_as_a_person(collection, f"{add_days(today(), 31)} 10:00:00")
		[back] = self.save_as_a_person(collection, f"{long_ago} 10:00:00")

		self.assertIn("more than 30 days after today", ahead)
		self.assertIn("more than a year before today", back)
		self.assertEqual(
			getdate(frappe.db.get_value("Collection", collection.name, "date")), getdate(long_ago)
		)

	def test_a_near_date_an_unchanged_date_or_an_import_gives_no_date_warning(self):
		collection = self._make_collection(date=f"{add_days(today(), 31)} 10:00:00")
		self.assertEqual(self.save_as_a_person(collection, collection.date), [])
		self.assertEqual(self.save_as_a_person(collection, f"{add_days(today(), 30)} 10:00:00"), [])
		self.assertEqual(self.save_as_a_person(collection, f"{add_years(today(), -1)} 10:00:00"), [])
		with patch.dict(frappe.flags, in_import=True):
			self.assertEqual(self.save_as_a_person(collection, "2062-11-15 10:00:00"), [])

	def test_the_title_is_the_functions_name_and_the_long_date(self):
		collection = self._make_collection(date="2030-04-04 09:30:00")
		self.assertEqual(collection.title, "Collection, Thursday, April 4, 2030")

		collection.function = make_function("_Test Title Service").name
		collection.save(ignore_permissions=True)
		self.assertEqual(collection.title, "_Test Title Service, Thursday, April 4, 2030")

	def test_the_patch_retitles_each_collection_once_and_keeps_its_modified_time(self):
		collection = self._make_collection(date="2030-04-04 09:30:00")
		frappe.db.set_value(
			"Collection",
			collection.name,
			{"function": make_function("_Test Retitle Service").name, "title": "FUNC-0001 - 2030-04-04"},
			update_modified=False,
		)
		modified = frappe.db.get_value("Collection", collection.name, "modified")

		retitle_collections.execute()
		retitle_collections.execute()

		self.assertEqual(
			frappe.db.get_value("Collection", collection.name, ["title", "modified"]),
			("_Test Retitle Service, Thursday, April 4, 2030", modified),
		)

	def make_notification(self, name, is_standard):
		doc = frappe.get_doc(
			{
				"doctype": "Notification",
				"name": name,
				"subject": "Thanks",
				"document_type": "Collection",
				"event": "Submit",
				"channel": "Email",
				"message": "<p>Thanks</p>",
				"recipients": [{"receiver_by_document_field": "owner"}],
			}
		)
		doc.insert(ignore_permissions=True, set_name=name)
		frappe.db.set_value("Notification", name, "is_standard", is_standard)

	def test_the_patch_removes_the_standard_notification_and_keeps_a_churchs_own_copy(self):
		frappe.db.delete("Notification", {"name": "Donation Acknowledgment"})
		self.make_notification("Donation Acknowledgment", 1)
		self.make_notification("_Test Own Receipt", 0)

		with patch.dict(frappe.flags, in_patch=True):
			remove_donation_acknowledgment_notification.execute()
			remove_donation_acknowledgment_notification.execute()

		self.assertFalse(frappe.db.exists("Notification", "Donation Acknowledgment"))
		self.assertTrue(frappe.db.exists("Notification", "_Test Own Receipt"))

	def test_the_patch_leaves_a_church_s_own_notification_with_the_same_name(self):
		frappe.db.delete("Notification", {"name": "Donation Acknowledgment"})
		self.make_notification("Donation Acknowledgment", 0)

		remove_donation_acknowledgment_notification.execute()

		self.assertTrue(frappe.db.exists("Notification", "Donation Acknowledgment"))

	def test_the_patch_dates_old_ledger_rows_from_their_collection(self):
		collection = self._make_collection(amount=321, date="2030-04-04 09:30:00")
		collection.submit()
		row = frappe.db.get_value(
			"Financial Transaction", {"source_type": "Collection", "source": collection.name}, "name"
		)
		frappe.db.set_value("Financial Transaction", row, "date", now())

		date_collection_ledger_rows.execute()
		self.assertEqual(
			frappe.db.get_value("Financial Transaction", row, "date"), get_datetime("2030-04-04 09:30:00")
		)

		with patch.object(frappe.db, "set_value") as set_value:
			date_collection_ledger_rows.execute()
		set_value.assert_not_called()


class TestRefund(RollbackEachTest):
	"""A refund at the processor is recorded by cancelling the gift's Collection, or by a negative row."""

	def setUp(self):
		super().setUp()
		self.giver = make_person("_Test Refund", "Giver")
		self.fund = frappe.get_doc({"doctype": "Fund", "fund": "_Test Refund Fund"}).insert(
			ignore_permissions=True
		)
		self.payment_type = _ensure("Payment Type", {"type": "Cash"}, {"type": "Cash"})

	def make_collection(self, date, amount):
		"""A submitted Collection with one gift of *amount* from the giver."""
		collection = frappe.get_doc({"doctype": "Collection", "date": date, "expected_total": amount})
		collection.append(
			"donations",
			{
				"person": self.giver.name,
				"fund": self.fund.name,
				"payment_type": self.payment_type,
				"amount": amount,
			},
		)
		collection.insert(ignore_permissions=True).submit()
		return collection

	def gift(self, collection=None, status="Paid"):
		gift = frappe.get_doc(
			{
				"doctype": "Online Donation",
				"amount": 40,
				"fund": self.fund.name,
				"currency": "USD",
				"status": status,
			}
		).insert(ignore_permissions=True)
		# Only recording a gift sets its Collection, so the test sets it under the form.
		if collection:
			gift.db_set("collection", collection.name)
		return gift

	def status(self, gift):
		return frappe.db.get_value("Online Donation", gift.name, "status")

	def test_cancelling_a_gifts_collection_refunds_the_gift(self):
		collection = self.make_collection("2031-03-01", 40)
		gift, pending = self.gift(collection), self.gift(collection, status="Pending")

		collection.cancel()

		self.assertEqual((self.status(gift), self.status(pending)), ("Refunded", "Pending"))
		self.assertFalse(frappe.db.exists("Financial Transaction", {"source": collection.name}))

	def test_a_second_callback_on_a_refunded_gift_records_nothing(self):
		_ensure(
			"Payment Type",
			{"type": ONLINE_PAYMENT_TYPE},
			{"type": ONLINE_PAYMENT_TYPE},
		)
		gift = self.gift(status="Pending")
		with (
			patch.object(online_donation, "is_charge_confirmed", return_value=True),
			patch.object(online_donation.OnlineDonation, "send_acknowledgment"),
		):
			gift.on_payment_authorized("Completed")
			frappe.get_doc(
				"Collection", frappe.db.get_value("Online Donation", gift.name, "collection")
			).cancel()
			collections = frappe.db.count("Collection")

			frappe.get_doc("Online Donation", gift.name).on_payment_authorized("Completed")

		self.assertEqual(self.status(gift), "Refunded")
		self.assertEqual(frappe.db.count("Collection"), collections)
		self.assertFalse(frappe.db.exists("Financial Transaction", {"parent": self.fund.name}))
		self.assertEqual(frappe.db.get_value("Fund", self.fund.name, "balance"), 0)

	def amend(self, collection):
		amended = frappe.copy_doc(collection)
		amended.update({"amended_from": collection.name, "docstatus": 0})
		return amended.insert(ignore_permissions=True)

	def test_a_gifts_collection_cannot_be_amended(self):
		"""The cancel marked the gift Refunded, so the amended copy would put its money back with no gift."""
		collection = self.make_collection("2031-03-01", 40)
		gift = self.gift(collection)
		collection.cancel()

		with self.assertRaises(frappe.ValidationError):
			self.amend(collection)
		self.assertFalse(frappe.db.exists("Collection", {"amended_from": collection.name}))
		self.assertEqual(self.status(gift), "Refunded")

		other = self.make_collection("2031-03-02", 15)
		other.cancel()
		self.assertTrue(self.amend(other).name)

	def test_cancelling_a_collection_with_no_gift_changes_no_gift(self):
		gift = self.gift(self.make_collection("2031-03-01", 40))
		self.make_collection("2031-03-02", 15).cancel()
		self.assertEqual(self.status(gift), "Paid")

	def test_a_negative_row_next_year_lowers_only_next_years_statement(self):
		self.make_collection("2031-03-01", 100)
		self.make_collection("2032-02-01", 50)
		self.make_collection("2032-04-01", -20)

		totals = [
			frappe.get_doc(
				{"doctype": "Giving Statement", "person": self.giver.name, "from_date": start, "to_date": end}
			)
			.insert(ignore_permissions=True)
			.total_amount
			for start, end in (("2031-01-01", "2031-12-31"), ("2032-01-01", "2032-12-31"))
		]
		self.assertEqual(totals, [100, 30])
