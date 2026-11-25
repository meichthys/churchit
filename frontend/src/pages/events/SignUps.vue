<template>
	<PageHead :crumbs="[{ label: __('Sign-Ups') }]" />
	<PageBody>
		<Masthead
			:title="__('Sign-Ups')"
			:label="boot.church?.title"
			:dateline="
				__('Events you signed up for and ones you can still join')
			"
		/>
		<SignUpTabs :current="tab" />

		<LoadState
			v-if="tab === 'upcoming'"
			:resource="signUps"
			v-slot="{ data }"
		>
			<section class="mt-8">
				<SectionHead :title="__('Your sign-ups')" />
				<ul
					v-if="current(data.items).length"
					class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
				>
					<li v-for="row in current(data.items)" :key="row.name">
						<IndexRow
							:title="row.function_name"
							:route="`/function-sign-up/${row.name}`"
							:facts="[row.attendee_names.join(', ')]"
							:status="row.status"
							:fresh="isFresh(row.name)"
						>
							<template v-if="row.start_date" #prefix
								><DateStack :date="row.start_date"
							/></template>
						</IndexRow>
					</li>
				</ul>
				<EmptyState
					v-else
					:title="__('No sign-ups yet')"
					:body="
						__(
							'When you sign up for an event, it is listed here with its status.',
						)
					"
				>
					<Button
						variant="solid"
						size="lg"
						class="min-h-11"
						:label="__('See what is open')"
						@click="openTab"
					/>
				</EmptyState>
			</section>

			<section v-if="earlier(data.items).length" class="mt-10">
				<SectionHead :title="__('Earlier and cancelled')" />
				<ul
					class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
				>
					<li v-for="row in earlier(data.items)" :key="row.name">
						<IndexRow
							:title="row.function_name"
							:route="`/function-sign-up/${row.name}`"
							:facts="[row.date_display]"
							:status="row.status"
							:fresh="isFresh(row.name)"
						/>
					</li>
				</ul>
			</section>
		</LoadState>

		<LoadState v-else :resource="open" v-slot="{ data }">
			<section class="mt-8">
				<SectionHead :title="__('Open for sign-up')" />
				<ul
					v-if="data.items.length"
					class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
				>
					<li v-for="row in data.items" :key="row.name">
						<IndexRow
							:title="row.function_name"
							v-bind="
								row.signs_up_in === 'app'
									? {
											route: `/function-sign-up/new?function=${encodeURIComponent(
												row.name,
											)}`,
										}
									: {
											href: `/register?function=${encodeURIComponent(
												row.name,
											)}`,
										}
							"
							:facts="openFacts(row)"
						>
							<template v-if="row.start_date" #prefix
								><DateStack :date="row.start_date"
							/></template>
						</IndexRow>
					</li>
				</ul>
				<EmptyState
					v-else
					:title="__('Nothing is open right now')"
					:body="
						__('When an event takes sign-ups, it is listed here.')
					"
				/>
			</section>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import { boot } from "@/boot";
import { useRead } from "@/api";
import DateStack from "@/components/DateStack.vue";
import EmptyState from "@/components/EmptyState.vue";
import IndexRow from "@/components/IndexRow.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { formatTime } from "@/format";
import { __ } from "@/translate";

import SignUpTabs from "./SignUpTabs.vue";
import type { OpenFunction, SignUpRow } from "./types";
import { useLiveList } from "./useLiveList";

const route = useRoute();
const router = useRouter();
const tab = computed(() => (route.query.tab === "open" ? "open" : "upcoming"));

const signUps = useRead<{ items: SignUpRow[] }>("events.get_sign_ups");
const open = useRead<{ items: OpenFunction[] }>("events.get_open_functions");

const today = new Date().toLocaleDateString("en-CA");

function isCurrent(row: SignUpRow): boolean {
	return (
		row.status !== "Cancelled" &&
		(!row.start_date || row.start_date >= today)
	);
}
const current = (items: SignUpRow[]) =>
	items
		.filter(isCurrent)
		.sort((a, b) => (a.start_date || "").localeCompare(b.start_date || ""));
const earlier = (items: SignUpRow[]) => items.filter((row) => !isCurrent(row));

function openFacts(row: OpenFunction): string[] {
	const facts = [
		row.all_day
			? __("All day")
			: row.start_time
				? formatTime(row.start_time)
				: "",
	];
	if (row.closes) facts.push(__("Sign-ups close {0}", [row.closes]));
	if (row.signs_up_in === "register")
		facts.push(__("Opens the sign-up page"));
	return facts;
}

function openTab() {
	router.push({ path: "/function-sign-up/list", query: { tab: "open" } });
}

const { isFresh } = useLiveList(
	"sign-ups",
	() => Promise.all([signUps.reload(), open.reload()]),
	(name) =>
		tab.value === "upcoming" &&
		Boolean(signUps.data?.items.some((row) => row.name === name)),
	() => __("Your sign-ups changed."),
);
</script>
