<template>
	<div class="flex flex-wrap items-center gap-2">
		<Button
			v-if="assignment.can_accept"
			variant="solid"
			size="lg"
			class="min-h-11"
			:label="request ? __('Yes, I can') : __('Accept')"
			:loading="answer.loading && answering === 'Accepted'"
			@click="accept"
		/>
		<Button
			v-if="assignment.can_decline"
			:variant="request ? 'outline' : 'ghost'"
			size="lg"
			class="min-h-11"
			:label="request ? __('I can\'t this time') : __('Decline')"
			@click="declining = true"
		/>
		<Button
			v-if="assignment.can_pass_on"
			variant="ghost"
			size="lg"
			class="min-h-11"
			:label="__('Ask someone else')"
			:loading="candidates.loading"
			@click="openReplacement"
		/>
	</div>
	<p
		v-if="assignment.pending_replacement"
		class="mt-2 text-lg text-ink-gray-6 md:text-md"
	>
		{{
			__(
				"You asked {0} to take your place. It passes to them when they accept.",
				[assignment.pending_replacement],
			)
		}}
	</p>

	<FormSheet
		v-model:open="declining"
		:title="__('Decline this request')"
		:description="assignment.function_name"
	>
		<FormControl
			size="lg"
			class="[&_input:not([type=checkbox])]:min-h-11 [&_select]:min-h-11 [&_textarea]:text-lg [&_button]:min-h-11"
			v-model="reason"
			type="text"
			maxlength="140"
			:label="__('Reason (optional)')"
		/>
		<template #actions>
			<Button
				variant="solid"
				theme="red"
				size="lg"
				:label="__('Decline')"
				:loading="answer.loading"
				@click="decline"
			/>
			<Button
				variant="outline"
				size="lg"
				:label="__('Cancel')"
				@click="declining = false"
			/>
		</template>
	</FormSheet>

	<FormSheet
		v-model:open="replacing"
		:title="__('Ask someone else')"
		:description="__('You serve until they accept.')"
	>
		<FormControl
			size="lg"
			class="[&_input:not([type=checkbox])]:min-h-11 [&_select]:min-h-11 [&_textarea]:text-lg [&_button]:min-h-11"
			v-model="replacement"
			type="select"
			:label="__('Person to ask')"
			:options="options"
			:placeholder="__('Choose a person')"
		/>
		<template #actions>
			<Button
				variant="solid"
				size="lg"
				:label="__('Ask')"
				:disabled="!replacement"
				:loading="ask.loading"
				@click="sendAsk"
			/>
			<Button
				variant="outline"
				size="lg"
				:label="__('Cancel')"
				@click="replacing = false"
			/>
		</template>
	</FormSheet>
</template>

<script setup lang="ts">
import { Button, FormControl, toast, useCall } from "frappe-ui";
import { computed, ref } from "vue";

import { reportError, useFrappeAction } from "@/api";
import FormSheet from "@/components/FormSheet.vue";
import { __ } from "@/translate";
import type { Assignment } from "./types";

const TEAM = "churchit.church_ministries.member_ministry_team";

const props = defineProps<{ assignment: Assignment; request?: boolean }>();
const emit = defineEmits<{ changed: [] }>();

const declining = ref(false);
const replacing = ref(false);
const reason = ref("");
const replacement = ref<string | null>(null);
const answering = ref<string | null>(null);

const answer = useFrappeAction<
	void,
	{ assignment: string; status: string; reason?: string }
>(`${TEAM}.answer_own_assignment`);
const ask = useFrappeAction<void, { assignment: string; replacement: string }>(
	`${TEAM}.ask_for_replacement`,
);
const candidates = useCall<
	{ person: string; full_name: string }[],
	{ assignment: string }
>({
	url: `/api/v2/method/${TEAM}.get_replacement_candidates`,
	method: "GET",
	immediate: false,
	onError: reportError,
});

const options = computed(() =>
	(candidates.data || []).map((row) => ({
		label: row.full_name,
		value: row.person,
	})),
);

async function accept() {
	answering.value = "Accepted";
	await answer
		.submit({ assignment: props.assignment.name, status: "Accepted" })
		.then(
			() => emit("changed"),
			() => {},
		);
}

async function decline() {
	answering.value = "Declined";
	await answer
		.submit({
			assignment: props.assignment.name,
			status: "Declined",
			reason: reason.value || undefined,
		})
		.then(
			() => {
				declining.value = false;
				emit("changed");
			},
			() => {},
		);
}

async function openReplacement() {
	replacement.value = null;
	candidates.data = null;
	await candidates
		.submit({ assignment: props.assignment.name })
		.catch(() => {});
	const list = candidates.data as { person: string }[] | null;
	if (!list) return;
	if (!list.length) {
		toast.info(__("No one else on the team is free then."));
		return;
	}
	replacing.value = true;
}

async function sendAsk() {
	if (!replacement.value) return;
	await ask
		.submit({
			assignment: props.assignment.name,
			replacement: replacement.value,
		})
		.then(
			() => {
				replacing.value = false;
				emit("changed");
			},
			() => {},
		);
}
</script>
