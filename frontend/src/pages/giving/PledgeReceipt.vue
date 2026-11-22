<template>
	<!-- A pledge as a receipt: leader dots between each label and its amount. -->
	<article class="py-6" :class="fresh && 'is-fresh -mx-3 rounded-4 px-3'">
		<div class="flex flex-wrap items-baseline justify-between gap-x-4">
			<h3 class="t-subhead text-ink-gray-9">{{ pledge.campaign_title }}</h3>
			<p class="t-label text-ink-gray-6">{{ __(pledge.frequency) }}</p>
		</div>
		<dl class="mt-4 space-y-2 text-lg">
			<div v-for="line in lines" :key="line.label" class="flex items-baseline">
				<dt :class="line.strong ? 'font-medium text-ink-gray-9' : 'text-ink-gray-7'">
					{{ line.label }}
				</dt>
				<span class="leader" aria-hidden="true" />
				<dd :class="line.strong ? 'font-medium text-ink-gray-9' : 'text-ink-gray-8'">
					<bdi>{{ line.value }}</bdi>
				</dd>
			</div>
		</dl>
		<Progress class="mt-4" :value="pledge.percent" :label="__('Given so far')" hint />
		<p
			v-if="pledge.percent >= 100"
			class="mt-3 flex items-center gap-1.5 text-lg font-medium text-ink-green-8"
		>
			<span class="lucide-check size-4" aria-hidden="true" />
			{{ __("Thank you.") }}
		</p>
		<Button
			v-if="pledge.can_edit"
			class="mt-4 min-h-11"
			variant="outline"
			size="lg"
			icon-left="lucide-pencil"
			:label="__('Change this pledge')"
			@click="$emit('edit')"
		/>
	</article>
</template>

<script setup lang="ts">
import { Button, Progress } from "frappe-ui";
import { computed } from "vue";

import { __ } from "@/translate";

import type { Pledge } from "./types";

const props = defineProps<{ pledge: Pledge; fresh?: boolean }>();
defineEmits<{ edit: [] }>();

const lines = computed(() => [
	{ label: __("Pledged"), value: props.pledge.pledged_display, strong: false },
	{ label: __("Given so far"), value: props.pledge.given_display, strong: false },
	{ label: __("Still to give"), value: props.pledge.remaining_display, strong: true },
]);
</script>
