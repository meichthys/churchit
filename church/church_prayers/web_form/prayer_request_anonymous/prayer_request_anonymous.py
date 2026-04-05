import frappe

from church.utils import setup_web_form_church_field


def get_context(context):
	setup_web_form_church_field(context)
