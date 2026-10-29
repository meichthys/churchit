# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe
import requests

from churchit.church_missions.doctype.missionary import missionary
from churchit.church_people import geocoding
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_address


def nominatim_answer(places):
	response = mock.Mock()
	response.json.return_value = places
	return response


class TestGeocoding(RollbackEachTest):
	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("People Settings", "look_up_addresses", 1)
		self.address = make_address("_Test Geocoding", pincode="62701")
		sleep = mock.patch("churchit.church_people.geocoding.time.sleep")
		sleep.start()
		self.addCleanup(sleep.stop)

	def coordinates(self):
		return frappe.db.get_value("Address", self.address.name, ["latitude", "longitude"])

	def test_a_moved_address_is_queued_once_after_the_commit(self):
		self.address.reload()
		self.address.city = "Shelbyville"
		with mock.patch.object(frappe, "in_test", False), mock.patch("frappe.enqueue") as enqueue:
			self.address.save(ignore_permissions=True)

		enqueue.assert_called_once()
		self.assertEqual(enqueue.call_args.kwargs["address"], self.address.name)
		self.assertEqual(enqueue.call_args.kwargs["job_id"], f"geocode::{self.address.name}")
		self.assertTrue(enqueue.call_args.kwargs["deduplicate"])
		self.assertTrue(enqueue.call_args.kwargs["enqueue_after_commit"])

	def test_a_change_that_does_not_move_the_address_queues_nothing(self):
		self.address.reload()
		self.address.phone = "555 010 0101"
		with mock.patch.object(frappe, "in_test", False), mock.patch("frappe.enqueue") as enqueue:
			self.address.save(ignore_permissions=True)

		enqueue.assert_not_called()

	def test_the_lookup_stores_the_first_place_found(self):
		with mock.patch(
			"requests.get", return_value=nominatim_answer([{"lat": "39.78", "lon": "-89.65"}])
		) as get:
			geocoding.geocode(self.address.name)

		self.assertEqual(self.coordinates(), (39.78, -89.65))
		self.assertEqual(get.call_args.args[0], f"{geocoding.NOMINATIM_URL}/search")
		self.assertEqual(get.call_args.kwargs["params"]["q"], "1 Main St, Springfield, 62701, United States")
		self.assertIn(frappe.utils.get_url(), get.call_args.kwargs["headers"]["User-Agent"])

	def test_a_failed_lookup_leaves_the_coordinates_blank_and_logs_nothing(self):
		errors = frappe.db.count("Error Log")
		for answer in ({"side_effect": requests.ConnectionError()}, {"return_value": nominatim_answer([])}):
			frappe.db.set_value("Address", self.address.name, {"latitude": 1, "longitude": 1})
			with mock.patch("requests.get", **answer):
				geocoding.geocode(self.address.name)
			self.assertEqual(self.coordinates(), (0, 0))
		self.assertEqual(frappe.db.count("Error Log"), errors)

	def test_geolocation_settings_may_name_its_own_nominatim_server(self):
		settings = frappe.get_single("Geolocation Settings")
		settings.update({"provider": "Nomatim", "base_url": "https://maps.example.com/"})
		settings.save(ignore_permissions=True)

		self.assertEqual(geocoding.get_search_base_url(), "https://maps.example.com")

	def test_the_addresses_without_coordinates_are_looked_up_a_batch_at_a_time(self):
		located = make_address("_Test Geocoding Located")
		frappe.db.set_value("Address", located.name, {"latitude": 1, "longitude": 1})
		with (
			mock.patch.object(geocoding, "BATCH", 1),
			mock.patch.object(geocoding, "geocode") as geocode,
			mock.patch.object(frappe.db, "commit"),
			mock.patch("frappe.enqueue") as enqueue,
		):
			geocoding.geocode_missing()

		self.assertEqual(geocode.call_count, 1)
		self.assertNotEqual(geocode.call_args.args[0], located.name)
		self.assertEqual(enqueue.call_args.kwargs["after"], geocode.call_args.args[0])

	def test_with_the_lookup_off_no_address_is_sent_or_queued(self):
		frappe.db.set_single_value("People Settings", "look_up_addresses", 0)
		frappe.db.set_value("Address", self.address.name, {"latitude": 39.8, "longitude": -89.6})
		self.address.reload()
		self.address.address_line1 = "_Test Moved Street"

		with (
			mock.patch.object(frappe, "in_test", False),
			mock.patch("frappe.enqueue") as enqueue,
			mock.patch("requests.get") as get,
		):
			self.address.save()
			geocoding.geocode(self.address.name)
			geocoding.geocode_missing()

		enqueue.assert_not_called()
		get.assert_not_called()
		self.assertEqual(self.coordinates(), (39.8, -89.6))

	def test_a_form_pin_takes_the_stored_coordinates_or_looks_them_up_once(self):
		answer = nominatim_answer([{"lat": "39.78", "lon": "-89.65"}])
		with mock.patch("requests.get", return_value=answer) as get:
			first = geocoding.get_address_coordinates(self.address.name)
			second = geocoding.get_address_coordinates(self.address.name)

		self.assertEqual((first, second), ((39.78, -89.65), (39.78, -89.65)))
		get.assert_called_once()

	def test_a_form_pin_sends_nothing_with_the_lookup_off(self):
		frappe.db.set_single_value("People Settings", "look_up_addresses", 0)
		with mock.patch("requests.get") as get:
			self.assertIsNone(geocoding.get_address_coordinates(self.address.name))

		get.assert_not_called()

	def test_a_form_pin_for_a_place_nominatim_cannot_find_is_zero(self):
		with mock.patch("requests.get", return_value=nominatim_answer([])):
			self.assertEqual(geocoding.get_address_coordinates(self.address.name), (0, 0))

	def test_a_form_pin_needs_read_on_the_address(self):
		frappe.set_user(ensure_user("_test_geocoding_member@example.com", "GeocodingMember"))
		try:
			with self.assertRaises(frappe.PermissionError):
				geocoding.get_address_coordinates(self.address.name)
		finally:
			frappe.set_user("Administrator")

	def test_the_missionary_country_pin_obeys_the_lookup_setting(self):
		with mock.patch.object(missionary, "get_coordinates", return_value=(39.8, -98.6)) as get_coordinates:
			self.assertEqual(missionary.get_country_coordinates("United States"), (39.8, -98.6))
			frappe.db.set_single_value("People Settings", "look_up_addresses", 0)
			self.assertEqual(missionary.get_country_coordinates("United States"), (0, 0))

		get_coordinates.assert_called_once_with("United States")

	def test_turning_the_lookup_on_queues_the_addresses_that_missed_out(self):
		settings = frappe.get_single("People Settings")
		settings.look_up_addresses = 0
		settings.save()
		settings.look_up_addresses = 1

		with mock.patch.object(geocoding, "queue_missing") as queue_missing:
			settings.save()

		queue_missing.assert_called_once_with()
