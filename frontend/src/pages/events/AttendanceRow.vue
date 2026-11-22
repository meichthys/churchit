<template>
	<IndexRow
		:title="row.function_name"
		:facts="row.start_date ? [] : [row.date_display]"
		:fresh="fresh"
	>
		<template v-if="row.start_date" #prefix><DateStack :date="row.start_date" /></template>
		<template #suffix>
			<FormControl
				v-if="row.is_changeable"
				type="select"
				size="lg"
				class="min-h-11 min-w-36 md:min-w-44"
				:model-value="row.attendance_type"
				:options="options"
				:disabled="change.loading"
				:aria-label="__('Your attendance at {0}', [row.function_name])"
				@update:model-value="save"
			/>
			<StatusBadge v-else :status="row.attendance_type" :label="label" :theme="theme" />
		</template>
	</IndexRow>
</template>

<script setup lang="ts">
import { FormControl, toast } from "frappe-ui";
import { computed } from "vue";

import { useFrappeAction } from "@/api";
import DateStack from "@/components/DateStack.vue";
import IndexRow from "@/components/IndexRow.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { __ } from "@/translate";

import type { AttendanceData } from "./types";

const props = defineProps<{
	row: AttendanceData["past"][number];
	choices: string[];
	fresh?: boolean;
}>();
const emit = defineEmits<{ changed: [] }>();

const change = useFrappeAction<unknown, { function: string; attendance_type: string }>(
	"churchit.church_ministries.member_attendance.change_own_attendance"
);

const CHOICE_LABELS: Record<string, string> = {
	Confirmed: __("I was there"),
	Absent: __("I was not there"),
};
const options = computed(() => [
	...(props.choices.includes(props.row.attendance_type)
		? []
		: [
				{
					label: __(props.row.attendance_type),
					value: props.row.attendance_type,
					disabled: true,
				},
		  ]),
	...props.choices.map((value) => ({ label: CHOICE_LABELS[value] || __(value), value })),
]);

const label = computed(() => {
	if (props.row.attendance_type === "Checked-In") return __("Checked in");
	return CHOICE_LABELS[props.row.attendance_type] || __(props.row.attendance_type);
});
const theme = computed(() =>
	["Checked-In", "Confirmed"].includes(props.row.attendance_type) ? "green" : undefined
);

async function save(value: string) {
	try {
		await change.submit({ function: props.row.function, attendance_type: value });
		toast.success(__("Saved."));
	} catch {
		// useFrappeAction already showed the error as a toast
	} finally {
		emit("changed");
	}
}
</script>
