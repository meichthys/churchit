/** What churchit.portal.home.get_home sends. */
export interface Entry {
	key: string;
	kind: "sign-up" | "serving" | "group";
	title: string;
	date: string;
	date_display: string;
	time: string | null;
	who?: string;
	status: string | null;
	route: string | null;
}

export interface Day {
	date: string;
	label: string;
	is_today: boolean;
	entries: Entry[];
}

export interface AnswerRequest {
	name: string;
	title: string;
	position: string;
	date: string;
	date_display: string;
	time: string | null;
}

export interface Home {
	person: string;
	check_in: {
		functions: { name: string; title: string; time: string | null }[];
		people: { name: string; display_name: string }[];
	} | null;
	needs_answer: AnswerRequest[];
	week: Day[];
	ahead: Entry[];
	notices: { name: string; title: string; date_display: string; announcements: string }[];
	bulletin: { name: string; title: string; date_display: string } | null;
	members_only_pages: { name: string; title: string; route: string }[];
	prayer_requests: { name: string; title: string | null; request: string | null; prayer_count: number }[];
}
