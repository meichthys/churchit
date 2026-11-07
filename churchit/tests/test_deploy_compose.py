# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The compose file starts the Flow server only when asked and shares its socket with every container."""

import os
from pathlib import Path

import frappe
import yaml
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_bench_path

from churchit.ai.switch import has_flow

COMPOSE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "deploy", "docker-compose.yml")
FLOW_SERVICES = {"flow-configurator", "flow-server"}
SOCKET_VOLUME = "flow-server"
FRAPPE_USER = {"uid=1000", "gid=1000"}
IMAGE_BENCH = "/home/frappe/frappe-bench"
# Where Flow keeps its socket and its pid file (frappe/flow/daemon/lifecycle.py), by dotted path.
FLOW_RUNTIME_DIR = "frappe.flow.daemon.lifecycle.runtime_dir"
FLOW_PID_FILE = "frappe.flow.daemon.lifecycle.pid_file"


class TestComposeFlowServer(FrappeTestCase):
	"""A Frappe 16 image has no Flow, so a stack that did not ask for the flow profile must not start it.

	Compose cannot start a service of an inactive profile, so a default service that waits for one
	makes the whole stack invalid.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		with open(COMPOSE_PATH, encoding="utf-8") as file:
			cls.compose = yaml.safe_load(file)
		cls.services = cls.compose["services"]

	def test_only_the_flow_services_belong_to_the_flow_profile(self):
		profiled = {name for name, service in self.services.items() if "profiles" in service}

		self.assertEqual(profiled, FLOW_SERVICES)
		for name in FLOW_SERVICES:
			self.assertEqual(self.services[name]["profiles"], ["flow"], name)

	def test_no_default_service_waits_for_a_flow_service(self):
		waiting = [
			name
			for name, service in self.services.items()
			if name not in FLOW_SERVICES and FLOW_SERVICES & set(service.get("depends_on", {}))
		]

		self.assertEqual(
			waiting, [], "These services need a Flow service, which a default stack does not start"
		)

	def test_every_container_of_the_image_mounts_the_socket_volume(self):
		image = self.compose["x-backend"]["image"]
		missing = [
			name
			for name, service in self.services.items()
			if service.get("image") == image
			and not any(volume.startswith(f"{SOCKET_VOLUME}:") for volume in service.get("volumes", []))
		]

		self.assertEqual(missing, [], "Flow's install and its chats need the socket in these containers")

	def test_the_socket_volume_belongs_to_the_frappe_user(self):
		"""A plain volume at the socket's path belongs to root, and the daemon cannot write there."""
		options = (self.compose["volumes"][SOCKET_VOLUME] or {}).get("driver_opts", {})

		self.assertEqual(options.get("type"), "tmpfs")
		self.assertLessEqual(FRAPPE_USER, set(options.get("o", "").split(",")))

	def test_the_volume_and_the_command_follow_flows_own_paths(self):
		"""The image has no ps, which Flow's check of a stale pid file needs, so the command removes the
		file. A Flow update that moves the file or the socket's folder must fail here first."""
		if not has_flow():
			self.skipTest("This Frappe has no Flow.")
		bench = Path(get_bench_path())
		runtime_dir = frappe.call(FLOW_RUNTIME_DIR).relative_to(bench)
		pid_file = frappe.call(FLOW_PID_FILE).relative_to(bench)

		self.assertIn(f"{SOCKET_VOLUME}:{IMAGE_BENCH}/{runtime_dir}", self.compose["x-backend"]["volumes"])
		self.assertIn(f"rm -f {pid_file} &&", " ".join(self.services["flow-server"]["command"]))
