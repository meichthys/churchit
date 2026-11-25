<template>
	<PageHead
		:crumbs="[
			{ label: __('My Household'), route: '/household' },
			{ label: __('Check-in') },
		]"
		back="/household"
	/>
	<PageBody>
		<Masthead
			:title="__('Check-in')"
			:label="boot.church?.title"
			:dateline="dateline"
		/>
		<LoadState :resource="preCheckIn" v-slot="{ data }">
			<EmptyState
				v-if="!data.functions.length"
				:title="closedTitle(data)"
				:body="closedBody(data)"
			>
				<Button
					variant="outline"
					size="lg"
					class="min-h-11"
					:label="__('Back to my household')"
					route="/household"
				/>
			</EmptyState>

			<EmptyState
				v-else-if="!data.people.length"
				:title="__('No one to check in')"
				:body="
					__(
						'Only adults check in their household. Ask the church office if someone is missing.',
					)
				"
			/>

			<div v-else class="mt-8 grid gap-x-10 gap-y-10 md:grid-cols-12">
				<section
					class="md:col-span-7"
					:class="pass && 'order-2 md:order-1'"
					aria-labelledby="check-in-who"
				>
					<SectionHead
						id="check-in-who"
						:title="__('Who is coming')"
					/>
					<TabButtons
						v-if="data.functions.length > 1"
						v-model="functionName"
						class="mb-4"
						:options="
							data.functions.map((row) => ({
								label: row.function_name,
								value: row.name,
							}))
						"
					/>
					<p v-else class="mb-4 text-lg text-ink-gray-8 md:text-md">
						{{ data.functions[0].function_name
						}}<template v-if="data.functions[0].start_time">
							· <TimeText :value="data.functions[0].start_time!"
						/></template>
					</p>
					<ul
						class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
					>
						<li v-for="person in data.people" :key="person.name">
							<label
								class="flex min-h-[4.5rem] cursor-pointer items-center gap-4 py-3"
							>
								<Checkbox
									v-model="chosen[person.name]"
									size="md"
									:disabled="isIn(person)"
									:aria-label="person.display_name"
								/>
								<Avatar
									:label="person.display_name"
									size="xl"
									shape="circle"
								/>
								<span class="min-w-0 flex-1">
									<span
										class="block text-xl-medium text-ink-gray-9"
										>{{ person.display_name }}</span
									>
									<span
										v-if="person.age"
										class="block text-lg text-ink-gray-6 md:text-md"
										>{{
											__("{0} years old", [person.age])
										}}</span
									>
								</span>
								<span
									v-if="isIn(person)"
									class="text-md-medium text-ink-green-8"
								>
									<span
										class="lucide-check me-1 inline-block size-4 align-text-bottom"
										aria-hidden="true"
									/>{{
										__("In at {0}", [
											formatTime(
												person.checked_in[functionName],
											),
										])
									}}
								</span>
							</label>
						</li>
					</ul>
					<Button
						class="mt-5 min-h-11 w-full md:w-auto"
						variant="solid"
						size="lg"
						icon-left="lucide-qr-code"
						:loading="code.loading"
						:disabled="!selected.length"
						:label="
							pass ? __('Update our pass') : __('Show our pass')
						"
						@click="makePass"
					/>
					<p class="mt-4 text-lg text-ink-gray-6 md:text-md">
						{{
							__(
								"Trouble at the door? A volunteer can check you in by name.",
							)
						}}
					</p>
				</section>

				<section
					v-if="pass"
					class="order-1 md:order-2 md:col-span-5"
					aria-labelledby="check-in-pass"
				>
					<h2 id="check-in-pass" class="sr-only">
						{{ __("Your check-in pass") }}
					</h2>
					<CheckInPass
						:church-name="boot.church?.title || ''"
						:function-name="passFunction?.function_name || ''"
						:time="passFunction?.start_time ?? null"
						:today="today"
						:qr-code="pass.qr_code"
						:valid-until="validUntil"
						:rooms="passFunction?.rooms.join(', ') || ''"
						:people="stub"
						:is-done="isDone"
						:strip="strip"
						:is-fresh="stripIsFresh"
					/>
					<p class="mt-4 text-lg text-ink-gray-8 md:text-md">
						{{
							__(
								"Show this at the door. Name tags print when staff scan it.",
							)
						}}
						{{
							data.has_pickup_codes && hasChildren
								? __(
										"Use the pickup code on the name tag to collect your children.",
									)
								: ""
						}}
					</p>
				</section>
			</div>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Avatar, Button, Checkbox, TabButtons } from "frappe-ui";
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";

import { reportError, useRead } from "@/api";
import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import TimeText from "@/components/TimeText.vue";
import { formatShortDate, formatTime } from "@/format";
import { useLiveRefresh } from "@/realtime";
import { __ } from "@/translate";
import CheckInPass from "./components/CheckInPass.vue";

interface Person {
	name: string;
	display_name: string;
	age: number | null;
	household_role: string | null;
	checked_in: Record<string, string>;
}

