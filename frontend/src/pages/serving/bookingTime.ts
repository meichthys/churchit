import { formatTime } from "@/format";
import { __ } from "@/translate";
import type { Booking } from "./types";

export function timeRange(item: Booking): string {
	const end = item.end_day_label
		? __("{0}, {1}", [item.end_day_label, formatTime(item.end_time)])
		: formatTime(item.end_time);
	return __("{0} to {1}", [formatTime(item.start_time), end]);
}
