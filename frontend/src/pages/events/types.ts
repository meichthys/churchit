export interface SignUpItem {
	item: string;
	description: string;
	quantity_needed: number;
	quantity_signed_up: number;
	my_quantity: number;
	is_limited: boolean;
}

export interface OpenFunction {
	name: string;
	function_name: string;
	start_date: string | null;
	date_display: string;
	date_long: string;
	start_time: string | null;
	all_day: boolean;
	description: string;
	closes: string;
	signs_up_in: "app" | "register";
	sign_up: string | null;
	items?: SignUpItem[];
}

export interface SignUpRow {
	name: string;
	function: string;
	function_name: string;
	status: string;
	attendee_names: string[];
	can_cancel: boolean;
	start_date: string | null;
	date_display: string;
	date_long: string;
}

export interface SignUpDetail extends SignUpRow {
	waits_for: "payment" | "approval" | "";
	hold_expires: string;
	attending: boolean;
	notes: string;
	attendees: { name: string; selection: string }[];
	items: SignUpItem[];
	amount_due: string;
	amount_paid: string;
	payment_status: string;
	can_edit: boolean;
	pay_url: string;
}

export interface AttendanceData {
	choices: string[];
	upcoming: {
		function: string;
		function_name: string;
		status: string;
		sign_up: string | null;
		start_date: string | null;
		date_display: string;
	}[];
	past: {
		function: string;
		function_name: string;
		attendance_type: string;
		is_changeable: boolean;
		start_date: string | null;
		date_display: string;
	}[];
}
