<template>
	<!-- One person asking to join: who, when, their words, and the two answers. -->
	<IndexRow
		:title="request.person_name"
		:facts="[__('Asked on {0}', [request.requested_on])]"
		:status="status"
		:fresh="fresh"
	>
		<p
			v-if="request.message"
			class="mt-2 whitespace-pre-line text-lg text-ink-gray-8 md:text-md"
		>
			{{ request.message }}
		</p>
		<div v-if="!status" class="mt-3 flex flex-wrap gap-2">
			<Button
				variant="solid"
				size="lg"
				class="min-h-11"
				:label="__('Approve')"
				:loading="decide.loading && approving"
				@click="answer(true)"
			/>
			<Button
				variant="subtle"
				size="lg"
				class="min-h-11"
				:label="__('Decline')"
				:loading="decide.loading && !approving"
				@click="answer(false)"
			/>
		</div>
	</IndexRow>
</template>

<script setup lang="ts">
import { Button, toast } from "frappe-ui";
import { ref } from "vue";

import { useFrappeAction } from "@/api";
import IndexRow from "@/components/IndexRow.vue";

import { __ } from "@/translate";

import type { JoinRequest } from "./types";

const props = defineProps<{ request: JoinRequest; fresh?: boolean }>();
const emit = defineEmits<{ decided: [] }>();

const decide = useFrappeAction<{ status: string }, Record<string, unknown>>(
	"churchit.church_people.group_api.decide_join_request",
);
const approving = ref(false);
const status = ref<string | null>(null);

async function answer(approve: boolean) {
	approving.value = approve;
	const result = await decide
		.submit({ request: props.request.name, approve })
		.catch(() => null);
	if (!result) return;

	status.value = result.status;
	if (approve)
		toast.success(
			__("{0} is now in the group.", [props.request.person_name]),
		);
	else toast.success(__("You declined {0}.", [props.request.person_name]));
	emit("decided");
}
</script>
