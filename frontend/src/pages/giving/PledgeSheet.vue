<template>
	<FormSheet
		v-model:open="open"
		:title="editing ? __('Change your pledge') : __('Make a pledge')"
		:description="
			__(
				'A pledge is what you plan to give. You can give through the church as you always do.',
			)
		"
	>
		<div class="space-y-4">
			<FormControl
				v-model="form.campaign"
				size="lg"
				type="select"
				:label="__('Campaign')"
				:options="campaignOptions"
				:disabled="Boolean(editing)"
			/>
			<p v-if="existingPledge" class="text-lg text-ink-gray-7">
				{{ __("You already pledged to this campaign.") }}
				<Button
					v-if="canChangeExisting"
					variant="ghost"
					size="lg"
					class="min-h-11"
					:label="__('Change that pledge')"
					@click="$emit('edit', existingPledge)"
				/>
				<template v-else>{{
					__(
						"Only the church office can change it. You can still make another pledge.",
					)
				}}</template>
			</p>
			<FormControl
				v-model="form.amount"
				size="lg"
				type="number"
				:label="__('Amount')"
				:placeholder="__('Amount')"
				min="1"
				step="any"
			/>
			<FormControl
				v-model="form.frequency"
				size="lg"
				type="select"
				:label="__('How often')"
				:options="frequencyOptions"
			/>
		</div>
		<template #actions>
			<Button
				variant="solid"
				size="lg"
				:label="editing ? __('Save') : __('Pledge')"
				:disabled="!canSave"
				:loading="save.loading"
				@click="submit"
			/>
			<Button
				variant="subtle"
				size="lg"
				:label="__('Cancel')"
				@click="open = false"
			/>
		</template>
	</FormSheet>
</template>

<script setup lang="ts">
import { Button, FormControl, toast } from "frappe-ui";
import { computed, reactive, watch } from "vue";

import { useAction } from "@/api";
import FormSheet from "@/components/FormSheet.vue";
import { __ } from "@/translate";

import type { Pledge, Pledges } from "./types";

const props = defineProps<{ pledges: Pledges; editing: Pledge | null }>();
const emit = defineEmits<{ saved: []; edit: [name: string] }>();
const open = defineModel<boolean>("open", { default: false });

const form = reactive({ campaign: "", amount: "", frequency: "One Time" });
const save = useAction<string, Record<string, unknown>>("giving.save_pledge");

const campaignOptions = computed(() => {
	const options = props.pledges.campaigns.map((campaign) => ({
		value: campaign.name,
		label: campaign.title,
	}));
	const current = props.editing;
	if (
		current &&
		!options.some((option) => option.value === current.campaign)
	) {
		options.push({
			value: current.campaign,
			label: current.campaign_title,
		});
	}
	return options;
});
const frequencyOptions = computed(() =>
	props.pledges.frequencies.map((value) => ({ value, label: __(value) })),
);
const existingPledge = computed(() =>
	props.editing ? null : props.pledges.existing[form.campaign] || null,
);
const canChangeExisting = computed(() =>
	props.pledges.items.some(
		(pledge) => pledge.name === existingPledge.value && pledge.can_edit,
	),
);
const canSave = computed(() =>
	Boolean(form.campaign && Number(form.amount) > 0),
);

watch(
	[open, () => props.editing],
	([isOpen]) => {
		if (!isOpen) return;
		const current = props.editing;
		Object.assign(form, {
			campaign:
				current?.campaign || props.pledges.campaigns[0]?.name || "",
			amount: current ? String(current.amount) : "",
			frequency: current?.frequency || "One Time",
		});
	},
	{ immediate: true },
);

async function submit() {
	const saved = await save
		.submit({
			campaign: form.campaign,
			amount: Number(form.amount),
			frequency: form.frequency,
			name: props.editing?.name,
		})
		.catch(() => null);
	if (saved === null) return;

	open.value = false;
	toast.success(__("Your pledge is saved."));
	emit("saved");
}
</script>
