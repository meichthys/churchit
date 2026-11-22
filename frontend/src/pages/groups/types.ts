export interface GroupRow {
	name: string;
	group_name: string;
	description: string;
	meets: string;
	leaders: string;
	is_leader: boolean;
	can_leave: boolean;
}

export interface JoinableGroup {
	name: string;
	group_name: string;
	description: string;
	requires_approval: boolean;
}

export interface MyGroups {
	groups: GroupRow[];
	joinable: JoinableGroup[];
	waiting: { name: string; group_name: string }[];
}

export interface Meeting {
	name: string;
	title: string;
	date: string;
	date_label: string;
	time: string | null;
	place: string | null;
}

export interface GroupFile {
	name: string;
	title: string;
	group: string;
	group_name: string;
	file_url: string;
	added_on: string;
}

/** One living member on the group page; email and phone only where shared and the viewer may see them. */
export interface GroupMember {
	name: string;
	full_name: string;
	photo: string | null;
	is_leader: boolean;
	email: string | null;
	phone: string | null;
}

export interface GroupDetail extends GroupRow {
	next_meeting: Meeting | null;
	later_meetings: Meeting[];
	files: GroupFile[];
	show_files: boolean;
	members: GroupMember[];
}

export interface GroupFiles {
	items: GroupFile[];
	groups: { value: string; label: string }[];
	can_add: boolean;
}

export interface RosterRow {
	name: string;
	full_name: string;
	group_role: string;
	email: string | null;
	phone: string | null;
}

export interface LedMeeting {
	name: string;
	title: string;
	date: string;
	time: string | null;
	did_not_meet: boolean;
	attendance_recorded_on: string | null;
	attendance: Record<string, string>;
}

export interface JoinRequest {
	name: string;
	person_name: string;
	message: string;
	requested_on: string;
}

export interface LedGroup {
	name: string;
	group_name: string;
	roster: RosterRow[];
	meetings: LedMeeting[];
	upcoming: { next_date: string | null; next_date_label: string | null; has_schedule: boolean } | null;
	join_requests: JoinRequest[];
}

export interface LeaderView {
	groups: LedGroup[];
	can_send_email: boolean;
	can_send_texts: boolean;
}

// Attendance types that count as present (church_ministries/attendance.py COUNTED_TYPES).
export const COUNTED_ATTENDANCE = ["Confirmed", "Assumed", "Checked-In"];
