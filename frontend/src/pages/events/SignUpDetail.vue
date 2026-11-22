<template>
	<PageHead
		:crumbs="[
			{ label: __('Sign-Ups'), route: '/function-sign-up' },
			{ label: detail.data?.function_name || name },
		]"
		back="/function-sign-up/list"
	>
		<template v-if="detail.data" #actions>
			<Button
				v-if="detail.data.can_edit"
				:label="__('Change')"
				icon-left="lucide-pencil"
				:route="`/function-sign-up/${name}/edit`"
			/>
		</template>
	</PageHead>
	<PageBody>
		<LoadState :resource="detail" v-slot="{ data }">
			<Masthead
				:title="data.function_name"
				:label="boot.church?.title"
				:dateline="data.date_long"
			>
				<div
					class="mt-4"
					:class="isFresh('status') && 'is-fresh -mx-3 rounded-4 px-3 py-2'"
				>
					<StatusBadge :status="data.status" />
					<p
						v-if="statusLine(data)"
						class="mt-2 max-w-[34rem] text-p-lg text-ink-gray-7"
					>
						{{ statusLine(data) }}
					</p>
					<Button
						v-if="data.can_edit"
						class="mt-4 min-h-11 w-full md:hidden"
						size="lg"
						icon-left="lucide-pencil"
						:label="__('Change my sign-up')"
						:route="`/function-sign-up/${name}/edit`"
					/>
				</div>
			</Masthead>

			<div class="mt-8 grid gap-10 md:grid-cols-12">
				<div class="md:col-span-8">
					<section>
						<SectionHead :title="__('Who is coming')" />
						<ul
							v-if="data.attendees.length"
							class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
						>
							<li
								v-for="attendee in data.attendees"
								:key="attendee.name"
								class="py-3 text-lg text-ink-gray-9"
							>
								{{ attendee.name }}
								<span v-if="attendee.selection" class="text-ink-gray-6"
									>· {{ attendee.selection }}</span
								>
							</li>
						</ul>
						<p
							v-else
							class="t-dateline border-t border-outline-gray-1 pt-3 text-ink-gray-6"
						>
							{{ __("You are not coming.") }}
						</p>
					</section>

					<section v-if="data.items.some((item) => item.my_quantity)" class="mt-10">
						<SectionHead :title="__('What you bring')" />
						<ul class="divide-y divide-outline-gray-1 border-t border-outline-gray-1">
							<li
								v-for="row in data.items.filter((item) => item.my_quantity)"
								:key="row.item"
								class="flex justify-between gap-4 py-3 text-lg"
							>
								<span class="text-ink-gray-9">{{ row.item }}</span>
								<span class="tabular-nums text-ink-gray-7">{{
									row.my_quantity
								}}</span>
							</li>
						</ul>
					</section>

					<section v-if="data.notes" class="mt-10">
						<SectionHead :title="__('Notes')" />
						<p
							class="whitespace-pre-line border-t border-outline-gray-1 pt-3 text-p-lg text-ink-gray-8"
						>
							{{ data.notes }}
						</p>
					</section>
				</div>

				<aside
					v-if="hasMoney(data) || data.can_cancel"
					class="md:col-span-4 md:border-s md:border-outline-gray-1 md:ps-10"
				>
					<section v-if="hasMoney(data)">
						<SectionHead :title="__('Payment')" />
						<dl class="space-y-2 text-lg">
							<div v-if="data.amount_due" class="flex items-baseline gap-2">
								<dt class="text-ink-gray-7">{{ __("Amount due") }}</dt>
								<span class="leader" aria-hidden="true" />
								<dd class="tabular-nums text-ink-gray-9">{{ data.amount_due }}</dd>
							</div>
							<div v-if="data.amount_paid" class="flex items-baseline gap-2">
								<dt class="text-ink-gray-7">{{ __("Paid") }}</dt>
								<span class="leader" aria-hidden="true" />
								<dd class="tabular-nums text-ink-green-8">
									{{ data.amount_paid }}
								</dd>
							</div>
						</dl>
						<StatusBadge
							v-if="data.payment_status"
							:status="data.payment_status"
							class="mt-3"
						/>
						<p v-if="data.pay_url" class="mt-4">
							<span class="rubric">{{ __("Pay to keep your place.") }}</span>
							<a
								:href="data.pay_url"
								class="mt-2 block min-h-11 text-xl-medium text-ink-gray-9 underline decoration-outline-gray-3 underline-offset-4"
							>
								{{ __("Pay now") }}
							</a>
						</p>
					</section>

					<section v-if="data.can_cancel" :class="hasMoney(data) && 'mt-10'">
						<SectionHead :title="__('Cancel')" />
						<p class="text-p-lg text-ink-gray-7">
							{{
								__(
									"If you cannot come, cancel so someone on the waitlist can have your place."
								)
							}}
						</p>
						<Button
							class="mt-4 min-h-11 w-full md:w-auto"
							size="lg"
							theme="red"
							:label="__('Cancel my sign-up')"
							@click="isCancelling = true"
						/>
					</section>
				</aside>
			</div>
		</LoadState>
	</PageBody>

	<FormSheet
		v-model:open="isCancelling"
		:title="__('Cancel your sign-up?')"
		:description="__('Your place goes to the next person on the waitlist.')"
	>
		<template #actions>
			<Button size="lg" :label="__('Keep my place')" @click="isCancelling = false" />
			<Button
				size="lg"
				variant="solid"
				theme="red"
				:label="__('Cancel my sign-up')"
				:loading="cancel.loading"
				@click="confirmCancel"
			/>
		</template>
	</FormSheet>
</template>

<script setup lang="ts">
import { Button, toast } from "frappe-ui";
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { errorText, useAction, useRead } from "@/api";
import { boot } from "@/boot";
import FormSheet from "@/components/FormSheet.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";
import { __ } from "@/translate";

import type { SignUpDetail } from "./types";

const route = useRoute();
const router = useRouter();
const name = computed(() => String(route.params.name));

const detail = useRead<SignUpDetail, { name: string }>("events.get_sign_up", {
	params: () => ({ name: name.value }),
});
const cancel = useAction<unknown, { name: string }>("events.cancel_sign_up");
const { mark, isFresh } = useFreshInk();
const isCancelling = ref(false);

useLiveRefresh(["sign-ups"], async (hint) => {
	if (hint?.name && hint.name !== name.value) return;
	const before = detail.data?.status;
	await detail.reload();
	if (before && detail.data && before !== detail.data.status) mark("status");
});

const hasMoney = (data: SignUpDetail) =>
	Boolean(data.amount_due || data.amount_paid || data.payment_status);

function statusLine(data: SignUpDetail): string {
	if (data.status === "Pending" && data.waits_for === "payment") {
		return data.hold_expires
			? __("Pay by {0} to keep your place.", [data.hold_expires])
			: __("Pay to keep your place.");
	}
	if (data.status === "Pending") return __("The church must approve your place.");
	if (data.status === "Waitlisted")
		return __("The event is full. You will get an email if a place opens.");
	if (data.status === "Cancelled")
		return __("This sign-up is cancelled. Make a new sign-up if you want to come.");
	return "";
}

async function confirmCancel() {
	try {
		await cancel.submit({ name: name.value });
	} catch {
		return;
	}
	isCancelling.value = false;
	toast.success(__("Your sign-up is cancelled."));
	router.replace("/function-sign-up/list");
}
</script>