interface CheckInFunction {
	name: string;
	function_name: string;
	time: string | null;
	start_time: string | null;
	rooms: string[];
}

interface PreCheckIn {
	functions: CheckInFunction[];
	people: Person[];
	opens_minutes: number | null;
	has_pickup_codes: boolean;
}

interface Pass {
	function: string;
	persons: string[];
	qr_code: string;
	ends: string;
}

const REOPEN_CHECK_MS = 60_000;

const preCheckIn = useRead<PreCheckIn>("household.get_pre_check_in");
const code = useRead<{ qr_code: string; ends: string }, Record<string, any>>(
	"household.get_check_in_code",
	{ immediate: false },
);
const functionName = ref("");
const chosen = reactive<Record<string, boolean>>({});
const pass = ref<Pass | null>(null);
const strip = ref(__("Waiting for the scan"));
const stripIsFresh = ref(false);
let stripTimer: ReturnType<typeof setTimeout> | undefined;

const today = new Date().toLocaleDateString("en-CA");
const dateline = computed(() =>
	__("Show this pass at the door of the service"),
);

const people = computed(() => preCheckIn.data?.people ?? []);
const selected = computed(() =>
	people.value
		.filter((person) => chosen[person.name] && !isIn(person))
		.map((person) => person.name),
);
const passFunction = computed(() =>
	preCheckIn.data?.functions.find((row) => row.name === pass.value?.function),
);
const hasChildren = computed(() =>
	people.value.some(
		(person) =>
			pass.value?.persons.includes(person.name) &&
			person.household_role === "Child",
	),
);
const validUntil = computed(() => {
	if (!pass.value) return "";
	const [day, time] = pass.value.ends.split(" ");
	if (day === today) return formatTime(time);
	return __("{0} at {1}", [formatShortDate(day), formatTime(time)]);
});
const stub = computed(() =>
	people.value
		.filter((person) => pass.value?.persons.includes(person.name))
		.map((person) => ({
			name: person.name,
			display_name: person.display_name,
			at: person.checked_in[pass.value!.function] ?? null,
		})),
);
const isDone = computed(
	() => stub.value.length > 0 && stub.value.every((person) => person.at),
);

watch(
	() => preCheckIn.data,
	(data) => {
		if (!data) return;
		if (!data.functions.some((row) => row.name === functionName.value))
			functionName.value = data.functions[0]?.name ?? "";
		for (const person of data.people)
			if (!(person.name in chosen)) chosen[person.name] = true;
	},
	{ immediate: true },
);

function isIn(person: Person): boolean {
	return Boolean(person.checked_in[functionName.value]);
}

function closedTitle(data: PreCheckIn): string {
	return data.opens_minutes === null
		? __("Check-in is not used here")
		: __("Check-in is not open yet");
}

function closedBody(data: PreCheckIn): string {
	if (data.opens_minutes === null)
		return __("Your church does not use self check-in right now.");
	if (data.opens_minutes === 0)
		return __(
			"Check-in opens when a service starts. This page checks again by itself.",
		);
	return __(
		"Check-in opens {0} minutes before the service starts. This page checks again by itself.",
		[data.opens_minutes],
	);
}

async function makePass() {
	const persons = selected.value;
	const result = await code
		.submit({
			function: functionName.value,
			persons: JSON.stringify(persons),
		})
		.catch((error: unknown) => {
			if (error instanceof Error)
				error.message = error.message.replace(/<br\s*\/?>/gi, "; ");
			void reportError(error);
		});
	if (!result) return;
	pass.value = {
		function: functionName.value,
		persons,
		qr_code: result.qr_code,
		ends: result.ends,
	};
	strip.value = __("Waiting for the scan");
}

async function showScan(previous: Pass, before: Set<string>) {
	await preCheckIn.reload();
	const arrived = people.value.filter(
		(person) =>
			previous.persons.includes(person.name) &&
			person.checked_in[previous.function] &&
			!before.has(person.name),
	);
	if (!arrived.length) return;
	const names = arrived.map((person) => person.display_name.split(" ")[0]);
	const at = formatTime(arrived[0].checked_in[previous.function]);
	strip.value = __("{0} checked in at {1}", [
		new Intl.ListFormat(boot.lang).format(names),
		at,
	]);
	stripIsFresh.value = true;
	clearTimeout(stripTimer);
	stripTimer = setTimeout(() => (stripIsFresh.value = false), 8000);
}

useLiveRefresh(["check-in"], () => {
	if (!pass.value) return void preCheckIn.reload();
	const before = new Set(
		people.value
			.filter((person) => person.checked_in[pass.value!.function])
			.map((person) => person.name),
	);
	void showScan(pass.value, before);
});

const reopenTimer = setInterval(() => {
	if (preCheckIn.data && !preCheckIn.data.functions.length)
		void preCheckIn.reload();
}, REOPEN_CHECK_MS);
onBeforeUnmount(() => {
	clearInterval(reopenTimer);
	clearTimeout(stripTimer);
});
</script>
