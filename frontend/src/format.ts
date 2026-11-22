import { boot } from "./boot";

/** Dates come from the server as "YYYY-MM-DD" (and times as "HH:mm:ss"). Read them as local dates. */
function toDate(value: string): Date {
	const [date, time = "00:00:00"] = value.split(" ");
	const [year, month, day] = date.split("-").map(Number);
	const [hour, minute, second] = time.split(":").map(Number);
	return new Date(year, month - 1, day, hour || 0, minute || 0, Math.floor(second || 0));
}

/** "Sunday, November 15, 2026": the long form the house style asks for in running text. */
export function formatLongDate(value: string): string {
	return toDate(value).toLocaleDateString(boot.lang, { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}

/** "November 15" or "Sunday, November 15": a date without its year. */
export function formatDayMonth(value: string, withWeekday = false): string {
	return toDate(value).toLocaleDateString(boot.lang, {
		month: "long",
		day: "numeric",
		...(withWeekday ? { weekday: "long" } : {}),
	});
}

/** The System Settings date format (such as mm-dd-yyyy), for tight spaces like list rows. */
export function formatShortDate(value: string): string {
	const date = toDate(value);
	const parts: Record<string, string> = {
		dd: String(date.getDate()).padStart(2, "0"),
		mm: String(date.getMonth() + 1).padStart(2, "0"),
		yyyy: String(date.getFullYear()),
	};
	return boot.date_format.replace(/dd|mm|yyyy/g, (token) => parts[token]);
}

/** "9:30 AM" (or "09:30" where the site uses a 24-hour clock), from "HH:mm:ss" or a datetime. */
export function formatTime(value: string): string {
	const date = value.includes("-") ? toDate(value) : toDate(`2000-01-01 ${value}`);
	const hour12 = !/^HH/.test(boot.time_format);
	return date.toLocaleTimeString(boot.lang, { hour: "numeric", minute: "2-digit", hour12 });
}

/** An amount in the church's giving currency. */
export function formatMoney(amount: number, currency = boot.currency): string {
	return new Intl.NumberFormat(boot.lang, { style: "currency", currency }).format(amount || 0);
}
