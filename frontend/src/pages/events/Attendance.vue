<template>
	<PageHead
		:crumbs="[
			{
				label: __('Sign-Ups'),
				...(isPageHidden('function-sign-up')
					? {}
					: { route: '/function-sign-up' }),
			},
			{ label: __('Attendance') },
		]"
	/>
	<PageBody>
		<Masthead
			:title="__('Attendance')"
			:label="boot.church?.title"
			:dateline="
				__('Events you are signed up for and the ones you attended')
			"
		/>
		<SignUpTabs current="attended" />

		<LoadState :resource="attendance" v-slot="{ data }">
			<section class="mt-8">
				<SectionHead
					:title="__('Attended')"
					:note="
						data.choices.length
							? __('You can correct a row if it is wrong.')
							: undefined
					"
				/>
				<ul
					v-if="data.past.length"
					class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
				>
					<li v-for="row in shown(data.past)" :key="row.function">
						<AttendanceRow
							:row="row"
							:choices="data.choices"
							:fresh="isFresh(row.function)"
							@changed="attendance.reload()"
						/>
					</li>
				</ul>
				<EmptyState
					v-else
					:title="__('No attendance yet')"
					:body="
						__('Events you attend are listed here after the day.')
					"
				/>
				<div
					v-if="data.past.length > limit"
					class="mt-4 flex justify-center"
				>
					<Button
						size="lg"
						class="min-h-11"
						:label="__('Show earlier')"
						@click="limit += PAGE"
					/>
				</div>
			</section>
			<section class="mt-10">
				<SectionHead :title="__('Coming up')" />
				<ul
					v-if="data.upcoming.length"
					class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
				>
					<li v-for="row in data.upcoming" :key="row.function">
						<IndexRow
							:title="row.function_name"
							:status="row.status"
							:facts="row.start_date ? [] : [row.date_display]"
							:fresh="isFresh(row.function)"
							v-bind="
								row.sign_up && !isPageHidden('function-sign-up')
									? {
											route: `/function-sign-up/${row.sign_up}`,
										}
									: {}
							"
						>
							<template v-if="row.start_date" #prefix
								><DateStack :date="row.start_date"
							/></template>
						</IndexRow>
					</li>
				</ul>
				<EmptyState
					v-else
					:title="__('Nothing coming up')"
					:body="
						__(
							'Events you sign up for are listed here until the day they happen.',
						)
					"
				>
					<Button
						v-if="!isPageHidden('function-sign-up')"
						size="lg"
						class="min-h-11"
						:label="__('See what is open')"
						route="/function-sign-up/list?tab=open"
					/>
				</EmptyState>
			</section>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { ref } from "vue";

import { useRead } from "@/api";
import { boot, isPageHidden } from "@/boot";
import DateStack from "@/components/DateStack.vue";
import EmptyState from "@/components/EmptyState.vue";
import IndexRow from "@/components/IndexRow.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { __ } from "@/translate";

import AttendanceRow from "./AttendanceRow.vue";
import SignUpTabs from "./SignUpTabs.vue";
import type { AttendanceData } from "./types";
import { useLiveList } from "./useLiveList";

const PAGE = 15;
const limit = ref(PAGE);
const attendance = useRead<AttendanceData>("events.get_attendance");

const shown = (rows: AttendanceData["past"]) => rows.slice(0, limit.value);

const { isFresh } = useLiveList(
	"attendance",
	() => attendance.reload(),
	(name) =>
		Boolean(
			attendance.data?.upcoming.some((row) => row.function === name) ||
			attendance.data?.past
				.slice(0, limit.value)
				.some((row) => row.function === name),
		),
	() => __("Your attendance changed."),
);
</script>
