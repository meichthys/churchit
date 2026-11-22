<template>
	<PageHead :crumbs="[{ label: __('This week') }]">
		<template v-if="boot.person" #actions>
			<Button
				v-if="give"
				variant="ghost"
				icon-left="lucide-gift"
				:label="give.title"
				@click="openPage(give.href)"
			/>
			<Button
				v-if="canSharePrayer"
				variant="subtle"
				icon-left="lucide-heart"
				:label="__('Share a prayer request')"
				route="/prayer-request/new"
			/>
		</template>
	</PageHead>
	<PageBody>
		<Masthead :title="__('This week')" :label="boot.church?.title" :dateline="dateline" />
		<div
			v-if="boot.person && (give || canSharePrayer)"
			class="mt-5 flex flex-wrap gap-2 md:hidden"
		>
			<Button
				v-if="canSharePrayer"
				variant="subtle"
				size="lg"
				class="min-h-11 flex-1"
				icon-left="lucide-heart"
				:label="__('Share a prayer request')"
				route="/prayer-request/new"
			/>
			<Button
				v-if="give"
				variant="subtle"
				size="lg"
				class="min-h-11 flex-1"
				icon-left="lucide-gift"
				:label="give.title"
				@click="openPage(give.href)"
			/>
		</div>

		<EmptyState
			v-if="!boot.person"
			class="mt-8"
			:title="__('Your login is not linked to a member yet')"
			:body="
				__(
					'The church office can link it to your record. Until then, the pages of the church are open to you.'
				)
			"
		>
			<a
				v-if="boot.website_home"
				:href="boot.website_home"
				class="inline-flex min-h-11 items-center rounded-5 border border-outline-gray-2 px-4 text-lg text-ink-gray-8 hover:bg-surface-gray-2"
			>
				{{ __("Open the church website") }}
			</a>
		</EmptyState>

		<LoadState v-else :resource="home" v-slot="{ data }">
			<NowBlock v-if="data.check_in" :check-in="data.check_in" />

			<div class="mt-8 md:grid md:grid-cols-12 md:gap-x-10">
				<div class="md:col-span-8">
					<section
						v-if="data.needs_answer.length"
						class="mb-8"
						aria-labelledby="answer-head"
					>
						<div class="rounded-6 border border-outline-gray-3 p-5">
							<h2 id="answer-head" class="t-head text-ink-gray-9">
								{{ __("Needs your answer") }}
							</h2>
							<ul class="mt-3 divide-y divide-outline-gray-1">
								<AnswerRequestRow
									v-for="request in data.needs_answer"
									:key="request.name"
									:request="request"
									:fresh="isFresh(request.name)"
									@answered="answered"
								/>
							</ul>
						</div>
					</section>

					<section aria-labelledby="week-head">
						<h2 id="week-head" class="sr-only">{{ __("The week") }}</h2>
						<template v-if="data.week.length">
							<DayBlock
								v-for="day in data.week"
								:key="day.date"
								:date="day.date"
								:today="day.is_today"
							>
								<OrderEntry
									v-for="(entry, index) in day.entries"
									:key="entry.key"
									:title="entry.title"
									:time="entry.time"
									:dim-time="
										Boolean(entry.time) &&
										entry.time === day.entries[index - 1]?.time
									"
									:route="entry.route || undefined"
									:facts="[entry.who]"
									:status="entry.status"
									:fresh="isFresh(entry.key)"
								/>
							</DayBlock>
						</template>
						<EmptyState
							v-else
							:title="__('Nothing is planned for you this week')"
							:body="
								__(
									'Your sign-ups, the times you serve and your group meetings are listed here.'
								)
							"
						>
							<Button
								v-if="signUpsOpen"
								variant="outline"
								size="lg"
								class="min-h-11"
								route="/function-sign-up/list?tab=open"
								:label="__('See what you can sign up for')"
							/>
						</EmptyState>
					</section>

					<section v-if="data.ahead.length" class="mt-8" aria-labelledby="ahead-head">
						<SectionHead id="ahead-head" :title="__('Looking ahead')" />
						<ul class="divide-y divide-outline-gray-1 border-t border-outline-gray-1">
							<li v-for="entry in data.ahead" :key="entry.key">
								<IndexRow
									:title="entry.title"
									:route="entry.route || undefined"
									:facts="[entry.date_display, entry.who]"
									:status="entry.status"
									:fresh="isFresh(entry.key)"
								>
									<template #prefix><DateStack :date="entry.date" /></template>
								</IndexRow>
							</li>
						</ul>
					</section>

					<footer class="mt-10 border-t border-outline-gray-1 pt-6 text-center">
						<p class="t-dateline is-large text-ink-gray-8">
							{{ __("That is the week.") }}
						</p>
						<a
							v-if="calendar"
							:href="calendar.href"
							class="mt-2 inline-block min-h-11 py-2 text-lg text-ink-gray-7 underline underline-offset-4"
						>
							{{ __("See the church calendar") }}
						</a>
					</footer>
				</div>

				<HomeMargin
					:home="data"
					class="mt-10 md:col-span-4 md:mt-0 md:border-s md:border-outline-gray-1 md:ps-10"
				/>
			</div>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button, toast } from "frappe-ui";
