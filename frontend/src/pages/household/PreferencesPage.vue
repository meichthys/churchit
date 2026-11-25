<template>
	<PageHead :crumbs="[{ label: __('Preferences') }]" />
	<PageBody>
		<Masthead :title="__('Preferences')" :label="boot.church?.title" :dateline="dateline" />
		<LoadState :resource="preferences" v-slot="{ data }">
			<div class="mt-8 grid gap-x-10 gap-y-10 md:grid-cols-12">
				<div class="md:col-span-8">
					<section aria-labelledby="pref-contact">
						<SectionHead id="pref-contact" :title="__('How we may reach you')" />
						<div v-if="data.channels.length" class="border-t border-outline-gray-1">
							<p
								v-if="data.is_globally_unsubscribed"
								class="py-3 text-lg text-ink-gray-8 md:text-md"
							>
								{{
									__(
										"You stopped every email this site sends. When you turn on an email switch, emails to this address start again."
									)
								}}
							</p>
							<p
								v-if="data.has_stopped_church_emails"
								class="py-3 text-lg text-ink-gray-8 md:text-md"
							>
								{{
									__(
										"You stopped all emails from {0}. Turn on Church News to hear from us again.",
										[data.church_name || ""]
									)
								}}
							</p>
							<ul class="divide-y divide-outline-gray-1">
								<li
									v-for="row in data.purposes"
									:key="row.purpose"
									class="py-4"
									:class="isFresh(row.purpose) && 'is-fresh'"
								>
									<p class="text-xl-medium text-ink-gray-9">
										{{ __(row.purpose) }}
									</p>
									<p
										v-if="row.description"
										class="mt-0.5 text-lg text-ink-gray-6 md:text-md"
									>
										{{ __(row.description) }}
									</p>
									<div class="mt-2 flex flex-wrap gap-x-8">
										<Switch
											v-for="channel in data.channels"
											:key="channel"
											padded
											size="md"
											:aria-label="
												__('{0} by {1}', [
													__(row.purpose),
													channelLabel(channel),
												])
											"
											:model-value="Boolean(row.allowed[channel])"
											:label="channelLabel(channel)"
											:disabled="saving === `${channel}|${row.purpose}`"
											@update:model-value="(value: boolean) => choose(channel, row.purpose, value)"
										/>
									</div>
								</li>
							</ul>
						</div>
						<p
							v-if="!data.channels.includes('Email')"
							class="py-3 text-lg text-ink-gray-8 md:text-md"
						>
							{{
								__(
									"There is no email address on file for you, so you cannot choose emails here. Please contact the church office to add one."
								)
							}}
						</p>
						<EmptyState
							v-if="!data.channels.length"
							:title="__('Nothing to choose yet')"
							:body="
								__(
									'Add an email address to your details, then come back to choose what we send you.'
								)
							"
						>
							<Button
								variant="outline"
								size="lg"
								class="min-h-11"
								:label="__('Open my details')"
								route="/personal-details"
							/>
						</EmptyState>
						<p v-if="data.email" class="mt-3 text-lg text-ink-gray-6 md:text-md">
							{{ __("We write to {0}.", [data.email]) }}
							<template v-if="data.phone">{{
								__("We text {0}.", [data.phone])
							}}</template>
						</p>
					</section>
				</div>

				<aside class="md:col-span-4 md:border-s md:border-outline-gray-1 md:ps-10">
					<section v-if="data.push_public_key" aria-labelledby="pref-push">
						<SectionHead id="pref-push" :title="__('This device')" />
						<p class="text-lg text-ink-gray-8 md:text-md">
							{{ pushText }}
						</p>
						<Button
							v-if="pushState === 'off' || pushState === 'on'"
							class="mt-4 min-h-11 w-full md:w-auto"
							:variant="pushState === 'on' ? 'outline' : 'solid'"
							size="lg"
							:icon-left="pushState === 'on' ? 'lucide-bell-off' : 'lucide-bell'"
							:loading="pushBusy"
							:label="
								pushState === 'on'
									? __('Turn off notifications')
									: __('Allow notifications')
							"
							@click="
								pushState === 'on'
									? turnPushOff()
									: turnPushOn(data.push_public_key)
							"
						/>
					</section>

					<section v-if="installable" class="mt-10" aria-labelledby="pref-install">
						<SectionHead id="pref-install" :title="__('Install the app')" />
						<p class="text-lg text-ink-gray-8 md:text-md">
							{{ __("Open the member app from your home screen.") }}
						</p>
						<Button
							class="mt-4 min-h-11 w-full md:w-auto"
							variant="outline"
							size="lg"
							icon-left="lucide-download"
							:label="__('Install')"
							@click="install"
						/>
					</section>

					<section class="mt-10" aria-labelledby="pref-look">
						<SectionHead id="pref-look" :title="__('Appearance')" />
						<Button
							class="theme-switch min-h-11 w-full md:w-auto"
							variant="outline"
							size="lg"
							:icon-left="isDark ? 'lucide-sun' : 'lucide-moon'"
							:label="isDark ? __('Use light mode') : __('Use dark mode')"
						/>
					</section>
				</aside>
			</div>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button, Switch, toast } from "frappe-ui";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { useFrappeAction, useRead } from "@/api";
