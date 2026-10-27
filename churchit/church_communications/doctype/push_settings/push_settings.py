# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address
from py_vapid import Vapid
from py_vapid.utils import b64urlencode


class PushSettings(Document):
	def validate(self):
		if not self.enabled:
			return
		if not self.vapid_public_key:
			frappe.throw(_("Generate the keys before you enable notifications."))
		subject = self.vapid_subject or ""
		if not (subject.startswith("mailto:") and validate_email_address(subject.removeprefix("mailto:"))):
			frappe.throw(
				_(
					"Write the Contact Address as mailto: and an email address, such as mailto:office@example.org."
				)
			)


@frappe.whitelist(methods=["POST"])
def generate_keys() -> None:
	"""Make the VAPID key pair while the keys are blank.

	New keys would end every browser's subscription, so keys that exist are kept. The public key is
	stored as browsers take it (applicationServerKey): the uncompressed point, base64url.
	"""
	frappe.only_for("System Manager")
	settings = frappe.get_single("Push Settings")
	if settings.vapid_public_key:
		frappe.throw(_("Push Settings already has its keys."))

	vapid = Vapid()
	vapid.generate_keys()
	public_point = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
	settings.vapid_public_key = b64urlencode(public_point)
	settings.vapid_private_key = b64urlencode(
		vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
	)
	settings.save()
