export interface ScheduleItem {
	time: string | null;
	title: string | null;
	detail: string | null;
	is_header: boolean;
	key: string | null;
	arrangement: string | null;
	notes: string | null;
	media: { label: string; url: string }[];
}

export interface Assignment {
	name: string;
	status: string;
	decline_reason: string | null;
	function: string;
	function_name: string;
	position: string;
	start_date: string;
	end_date: string | null;
	date_label: string;
	start_time: string | null;
	meeting_url: string | null;
	replaced_by: string | null;
	pending_replacement: string | null;
	needs_answer: boolean;
	can_accept: boolean;
	can_decline: boolean;
	can_pass_on: boolean;
	schedule: ScheduleItem[];
	need_notes: { position: string; notes: string }[];
}

export interface Block {
	name: string;
	from_date: string;
	to_date: string;
	reason: string | null;
	whole_household: boolean;
	repeat_frequency: string | null;
	repeat_until: string | null;
}

export interface Serving {
	assignments: Assignment[];
	blocks: Block[];
	positions: { position: string; title: string; max_times_per_month: number }[];
	calendar: { url: string; webcal: string } | null;
}

export interface Booking {
	name: string;
	room: string;
	room_name: string | null;
	purpose: string;
	notes: string | null;
	status: string;
	start_datetime: string;
	end_datetime: string;
	date_label: string;
	start_time: string;
	end_time: string;
	ends_same_day: boolean;
	end_day_label: string | null;
	can_edit: boolean;
}
