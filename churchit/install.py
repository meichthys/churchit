# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import os
import re

import frappe

# Frappe locks a document by writing a file named after its signature — a
# 56-char sha224 hexdigest (see ``Document.get_signature``). Bench operation
# locks (``bench_migrate.lock``, ``install_app.lock``, ``bench_new_site.lock``…)
# use descriptive names, so this pattern matches only per-document locks and
# never an in-progress bench operation.
_DOCUMENT_LOCK_RE = re.compile(r"^[0-9a-f]{56}\.lock$")


def clear_stale_document_locks():
	"""Remove leftover per-document lock files before install/migrate.

	Several shipped fixtures (notably the ``Church%`` Role Profiles) queue a
	background action on import via ``Document.queue_action``, which first locks
	the document. On a bench with no running worker that job never executes, so
	the lock file lingers and the next ``bench migrate`` / ``bench reinstall``
	aborts with ``DocumentLockedError``. Clearing the stale document locks here
	lets those commands run out of the box. Bench operation locks are untouched.
	"""
	try:
		locks_dir = frappe.get_site_path("locks")
	except Exception:
		return

	if not os.path.isdir(locks_dir):
		return

	for filename in os.listdir(locks_dir):
		if _DOCUMENT_LOCK_RE.match(filename):
			try:
				os.remove(os.path.join(locks_dir, filename))
			except FileNotFoundError:
				pass