import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { installPrompt } from "@/pwa";
import { __ } from "@/translate";

interface Preferences {
	church_name: string | null;
	email: string | null;
	phone: string | null;
	channels: string[];
	purposes: { purpose: string; description: string | null; allowed: Record<string, boolean> }[];
	is_globally_unsubscribed: boolean;
	has_stopped_church_emails: boolean;
	push_public_key: string | null;
}

type PushState = "unsupported" | "checking" | "blocked" | "off" | "on";

const preferences = useRead<Preferences>("account.get_preferences");
const setPreference = useFrappeAction<{ message: string }, Record<string, any>>(
	"churchit.church_communications.preferences.set_preference"
);
const subscribe = useFrappeAction<unknown, Record<string, any>>(
	"churchit.church_communications.push.subscribe"
);
const unsubscribe = useFrappeAction<unknown, Record<string, any>>(
	"churchit.church_communications.push.unsubscribe"
);
const { mark, isFresh } = useFreshInk();
const saving = ref("");
const pushState = ref<PushState>("checking");
const pushBusy = ref(false);
const isDark = ref(document.documentElement.getAttribute("data-theme") === "dark");
let observer: MutationObserver | undefined;

const dateline = computed(() => __("What we may send you, and how this app looks on your device"));
const installable = computed(() => Boolean(installPrompt.value));
const pushText = computed(() => {
	if (pushState.value === "on") return __("This device gets notifications from the church.");
	if (pushState.value === "unsupported")
		return __(
			"This browser cannot show notifications. On an iPhone or iPad (iOS 16.4 or later), first add this site to the Home Screen, then open it from there."
		);
	if (pushState.value === "blocked")
		return __(
			"Notifications are blocked in this browser. Allow them in the browser settings, then come back."
		);
	return __("Allow notifications to hear from the church on this device.");
});

function channelLabel(channel: string): string {
	return { Email: __("Email"), SMS: __("Text"), Push: __("Push") }[channel] ?? channel;
}

async function choose(channel: string, purpose: string, allow: boolean) {
	saving.value = `${channel}|${purpose}`;
	const result = await setPreference.submit({ channel, purpose, allow }).catch(() => null);
	saving.value = "";
	if (!result) return void preferences.reload();
	await preferences.reload();
	mark(purpose);
	toast.success(result.message);
}

async function install() {
	await installPrompt.value?.prompt();
	installPrompt.value = null;
}

async function findSubscription(): Promise<PushSubscription | null> {
	const registration = await navigator.serviceWorker.ready;
	return registration.pushManager.getSubscription();
}

async function checkPush(resubscribe = false) {
	if (
		!("serviceWorker" in navigator) ||
		!("PushManager" in window) ||
		!("Notification" in window)
	) {
		pushState.value = "unsupported";
		return;
	}
	if (Notification.permission === "denied") {
		pushState.value = "blocked";
		return;
	}
	const subscription = await findSubscription();
	if (subscription && Notification.permission === "granted" && resubscribe) {
		await subscribe.submit({ subscription: JSON.stringify(subscription) }).catch(() => {});
		await preferences.reload();
	}
	pushState.value = subscription ? "on" : "off";
}

async function turnPushOn(publicKey: string) {
	pushBusy.value = true;
	try {
		if ((await Notification.requestPermission()) !== "granted")
			return void (await checkPush());
		const registration = await navigator.serviceWorker.ready;
		const subscription = await registration.pushManager.subscribe({
			userVisibleOnly: true,
			applicationServerKey: publicKey,
		});
		await subscribe.submit({ subscription: JSON.stringify(subscription) }).catch(async () => {
			await subscription.unsubscribe();
			throw new Error("subscribe failed");
		});
		pushState.value = "on";
		await preferences.reload();
	} catch {
		await checkPush();
	} finally {
		pushBusy.value = false;
	}
}

async function turnPushOff() {
	pushBusy.value = true;
	try {
		const subscription = await findSubscription();
		if (subscription) {
			await unsubscribe.submit({ endpoint: subscription.endpoint });
			await subscription.unsubscribe();
		}
		pushState.value = "off";
		await preferences.reload();
	} catch {
		await checkPush();
	} finally {
		pushBusy.value = false;
	}
}

onMounted(() => {
	watch(
		() => preferences.data?.push_public_key,
		(key) => void checkPush(Boolean(key)),
		{ immediate: true }
	);
	observer = new MutationObserver(
		() => (isDark.value = document.documentElement.getAttribute("data-theme") === "dark")
	);
	observer.observe(document.documentElement, {
		attributes: true,
		attributeFilter: ["data-theme"],
	});
});
onBeforeUnmount(() => observer?.disconnect());
</script>
