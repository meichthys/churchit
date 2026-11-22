<template>
	<!-- The one drawn object of the app: a pass to show at the door. The QR code never moves; the live strip
	     under it has a fixed height so a scan does not shift anything. -->
	<article
		class="mx-auto w-full max-w-[26rem] rounded-6 border border-outline-gray-2 bg-surface-elevation-1 shadow-sm"
		:aria-label="__('Your check-in pass')"
	>
		<header class="flex items-start justify-between gap-4 px-6 pt-5">
			<div class="min-w-0">
				<p class="t-label text-ink-gray-7">{{ churchName }}</p>
				<p class="mt-2 text-xl-semibold text-ink-gray-9">{{ functionName }}</p>
				<p v-if="time" class="mt-0.5 text-lg text-ink-gray-7">
					<TimeText :value="time" />
				</p>
			</div>
			<DateStack :date="today" accent />
		</header>

		<div class="px-6 pb-1 pt-4">
			<div
				v-if="isDone"
				class="flex min-h-[13rem] flex-col items-center justify-center gap-3 rounded-5 border border-outline-gray-1 px-4 py-8 text-center"
			>
				<span class="lucide-check-circle size-10 text-ink-green-8" aria-hidden="true" />
				<p class="text-lg-medium text-ink-gray-9">
					{{ __("Everyone is checked in. You will not need the code again today.") }}
				</p>
			</div>
			<template v-else>
				<div
					class="mx-auto flex w-full max-w-[14rem] items-center justify-center rounded-5 p-3"
					style="background: var(--qr-paper)"
				>
					<img
						:src="qrCode"
						:alt="__('Check-in code')"
						class="aspect-square w-full min-w-[200px]"
					/>
				</div>
				<p class="t-label mt-3 text-center text-ink-gray-7">
					{{ __("Valid until") }}
					<span class="t-numeral text-lg text-ink-gray-9">{{ validUntil }}</span>
				</p>
			</template>
			<p
				class="mt-3 flex h-12 items-center justify-center text-balance text-center text-lg text-ink-gray-7 md:text-md"
				:class="isFresh && 'is-fresh text-ink-gray-9'"
				aria-live="polite"
			>
				{{ strip }}
			</p>
		</div>

		<div class="perforation my-3" aria-hidden="true" />

		<dl class="px-6 pb-6">
			<div class="t-label grid grid-cols-[1fr_auto_auto] gap-x-5 pb-2 text-ink-gray-7">
				<dt>{{ __("Who") }}</dt>
				<dt>{{ __("Room") }}</dt>
				<dt class="min-w-[5.5rem] text-end">{{ __("Time") }}</dt>
			</div>
			<div
				v-for="person in people"
				:key="person.name"
				class="grid min-h-12 grid-cols-[1fr_auto_auto] items-center gap-x-5 border-t border-outline-gray-1 py-2"
			>
				<dd class="min-w-0 text-lg text-ink-gray-9">{{ person.display_name }}</dd>
				<dd class="t-numeral text-[28px] text-ink-gray-9">{{ rooms || "-" }}</dd>
				<dd
					class="min-w-[5.5rem] text-end text-md-medium"
					:class="person.at ? 'text-ink-green-8' : 'text-ink-gray-7'"
				>
					<template v-if="person.at">
						<span
							class="lucide-check me-1 inline-block size-4 align-text-bottom"
							aria-hidden="true"
						/>{{ __("In at {0}", [formatTime(person.at)]) }}
					</template>
					<template v-else>{{ __("Not in yet") }}</template>
				</dd>
			</div>
		</dl>
	</article>
</template>

<script setup lang="ts">
import DateStack from "@/components/DateStack.vue";
import TimeText from "@/components/TimeText.vue";
import { formatTime } from "@/format";
import { __ } from "@/translate";

defineProps<{
	churchName: string;
	functionName: string;
	time: string | null;
	today: string;
	qrCode: string;
	validUntil: string;
	rooms: string;
	people: { name: string; display_name: string; at: string | null }[];
	isDone: boolean;
	strip: string;
	isFresh: boolean;
}>();
</script>
