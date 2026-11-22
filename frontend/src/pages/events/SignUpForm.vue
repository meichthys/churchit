<template>
	<form class="mt-8 max-w-[34rem]" @submit.prevent="send">
		<Checkbox
			v-model="attending"
			size="md"
			class="min-h-11 w-full items-start py-2 [&_input]:size-5"
		>
			<template #label
				><span class="text-lg text-ink-gray-9">{{ __("I am coming") }}</span></template
			>
		</Checkbox>

		<div v-if="items.length" class="mt-8">
			<SectionHead :title="__('What you can bring')" />
			<ul class="divide-y divide-outline-gray-1 border-t border-outline-gray-1">
				<li
					v-for="row in items"
					:key="row.item"
					class="flex items-center justify-between gap-4 py-4"
				>
					<div class="min-w-0">
						<p class="text-xl-medium text-ink-gray-9">{{ row.item }}</p>
						<p v-if="row.description" class="text-lg text-ink-gray-6 md:text-md">
							{{ row.description }}
						</p>
						<p class="text-lg text-ink-gray-6 md:text-md">{{ needed(row) }}</p>
					</div>
					<FormControl
						v-model="quantities[row.item]"
						type="number"
						size="lg"
						class="w-24 shrink-0 [&_input]:min-h-11 [&_input]:text-lg"
						:min="0"
						:max="maximum(row)"
						:aria-label="__('How many {0} you bring', [row.item])"
					/>
				</li>
			</ul>
		</div>

		<FormControl
			v-model="notes"
			type="textarea"
			size="lg"
			class="mt-8 [&_textarea]:text-lg"
			:label="__('Notes')"
			:description="
				__('Anything the organizers should know, such as allergies or a late arrival.')
			"
		/>

		<div class="mt-8 flex flex-col-reverse gap-2 md:flex-row md:justify-end [&>*]:min-h-11">
			<Button size="lg" :label="__('Cancel')" :route="cancelRoute" />
			<Button type="submit" variant="solid" size="lg" :label="submitLabel" :loading="busy" />
		</div>
	</form>
</template>

<script setup lang="ts">
import { Button, Checkbox, FormControl } from "frappe-ui";
import { reactive, ref } from "vue";

import SectionHead from "@/components/SectionHead.vue";
import { __ } from "@/translate";

import type { SignUpItem } from "./types";

const props = withDefaults(
	defineProps<{
		items: SignUpItem[];
		attending?: boolean;
		notes?: string;
		submitLabel: string;
		cancelRoute: string;
		busy?: boolean;
	}>(),
	{ attending: true, notes: "" }
);
const emit = defineEmits<{
	submit: [
		value: {
			attending: boolean;
			notes: string;
			items: { item: string; my_quantity: number }[];
		}
	];
}>();

const attending = ref(props.attending);
const notes = ref(props.notes);
const quantities = reactive<Record<string, number>>(
	Object.fromEntries(props.items.map((row) => [row.item, row.my_quantity]))
);

/** The server counts what others took, never this member's own saved quantity. */
function others(row: SignUpItem): number {
	return row.quantity_signed_up;
}

function maximum(row: SignUpItem): number | undefined {
	return row.is_limited ? Math.max(row.quantity_needed - others(row), 0) : undefined;
}

function needed(row: SignUpItem): string {
	if (!row.quantity_needed) return __("{0} signed up so far", [others(row)]);
	return __("{0} of {1} signed up so far", [others(row), row.quantity_needed]);
}

function send() {
	emit("submit", {
		attending: attending.value,
		notes: notes.value,
		items: props.items.map((row) => ({
			item: row.item,
			my_quantity: Number(quantities[row.item]) || 0,
		})),
	});
}
</script>
