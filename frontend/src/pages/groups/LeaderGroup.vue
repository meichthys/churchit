<template>
	<section class="mt-10" :aria-labelledby="`led-${group.name}`">
		<h2
			:id="`led-${group.name}`"
			class="t-head text-[1.75rem] text-ink-gray-9"
		>
			{{ group.group_name }}
		</h2>
		<div class="mt-3 border-t-2 border-ink-gray-9" />

		<div v-if="group.join_requests.length" class="mt-8">
			<SectionHead :level="3" :title="__('Asking to join')" />
			<ul
				class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
			>
				<li v-for="request in group.join_requests" :key="request.name">
					<RequestRow
						:request="request"
						:fresh="isFresh(request.name)"
						@decided="emit('changed')"
					/>
				</li>
			</ul>
		</div>

		<div class="mt-8">
			<SectionHead
				:level="3"
				:title="__('Meetings')"
				:note="__('The last eight weeks')"
			/>
			<ul
				v-if="group.meetings.length"
				class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
			>
				<li
					v-for="meeting in group.meetings"
					:key="meeting.name"
					class="flex flex-wrap items-center gap-x-5 gap-y-3 py-4"
					:class="{ 'is-fresh': isFresh(meeting.name) }"
				>
					<DateStack :date="meeting.date" />
					<div class="min-w-0 flex-1 basis-48">
						<p class="text-xl-medium text-ink-gray-9">
							{{ meeting.title }}
						</p>
						<p class="mt-1 text-lg text-ink-gray-6 md:text-md">
							{{ meetingState(meeting) }}
						</p>
					</div>
					<Button
						:variant="isRecorded(meeting) ? 'subtle' : 'solid'"
						size="lg"
						class="min-h-11"
						:label="
							isRecorded(meeting)
								? __('Change attendance')
								: __('Take attendance')
						"
						@click="take(meeting)"
					/>
				</li>
			</ul>
			<EmptyState
				v-else
				:title="__('No meetings yet')"
				:body="noMeetings"
			/>
		</div>

		<div class="mt-8">
			<SectionHead :level="3" :title="__('Message the group')" />
			<div class="border-t border-outline-gray-1 pt-4">
				<template v-if="canEmail || canText">
					<Button
						size="lg"
						class="min-h-11"
						icon-left="lucide-send"
						:label="__('Write a message')"
						@click="messaging = true"
					/>
				</template>
				<p v-else class="text-lg text-ink-gray-6 md:text-md">
					{{
						__(
							"This site cannot send email yet. Ask the church office.",
						)
					}}
				</p>
			</div>
		</div>

		<div class="mt-8">
			<SectionHead :level="3" :title="__('People')" />
			<ul
				class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
			>
				<li
					v-for="person in group.roster"
					:key="person.name"
					class="py-4"
				>
					<p class="text-xl-medium text-ink-gray-9">
						{{ person.full_name }}
					</p>
					<p class="mt-1 text-lg text-ink-gray-6 md:text-md">
						{{ person.group_role }}
					</p>
					<p
						v-if="person.email || person.phone"
						class="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-lg md:text-md"
					>
						<a
							v-if="person.email"
							:href="`mailto:${person.email}`"
							class="inline-flex min-h-11 items-center text-ink-gray-8 underline decoration-outline-gray-3 underline-offset-4 [overflow-wrap:anywhere]"
							>{{ person.email }}</a
						>
						<a
							v-if="person.phone"
							:href="`tel:${person.phone}`"
							class="inline-flex min-h-11 items-center text-ink-gray-8 underline decoration-outline-gray-3 underline-offset-4"
							><bdi>{{ person.phone }}</bdi></a
						>
					</p>
				</li>
			</ul>
		</div>

		<AttendanceSheet
			v-model:open="recording"
			:meeting="current"
			:roster="group.roster"
			@saved="emit('changed')"
		/>
		<MessageSheet
			v-model:open="messaging"
			:group="group.name"
			:can-email="canEmail"
			:can-text="canText"
		/>
	</section>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { computed, ref } from "vue";

import DateStack from "@/components/DateStack.vue";
import EmptyState from "@/components/EmptyState.vue";
import SectionHead from "@/components/SectionHead.vue";

import AttendanceSheet from "./AttendanceSheet.vue";
import MessageSheet from "./MessageSheet.vue";
import RequestRow from "./RequestRow.vue";
import { COUNTED_ATTENDANCE, type LedGroup, type LedMeeting } from "./types";
import { __ } from "@/translate";

const props = defineProps<{
	group: LedGroup;
	canEmail: boolean;
	canText: boolean;
	isFresh: (key: string) => boolean;
}>();
const emit = defineEmits<{ changed: [] }>();

const recording = ref(false);
const messaging = ref(false);
const current = ref<LedMeeting | null>(null);

const noMeetings = computed(() => {
	const upcoming = props.group.upcoming;
	if (upcoming?.next_date_label)
		return __(
			"The next meeting is on {0}. It appears here once it has happened.",
			[upcoming.next_date_label],
		);
	if (upcoming?.has_schedule)
		return __(
			"The group meets on a schedule. Each meeting appears here after its date.",
		);
	return __(
		"No meetings are scheduled for this group. Ask the church office to add them.",
	);
});

function isRecorded(meeting: LedMeeting): boolean {
	return meeting.did_not_meet || Boolean(meeting.attendance_recorded_on);
}

function meetingState(meeting: LedMeeting): string {
	if (meeting.did_not_meet) return __("The group did not meet");
	if (!isRecorded(meeting)) return __("Attendance not recorded yet");
	const here = Object.values(meeting.attendance).filter((type) =>
		COUNTED_ATTENDANCE.includes(type),
	).length;
	return __("Attendance recorded: {0} here", [here]);
}

function take(meeting: LedMeeting) {
	current.value = meeting;
	recording.value = true;
}
</script>