import { computed } from "vue";

import { useRead } from "@/api";
import { boot, isPageHidden } from "@/boot";
import DateStack from "@/components/DateStack.vue";
import DayBlock from "@/components/DayBlock.vue";
import EmptyState from "@/components/EmptyState.vue";
import IndexRow from "@/components/IndexRow.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import OrderEntry from "@/components/OrderEntry.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { formatDayMonth, formatTime } from "@/format";
import { useLiveRefresh } from "@/realtime";
import { __ } from "@/translate";

import AnswerRequestRow from "./AnswerRequestRow.vue";
import HomeMargin from "./HomeMargin.vue";
import NowBlock from "./NowBlock.vue";
import type { Entry, Home } from "./types";

const home = useRead<Home>("home.get_home", { immediate: Boolean(boot.person) });
const { mark, isFresh } = useFreshInk();

const calendar = computed(() => boot.site_links.find((link) => link.page === "calendar"));
const signUpsOpen = computed(() => !isPageHidden("function-sign-up"));
const give = boot.site_links.find((link) => link.page === "give");
const canSharePrayer =
	!isPageHidden("prayer-request") &&
	boot.navigation.some((section) =>
		section.links.some((link) => link.page === "prayer-request")
	);

/** A page of the website, in the same tab (frappe-ui's Button href would open a new one). */
function openPage(href: string) {
	window.location.assign(href);
}

const entries = computed<Entry[]>(() => home.data?.week.flatMap((day) => day.entries) ?? []);

function phrase(entry: Entry): string {
	const isToday = entry.date === home.data?.week[0]?.date && home.data.week[0].is_today;
	const day = formatDayMonth(entry.date, true);
	const time = entry.time ? formatTime(entry.time) : "";
	const name = entry.kind === "serving" ? entry.who || "" : entry.title;
	if (entry.kind === "serving") {
		if (isToday)
			return time
				? __("You serve as {0} today at {1}.", [name, time])
				: __("You serve as {0} today.", [name]);
		return time
			? __("You serve as {0} on {1} at {2}.", [name, day, time])
			: __("You serve as {0} on {1}.", [name, day]);
	}
	if (entry.kind === "group") {
		if (isToday)
			return time
				? __("{0} meets today at {1}.", [name, time])
				: __("{0} meets today.", [name]);
		return time
			? __("{0} meets on {1} at {2}.", [name, day, time])
			: __("{0} meets on {1}.", [name, day]);
	}
	if (isToday)
		return time
			? __("You are signed up for {0} today at {1}.", [name, time])
			: __("You are signed up for {0} today.", [name]);
	return time
		? __("You are signed up for {0} on {1} at {2}.", [name, day, time])
		: __("You are signed up for {0} on {1}.", [name, day]);
}

const dateline = computed(() => {
	if (!boot.person) return __("Your week at the church, once your login is linked");
	if (!home.data) return "";
	const first = entries.value.slice(0, 2).map(phrase);
	if (first.length) return first.join(" ");
	if (home.data.ahead.length) return __("A quiet week.");
	return __("A quiet week. Nothing is planned for you yet.");
});

function answered() {
	toast.success(__("Thank you. Your answer is sent."));
	home.reload();
}

useLiveRefresh(["sign-ups", "serving", "groups", "group-meetings", "check-in"], async () => {
	if (!boot.person) return;
	const before = new Set([
		...entries.value.map((entry) => entry.key),
		...(home.data?.ahead.map((entry) => entry.key) ?? []),
		...(home.data?.needs_answer.map((request) => request.name) ?? []),
	]);
	await home.reload();
	const keys = [
		...entries.value.map((entry) => entry.key),
		...(home.data?.ahead.map((entry) => entry.key) ?? []),
		...(home.data?.needs_answer.map((request) => request.name) ?? []),
	];
	for (const key of keys) if (!before.has(key)) mark(key);
});
</script>
