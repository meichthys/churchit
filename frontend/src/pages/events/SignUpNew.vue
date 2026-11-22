<template>
	<PageHead
		:crumbs="[{ label: __('Sign-Ups'), route: '/function-sign-up' }, { label: __('Sign up') }]"
		back="/function-sign-up/list?tab=open"
	/>
	<PageBody>
		<LoadState :resource="open" v-slot="{ data }">
			<template v-if="chosen(data.items)">
				<Masthead
					:title="chosen(data.items)!.function_name"
					:label="boot.church?.title"
					:dateline="chosen(data.items)!.date_long"
				/>
				<p
					v-if="chosen(data.items)!.description"
					class="mt-6 whitespace-pre-line max-w-[34rem] text-p-lg text-ink-gray-7"
				>
					{{ chosen(data.items)!.description }}
				</p>
				<SignUpForm
					:items="chosen(data.items)!.items || []"
					:submit-label="__('Sign up')"
					cancel-route="/function-sign-up/list?tab=open"
					:busy="signUp.loading"
					@submit="save(chosen(data.items)!, $event)"
				/>
			</template>
			<template v-else-if="onRegister(data.items)">
				<Masthead
					:title="onRegister(data.items)!.function_name"
					:label="boot.church?.title"
					:dateline="onRegister(data.items)!.date_long"
				/>
				<EmptyState
					:title="__('This event has its own sign-up page')"
					:body="__('It asks you some questions first.')"
				>
					<a
						:href="`/register?function=${encodeURIComponent(functionName)}`"
						class="inline-flex min-h-11 items-center text-xl-medium text-ink-gray-9 underline decoration-outline-gray-3 underline-offset-4"
					>
						{{ __("Open the sign-up page") }}
					</a>
				</EmptyState>
			</template>
			<template v-else>
				<Masthead
					:title="__('Sign up')"
					:label="boot.church?.title"
					:dateline="__('Pick an event')"
				/>
				<EmptyState
					:title="__('This event is not open for you')"
					:body="__('Events that take sign-ups are listed under Open.')"
				>
					<Button
						size="lg"
						class="min-h-11"
						:label="__('See what is open')"
						route="/function-sign-up/list?tab=open"
					/>
				</EmptyState>
			</template>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button, toast } from "frappe-ui";
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAction, useRead } from "@/api";
import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import { __ } from "@/translate";

import SignUpForm from "./SignUpForm.vue";
import type { OpenFunction } from "./types";

interface SaveParams {
	function: string;
	attending: boolean;
	notes: string;
	items: { item: string; my_quantity: number }[];
}

const route = useRoute();
const router = useRouter();
const functionName = computed(() => String(route.query.function || ""));

const open = useRead<{ items: OpenFunction[] }>("events.get_open_functions");
const signUp = useAction<
	{ name: string; status: string; waits_for: string; amount_due: string; pay_url: string },
	SaveParams
>("events.sign_up");

const chosen = (items: OpenFunction[]) =>
	items.find((row) => row.name === functionName.value && row.signs_up_in === "app");
const onRegister = (items: OpenFunction[]) =>
	items.find((row) => row.name === functionName.value && row.signs_up_in === "register");

if (!functionName.value) router.replace("/function-sign-up/list?tab=open");

async function save(
	row: OpenFunction,
	value: { attending: boolean; notes: string; items: { item: string; my_quantity: number }[] }
) {
	const result = await signUp.submit({ function: row.name, ...value }).catch(() => null);
	if (!result) return;
	if (result.status === "Waitlisted")
		toast.success(__("You are on the waitlist for {0}.", [row.function_name]));
	else if (result.status === "Pending" && result.waits_for === "payment")
		toast.success(__("Pay to keep your place at {0}.", [row.function_name]));
	else if (result.status === "Pending")
		toast.success(__("Your sign-up for {0} waits for approval.", [row.function_name]));
	else toast.success(__("You are signed up for {0}.", [row.function_name]));
	router.replace(`/function-sign-up/${result.name}`);
}
</script>
