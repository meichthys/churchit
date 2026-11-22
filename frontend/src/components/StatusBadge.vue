<template>
	<!-- How a record stands, always as a word. Labels are one step darker than frappe-ui's so they pass AA. -->
	<Badge :label="label || __(status)" :theme="theme" size="lg" :class="ink" />
</template>

<script setup lang="ts">
import { Badge } from "frappe-ui";
import { computed } from "vue";

type Theme = "gray" | "blue" | "green" | "amber" | "red";

/** The stored status values the app shows, by theme: green is done or yes, amber waits for someone,
 * red is no or stopped, gray is neutral. A status not listed is gray. */
const THEMES: Record<string, Theme> = {
	Confirmed: "green",
	Accepted: "green",
	Approved: "green",
	Completed: "green",
	Present: "green",
	Paid: "green",
	Answered: "green",
	Distributed: "green",
	Memorized: "green",
	Pending: "amber",
	Waitlisted: "amber",
	Requested: "amber",
	Conflict: "amber",
	Unpaid: "amber",
	"Partly Paid": "amber",
	Open: "blue",
	New: "blue",
	"In Progress": "blue",
	Cancelled: "red",
	Denied: "red",
	Declined: "red",
	Rejected: "red",
	Absent: "red",
	Expired: "red",
};

const INK: Record<Theme, string> = {
	gray: "!text-ink-gray-7",
	blue: "!text-ink-blue-8",
	green: "!text-ink-green-8",
	amber: "!text-ink-amber-8",
	red: "!text-ink-red-8",
};

const props = defineProps<{ status: string; label?: string; theme?: Theme }>();
const theme = computed<Theme>(() => props.theme || THEMES[props.status] || "gray");
const ink = computed(() => INK[theme.value]);
</script>
