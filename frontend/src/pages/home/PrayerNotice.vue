<template>
	<li class="py-4 first:pt-0">
		<RouterLink
			:to="`/community-prayer-requests/${encodeURIComponent(request.name)}`"
			class="t-subhead inline-block py-2 text-ink-gray-9 underline decoration-outline-gray-3 underline-offset-4 hover:decoration-ink-gray-7 md:py-0"
		>
			{{ request.title || __("Prayer request") }}
		</RouterLink>
		<p v-if="request.request" class="mt-1 line-clamp-4 text-p-lg text-ink-gray-8">
			{{ request.request }}
		</p>
		<div class="mt-3 flex flex-wrap items-center gap-3">
			<p
				v-if="prayed"
				class="flex min-h-11 items-center gap-1.5 text-lg font-medium text-ink-green-8"
			>
				<span class="lucide-check size-4" aria-hidden="true" />
				{{ __("You prayed") }}
			</p>
			<Button
				v-else
				variant="subtle"
				size="lg"
				class="min-h-11"
				icon-left="lucide-heart"
				:label="__('I prayed')"
				:loading="pray.loading"
				@click="send"
			/>
			<span v-if="count" class="text-lg text-ink-gray-6">{{
				__("{0} praying", [count])
			}}</span>
		</div>
	</li>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { computed, ref } from "vue";

import { useFrappeAction } from "@/api";
import { __ } from "@/translate";

import type { Home } from "./types";

const props = defineProps<{ request: Home["prayer_requests"][number] }>();

const prayed = ref(false);
const count = computed(() => props.request.prayer_count + (prayed.value ? 1 : 0));
const pray = useFrappeAction<{ name: string }, { prayer_request: string }>(
	"churchit.church_prayers.api.create_prayer"
);

async function send() {
	await pray.submit({ prayer_request: props.request.name }).catch(() => {});
	if (!pray.error) prayed.value = true;
}
</script>
