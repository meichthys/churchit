<template>
	<PageHead :crumbs="[{ label: __('Serving') }]">
		<template #actions>
			<Button
				variant="outline"
				:label="__('Add dates you cannot serve')"
				icon-left="lucide-calendar-x"
				@click="blocking = true"
			/>
		</template>
	</PageHead>
	<PageBody>
		<Masthead
			:title="__('Serving')"
			:label="boot.church?.title"
			:dateline="dateline"
		/>

		<LoadState :resource="serving" v-slot="{ data }">
			<div class="mt-8 lg:grid lg:grid-cols-12 lg:gap-x-10">
				<div class="lg:col-span-8">
					<section
						v-if="requests(data).length"
						class="mb-10 rounded-6 border border-outline-gray-3 p-5 md:p-6"
					>
						<SectionHead :title="__('Needs your answer')" />
						<ul class="divide-y divide-outline-gray-1">
							<li
								v-for="row in requests(data)"
								:key="row.name"
								class="py-5 first:pt-2"
								:class="
									isFresh(row.name) &&
									'is-fresh -mx-3 rounded-4 px-3'
								"
							>
								<p class="text-xl-medium text-ink-gray-9">
									{{ row.position }}
								</p>
								<Facts
									:facts="[
										row.function_name,
										row.date_label,
										row.start_time
											? formatTime(row.start_time)
											: null,
									]"
									class="mt-1 text-lg text-ink-gray-6 md:text-md"
								/>
								<p class="rubric mt-3 text-lg">
									{{ __("Can you serve?") }}
								</p>
								<div class="mt-2">
									<AssignmentActions
										:assignment="row"
										request
										@changed="changed"
									/>
								</div>
								<a
									v-if="row.meeting_url"
									:href="row.meeting_url"
									class="mt-1 block py-3 text-lg text-ink-gray-9 underline underline-offset-4 md:text-md"
								>
									{{ __("Join online") }}
								</a>
								<ScheduleDetails :assignment="row" />
							</li>
						</ul>
					</section>

					<section>
						<SectionHead :title="__('Where you serve')" />
						<EmptyState
							v-if="!schedule(data).length"
							:title="__('Nothing is asked of you yet')"
							:body="
								__(
									'When a team leader asks you to serve, the request shows here and in your email.',
								)
							"
						/>
						<template v-else>
							<DayBlock
								v-for="day in days(data)"
								:key="day.date"
								:date="day.date"
								:today="day.date === today"
								compact
							>
								<OrderEntry
									v-for="row in day.rows"
									:key="row.name"
									:title="row.position"
									:time="row.start_time"
									:facts="[
										row.function_name,
										row.replaced_by
											? __('Your place went to {0}.', [
													row.replaced_by,
												])
											: null,
										row.replaced_by
											? null
											: row.decline_reason,
									]"
									:status="row.status"
									:fresh="isFresh(row.name)"
								>
									<div class="space-y-1">
										<a
											v-if="row.meeting_url"
											:href="row.meeting_url"
											class="block py-3 text-lg text-ink-gray-9 underline underline-offset-4 md:text-md"
										>
											{{ __("Join online") }}
										</a>
										<AssignmentActions
											:assignment="row"
											@changed="changed"
										/>
										<ScheduleDetails :assignment="row" />
									</div>
								</OrderEntry>
							</DayBlock>
						</template>
					</section>
				</div>

				<aside
					class="mt-10 space-y-10 lg:col-span-4 lg:mt-0 lg:border-s lg:border-outline-gray-1 lg:ps-10"
				>
					<section>
						<SectionHead :title="__('Dates you cannot serve')" />
						<ul
							v-if="data.blocks.length"
							class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
						>
							<li
								v-for="block in data.blocks"
								:key="block.name"
								class="flex items-start gap-3 py-4"
							>
								<div class="min-w-0 flex-1 text-lg md:text-md">
									<p class="text-ink-gray-9">
										{{ blockRange(block) }}
									</p>
									<Facts
										:facts="[
											block.reason,
											block.repeat_frequency
												? block.repeat_until
													? __('{0} until {1}', [
															__(
																block.repeat_frequency,
															),
															block.repeat_until,
														])
													: __(block.repeat_frequency)
												: null,
											block.whole_household
												? __('Whole household')
												: null,
										]"
										class="text-ink-gray-6"
									/>
								</div>
								<Button
									variant="ghost"
									size="lg"
									class="min-h-11"
									:label="__('Remove')"
									:loading="removing === block.name"
									@click="removeBlock(block.name)"
								/>
							</li>
						</ul>
						<p v-else class="t-dateline text-ink-gray-6">
							{{ __("No dates blocked.") }}
						</p>
						<Button
							class="mt-3 min-h-11 w-full"
							variant="outline"
							size="lg"
							:label="__('Add dates')"
							icon-left="lucide-plus"
							@click="blocking = true"
						/>
					</section>

					<section v-if="data.positions.length">
						<SectionHead :title="__('How often you serve')" />
						<p class="text-lg text-ink-gray-6 md:text-md">
							{{
								__(
									"Choose the most times a month you serve in each position. 0 means no limit.",
								)
							}}
						</p>
						<div
							class="mt-2 divide-y divide-outline-gray-1 border-t border-outline-gray-1"
						>
							<FrequencyRow
								v-for="row in data.positions"
								:key="row.position"
								:position="row.position"
								:title="row.title"
								:value="row.max_times_per_month"
								@saved="serving.reload()"
							/>
						</div>
					</section>

					<section>
						<SectionHead :title="__('Your calendar')" />
						<CalendarLink
							:calendar="data.calendar"
							@changed="changed"
						/>
					</section>
				</aside>
			</div>
		</LoadState>
	</PageBody>

	<BlockSheet v-model:open="blocking" @saved="changed" />
