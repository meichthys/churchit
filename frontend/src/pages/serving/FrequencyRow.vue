<template>
	<div class="py-4">
		<p class="text-lg text-ink-gray-9 md:text-md">{{ title }}</p>
		<div class="mt-2 flex items-center gap-3">
			<FormControl
				size="lg"
				v-model="times"
				type="number"
				min="0"
				step="1"
				class="w-24 [&_input:not([type=checkbox])]:min-h-11 [&_select]:min-h-11 [&_textarea]:text-lg [&_button]:min-h-11"
				:aria-label="__('Most times a month as {0}', [title])"
			/>
			<Button
				variant="outline"
				size="lg"
				class="min-h-11"
				:label="__('Save')"
				:loading="save.loading"
				@click="submit"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button, FormControl, toast } from "frappe-ui";
import { ref } from "vue";

import { useFrappeAction } from "@/api";
import { __ } from "@/translate";

const props = defineProps<{ position: string; title: string; value: number }>();
const emit = defineEmits<{ saved: [] }>();

const times = ref(String(props.value));
const save = useFrappeAction<void, { position: string; max_times_per_month: string }>(
	"churchit.church_ministries.member_ministry_team.set_own_frequency"
);

async function submit() {
	await save.submit({ position: props.position, max_times_per_month: times.value || "0" }).then(
		() => {
			toast.success(__("Saved"));
			emit("saved");
		},
		() => {}
	);
}
</script>
