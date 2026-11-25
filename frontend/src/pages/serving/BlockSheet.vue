<template>
	<FormSheet
		v-model:open="open"
		:title="__('Add dates you cannot serve')"
		:description="
			__(
				'Team leaders see these dates, and the schedule skips you when it fills places.',
			)
		"
	>
		<div
			class="space-y-4 [&_input:not([type=checkbox])]:min-h-11 [&_select]:min-h-11 [&_textarea]:text-lg [&_button]:min-h-11"
		>
			<FormControl
				size="lg"
				v-model="form.from_date"
				type="date"
				:placeholder="__('Choose a date')"
				:label="__('From')"
				required
			/>
			<FormControl
				size="lg"
				v-model="form.to_date"
				type="date"
				:placeholder="__('Choose a date')"
				:label="__('To')"
				required
			/>
			<FormControl
				size="lg"
				v-model="form.reason"
				type="text"
				maxlength="140"
				:label="__('Reason')"
			/>
			<FormControl
				size="lg"
				v-model="form.repeat_frequency"
				type="select"
				:label="__('Repeat')"
				:options="repeatOptions"
			/>
			<FormControl
				size="lg"
				v-if="form.repeat_frequency"
				v-model="form.repeat_until"
				type="date"
				:placeholder="__('Choose a date')"
				:label="__('Repeat until (optional)')"
			/>
			<div class="min-h-11 py-2">
				<FormControl
					v-model="form.whole_household"
					type="checkbox"
					:label="__('Whole household')"
				/>
			</div>
		</div>
		<template #actions>
			<Button
				variant="solid"
				size="lg"
				:label="__('Add')"
				:disabled="!form.from_date || !form.to_date"
				:loading="add.loading"
				@click="save"
			/>
			<Button
				variant="outline"
				size="lg"
				:label="__('Cancel')"
				@click="open = false"
			/>
		</template>
	</FormSheet>
</template>

<script setup lang="ts">
import { Button, FormControl } from "frappe-ui";
import { reactive, watch } from "vue";

import { useFrappeAction } from "@/api";
import FormSheet from "@/components/FormSheet.vue";
import { __ } from "@/translate";

const open = defineModel<boolean>("open", { default: false });
const emit = defineEmits<{ saved: [] }>();

const repeatOptions = [
	{ label: __("Does not repeat"), value: "" },
	{ label: __("Weekly"), value: "Weekly" },
	{ label: __("Every Other Week"), value: "Every Other Week" },
	{
		label: __("Monthly on the Same Weekday"),
		value: "Monthly on the Same Weekday",
	},
];

const empty = () => ({
	from_date: "",
	to_date: "",
	reason: "",
	repeat_frequency: "",
	repeat_until: "",
	whole_household: false,
});
const form = reactive(empty());
watch(open, (value) => value && Object.assign(form, empty()));

const add = useFrappeAction<void, Record<string, string | number>>(
	"churchit.church_ministries.member_ministry_team.add_own_block",
);

async function save() {
	await add
		.submit({
			from_date: form.from_date,
			to_date: form.to_date,
			reason: form.reason,
			whole_household: form.whole_household ? 1 : 0,
			repeat_frequency: form.repeat_frequency,
			repeat_until: form.repeat_frequency ? form.repeat_until : "",
		})
		.then(
			() => {
				open.value = false;
				emit("saved");
			},
			() => {},
		);
}
</script>
