<template>
	<p
		v-if="request.prayed_today"
		class="flex min-h-11 items-center gap-2 text-p-lg text-ink-green-8 md:text-p-base"
	>
		<span class="lucide-check size-5" aria-hidden="true" />
		<span>{{ __("You prayed") }}</span>
		<span v-if="request.prayer_count" class="text-ink-gray-6">{{
			request.prayer_count === 1 ? __("1 prayer") : __("{0} prayers", [request.prayer_count])
		}}</span>
	</p>
	<div v-else class="flex flex-wrap items-center gap-x-4 gap-y-1">
		<Button
			class="min-h-11"
			size="lg"
			variant="subtle"
			icon-left="lucide-heart"
			:loading="pray.loading"
			:label="__('I prayed')"
			@click="prayNow"
		/>
		<span v-if="request.prayer_count" class="text-p-lg text-ink-gray-6 md:text-p-base">{{
			request.prayer_count === 1 ? __("1 prayer") : __("{0} prayers", [request.prayer_count])
		}}</span>
	</div>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";

import { useFrappeAction } from "@/api";

import type { PrayerRequest } from "./types";

const props = defineProps<{ request: PrayerRequest; note?: string }>();
const emit = defineEmits<{ prayed: [] }>();
const pray = useFrappeAction<unknown, { prayer_request: string; content: string | null }>(
	"churchit.church_prayers.api.create_prayer"
);

async function prayNow() {
	await pray
		.submit({ prayer_request: props.request.name, content: props.note?.trim() || null })
		.then(
			() => emit("prayed"),
			() => {}
		);
}
</script>
