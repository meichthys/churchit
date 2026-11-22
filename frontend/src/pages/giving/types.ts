/** What churchit.portal.giving sends. */
export interface Pledge {
	name: string;
	campaign: string;
	campaign_title: string;
	amount: number;
	frequency: string;
	pledged_display: string;
	given_display: string;
	remaining_display: string;
	percent: number;
	can_edit: boolean;
	give_path: string | null;
}

export interface Pledges {
	items: Pledge[];
	campaigns: { name: string; title: string }[];
	/** campaign -> the member's pledge to it */
	existing: Record<string, string>;
	frequencies: string[];
}

export interface Statement {
	name: string;
	title: string;
	from_date: string;
	to_date: string;
	period_display: string;
	total_display: string;
}
