<template>
	<FormSheet
		v-model:open="open"
		:title="__('Attendance')"
		:description="meeting ? `${meeting.title}, ${formatShortDate(meeting.date)}` : undefined"
	>
		<template v-if="meeting">
			<Checkbox
				:model-value="didNotMeet"
				@update:model-value="didNotMeet = Boolean($event)"
				:label="__('The group did not meet')"
				size="md"
				padded
				class="!h-auto min-h-14 w-full [&_[data-slot=label]]:text-lg"
			/>
			<template v-if="!didNotMeet">
				<p class="rubric mb-2 mt-3 text-lg">
					{{ __("Tick everyone who came. The rest are marked absent.") }}
				</p>
				<ul class="divide-y divide-outline-gray-1 border-y border-outline-gray-1">
					<li v-for="person in roster" :key="person.name">
						<Checkbox
							:model-value="here.has(person.name)"
							:label="person.full_name"
							class="!h-auto min-h-14 w-full [&_[data-slot=label]]:text-lg"
							size="md"
							padded
							@update:model-value="toggle(person.name, Boolean($event))"
						/>
					</li>
				</ul>
			</template>
		</template>
		<template #actions>
			<Button
				variant="solid"
				size="lg"
				:label="__('Save attendance')"
				:loading="save.loading"
				@click="submit"
			/>
			<Button variant="subtle" size="lg" :label="__('Cancel')" @click="open = false" />
		</template>
	</FormSheet>
</template>

<script setup lang="ts">
import { Button, Checkbox, toast } from "frappe-ui";
import { reactive, ref, watch } from "vue";

import { useFrappeAction } from "@/api";
import FormSheet from "@/components/FormSheet.vue";
import { formatShortDate } from "@/format";
import { __ } from "@/translate";

import { COUNTED_ATTENDANCE, type LedMeeting, type RosterRow } from "./types";

const props = defineProps<{ meeting: LedMeeting | null; roster: RosterRow[] }>();
const emit = defineEmits<{ saved: [] }>();
const open = defineModel<boolean>("open", { default: false });

const didNotMeet = ref(false);
const here = reactive(new Set<string>());
const save = useFrappeAction<unknown, Record<string, unknown>>(
	"churchit.church_people.group_meetings.record_group_attendance"
);

watch(open, (isOpen) => {
	if (!isOpen || !props.meeting) return;

	didNotMeet.value = props.meeting.did_not_meet;
	here.clear();
	for (const person of props.roster) {
		const type = props.meeting.attendance[person.name];
		if (type && COUNTED_ATTENDANCE.includes(type)) here.add(person.name);
	}
});

function toggle(person: string, checked: boolean) {
	if (checked) here.add(person);
	else here.delete(person);
}

async function submit() {
	if (!props.meeting) return;

	const present = didNotMeet.value
		? []
		: props.roster.filter((person) => here.has(person.name)).map((person) => person.name);
	const absent = didNotMeet.value
		? []
		: props.roster.filter((person) => !here.has(person.name)).map((person) => person.name);
	const done = await save
		.submit({
			function: props.meeting.name,
			present,
			absent,
			did_not_meet: didNotMeet.value ? 1 : 0,
		})
		.then(
			() => true,
			() => false
		);
	if (!done) return;

	toast.success(__("Attendance saved."));
	open.value = false;
	emit("saved");
}
</script>
