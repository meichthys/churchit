export interface PrayerRequest {
	name: string;
	title: string;
	type: string;
	status: string;
	urgent: 0 | 1;
	visibility: string;
	recipient_type?: string;
	recipient?: string;
	recipient_name: string | null;
	request: string | null;
	prayer_count: number;
	date: string;
	date_display: string;
	prayed_today?: boolean;
}

export interface PrayerComment {
	name: string;
	comment_by: string;
	content: string;
	date_display: string;
}

export interface PrayerForm {
	types: { name: string; description: string | null }[];
	visibilities: { name: string; description: string }[];
	recipient_doctypes: string[];
	me: { name: string; full_name: string };
}

export interface CareRequest {
	name: string;
	category: string;
	urgency: string;
	status: string;
	description: string;
	preferred_contact: string | null;
	date_display: string;
}

export interface CareForm {
	categories: { name: string; description: string | null }[];
	urgencies: string[];
	preferred_contacts: string[];
	default_urgency: string;
}

export interface AlmsRequest {
	name: string;
	recipient_name: string;
	recipient_type: string;
	recipient: string;
	amount: number | null;
	description: string;
	status: string;
	date_display: string;
	can_change: boolean;
}

export interface Recipient {
	name: string;
	label: string;
}

/** The Web Form of each request; Frappe's accept and delete save through it. */
export const WEB_FORMS = {
	prayer: "prayer-request",
	care: "care-request-form",
	alms: "alms-request",
} as const;

export interface AcceptParams {
	web_form: string;
	data: string;
}

export interface DeleteParams {
	web_form_name: string;
	docname: string;
}