</template>

<script setup lang="ts">
import { Button, toast } from "frappe-ui";
import { computed, ref } from "vue";

import { useFrappeAction, useRead } from "@/api";
import { boot } from "@/boot";
import DayBlock from "@/components/DayBlock.vue";
import EmptyState from "@/components/EmptyState.vue";
import Facts from "@/components/Facts.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import OrderEntry from "@/components/OrderEntry.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { formatDayMonth, formatTime } from "@/format";
import { useLiveRefresh } from "@/realtime";
import { __ } from "@/translate";
import AssignmentActions from "./AssignmentActions.vue";
import BlockSheet from "./BlockSheet.vue";
import CalendarLink from "./CalendarLink.vue";
import FrequencyRow from "./FrequencyRow.vue";
import ScheduleDetails from "./ScheduleDetails.vue";
import type { Assignment, Block, Serving } from "./types";

const OWN_ACTION_MS = 4000;

const serving = useRead<Serving>("serving.get_serving");
const { mark, isFresh } = useFreshInk();
const blocking = ref(false);
const removing = ref<string | null>(null);
let lastOwnAction = 0;

const today = new Date().toLocaleDateString("sv");

const requests = (data: Serving) =>
	data.assignments.filter((row) => row.needs_answer);
const schedule = (data: Serving) =>
	data.assignments.filter((row) => !row.needs_answer);

function days(data: Serving): { date: string; rows: Assignment[] }[] {
	const groups = new Map<string, Assignment[]>();
	for (const row of schedule(data))
		groups.set(row.start_date, [
			...(groups.get(row.start_date) || []),
			row,
		]);
	return [...groups].map(([date, rows]) => ({ date, rows }));
}

const dateline = computed(() => {
	const assignments = serving.data?.assignments;
	if (!assignments) return __("Where you are asked to serve");
	const waiting = assignments.find((row) => row.needs_answer);
	if (waiting)
		return __("{0} at {1} is waiting for your answer.", [
			waiting.position,
			waiting.function_name,
		]);
	const next = assignments.find((row) => row.status === "Accepted");
	if (next) return __("Next, {0} on {1}.", [next.position, next.date_label]);
	return __("Where you are asked to serve");
});

function blockRange(block: Block): string {
	if (block.from_date === block.to_date)
		return formatDayMonth(block.from_date, true);
	return __("{0} to {1}", [
		formatDayMonth(block.from_date),
		formatDayMonth(block.to_date),
	]);
}

function changed() {
	lastOwnAction = Date.now();
	serving.reload();
}

const remove = useFrappeAction<void, { block: string }>(
	"churchit.church_ministries.member_ministry_team.remove_own_block",
);

async function removeBlock(name: string) {
	removing.value = name;
	await remove.submit({ block: name }).then(changed, () => {});
	removing.value = null;
}

useLiveRefresh(["serving"], async (hint) => {
	const own = Date.now() - lastOwnAction < OWN_ACTION_MS;
	await serving.reload();
	if (!hint?.name || own) return;
	if (serving.data?.assignments.some((row) => row.name === hint.name))
		mark(hint.name);
	else toast.info(__("Your serving schedule changed."));
});
</script>
