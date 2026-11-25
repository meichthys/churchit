<template>
	<li class="py-4 first:pt-0 last:pb-0" :class="fresh && 'is-fresh -mx-3 rounded-4 px-3'">
		<p class="text-lg text-ink-gray-9">
			{{
				__("You are asked to serve as {0} at {1} on {2}.", [
					request.position,
					request.title,
					request.date_display,
				])
			}}
		</p>
		<p v-if="request.time" class="mt-0.5 text-lg text-ink-gray-6">
			<TimeText :value="request.time" />
		</p>
		<div class="mt-3 flex flex-wrap gap-2">
			<Button
				variant="solid"
				size="lg"
				class="min-h-11"
				:label="__('Yes, I can')"
				:loading="answer.loading"
				@click="send('Accepted')"
			/>
			<Button
				variant="outline"
				size="lg"
				class="min-h-11"
				:label="__('I can\'t this time')"
				:loading="answer.loading"
				@click="send('Declined')"
			/>
		</div>
	</li>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";

import { useFrappeAction } from "@/api";
import TimeText from "@/components/TimeText.vue";
import { __ } from "@/translate";

import type { AnswerRequest } from "./types";

const props = defineProps<{ request: AnswerRequest; fresh?: boolean }>();
const emit = defineEmits<{ answered: [] }>();

const answer = useFrappeAction<null, { assignment: string; status: string }>(
	"churchit.church_ministries.member_ministry_team.answer_own_assignment"
);

async function send(status: "Accepted" | "Declined") {
	await answer.submit({ assignment: props.request.name, status }).catch(() => {});
	if (!answer.error) emit("answered");
}
</script>
