<template>
	<PageHead
		:crumbs="[{ label: __('My Household'), route: '/household' }, { label: title }]"
		back="/household"
	/>
	<PageBody>
		<Masthead
			:title="title"
			:label="boot.church?.title"
			:dateline="__('What the church keeps about you, and what other members see')"
		/>
		<PageIntro page="personal-details" />
		<LoadState :resource="details" v-slot="{ data }">
			<div
				v-if="stale"
				class="mt-6 rounded-5 border border-outline-amber-2 bg-surface-amber-1 p-4"
				role="alert"
			>
				<p class="text-lg text-ink-gray-9">
					{{
						__(
							"This record was changed while you had it open. Reload it, then make your change again."
						)
					}}
				</p>
				<Button
					class="mt-3 min-h-11"
					variant="outline"
					size="lg"
					:label="__('Reload')"
					@click="reload"
				/>
			</div>

			<p v-if="!data.can_edit" class="mt-6 text-lg text-ink-gray-6">
				{{ __("You can read this record but not change it.") }}
			</p>

			<form
				v-if="form"
				class="mt-8 space-y-12 [&_input:not([type=checkbox])]:min-h-11 [&_select]:min-h-11 [&_input]:text-lg"
				@submit.prevent="save"
			>
				<section aria-labelledby="pd-personal">
					<SectionHead id="pd-personal" :title="__('Personal information')" />
					<div class="grid gap-4 border-t border-outline-gray-1 pt-5 sm:grid-cols-2">
						<FormControl
							size="lg"
							v-if="has('first_name')"
							v-model="form.values.first_name"
							:label="__('First name')"
							required
							:disabled="!data.can_edit"
						/>
						<FormControl
							size="lg"
							v-if="has('last_name')"
							v-model="form.values.last_name"
							:label="__('Last name')"
							:disabled="!data.can_edit"
						/>
						<FormControl
							size="lg"
							v-if="has('gender')"
							v-model="form.values.gender"
							type="select"
							:label="__('Gender')"
							:options="
								data.options.genders.map((gender) => ({
									label: __(gender),
									value: gender,
								}))
							"
							:disabled="!data.can_edit"
						/>
						<FormControl
							size="lg"
							v-if="has('birthday')"
							v-model="form.values.birthday"
							type="date"
							:placeholder="__('Choose a date')"
							:label="__('Birthday')"
							:disabled="!data.can_edit"
						/>
						<FormControl
							size="lg"
							v-if="has('alergies')"
							v-model="form.values.alergies"
							:label="__('Allergies')"
							:disabled="!data.can_edit"
							class="sm:col-span-2"
						/>
					</div>
					<div v-if="has('photo') && data.can_edit" class="mt-5 flex items-center gap-4">
						<Avatar
							:label="data.display_name"
							:image="form.values.photo || undefined"
							size="3xl"
							shape="circle"
						/>
						<FileUploader
							file-types="image/*"
							doctype="Person"
							:docname="data.name"
							:validate-file="validatePhoto"
							@success="(file) => (form!.values.photo = file.file_url)"
							@failure="(message) => toast.error(String(message))"
						>
							<template #default="{ openFileSelector, uploading }">
								<Button
									variant="outline"
									size="lg"
									class="min-h-11"
									icon-left="lucide-camera"
									:loading="uploading"
									:label="
										form.values.photo ? __('Change photo') : __('Add a photo')
									"
									@click="openFileSelector"
								/>
							</template>
						</FileUploader>
					</div>
				</section>

				<section v-if="has('emails') || has('phones')" aria-labelledby="pd-contact">
					<SectionHead id="pd-contact" :title="__('Contact information')" />
					<div v-if="has('emails')" class="mb-8">
						<p class="mb-2 text-lg text-ink-gray-6 md:text-md">
							{{ __("Mark the one we should use to reach you.") }}
						</p>
						<ContactRows
							v-model:rows="form.emails"
							kind="email"
							:person="data.name"
							:types="data.options.email_types"
						/>
					</div>
					<div v-if="has('phones')">
						<p class="mb-2 text-lg text-ink-gray-6 md:text-md">
							{{ __("Mark the one we should call.") }}
						</p>
						<ContactRows
							v-model:rows="form.phones"
							kind="phone"
							:person="data.name"
							:types="data.options.phone_types"
						/>
					</div>
					<div v-if="data.addresses.length" class="mt-8">
						<p class="t-label mb-2 text-ink-gray-7">{{ __("Addresses") }}</p>
						<ul class="divide-y divide-outline-gray-1 border-t border-outline-gray-1">
							<li
								v-for="address in data.addresses"
								:key="address.name"
								class="py-3 text-lg text-ink-gray-9"
							>
								{{ address.text }}
								<span v-if="address.address_type" class="text-ink-gray-6">
									· {{ __(address.address_type) }}</span
								>
							</li>
						</ul>
						<p class="mt-2 text-lg text-ink-gray-6 md:text-md">
							{{ __("To change your address, tell the church office.") }}
						</p>
					</div>
				</section>

				<section v-if="has('marital_status')" aria-labelledby="pd-family">
					<SectionHead id="pd-family" :title="__('Family information')" />
					<div class="grid gap-4 border-t border-outline-gray-1 pt-5 sm:grid-cols-2">
						<FormControl
							size="lg"
							v-model="form.values.marital_status"
							type="select"
							:label="__('Marital status')"
							:options="
								data.options.marital_statuses.map((status) => ({
									label: __(status),
									value: status,
								}))
							"
							:disabled="!data.can_edit"
						/>
						<FormControl
							size="lg"
							v-if="has('anniversary') && showsAnniversary"
							v-model="form.values.anniversary"
							type="date"
							:placeholder="__('Choose a date')"
							:label="__('Anniversary')"
							:disabled="!data.can_edit"
						/>
					</div>
				</section>

				<section v-if="has('hide_from_directory')" aria-labelledby="pd-directory">
					<SectionHead
						id="pd-directory"
						:title="__('Directory')"
						:note="
							__(
								'What the other members of your church see about you on the Member Directory page.'
							)
						"
					/>
					<p
						v-if="data.notes.directory_off"
						class="mb-3 text-lg text-ink-gray-6 md:text-md"
					>
						{{
							__(
								"Your church has no Member Directory page now. If it adds one, other members see what you choose here."
							)
						}}
					</p>
					<div class="space-y-1 border-t border-outline-gray-1 pt-4">
						<FormControl
							v-model="form.values.hide_from_directory"
							type="checkbox"
							:label="__('Hide me from the member directory')"
							:description="
								__(
									'Leave me out of the member directory, the printed church directory, and the birthdays and anniversaries in the bulletin.'
								)
							"
							class="min-h-11"
							:disabled="!data.can_edit"
						/>
						<template v-if="!form.values.hide_from_directory">
							<FormControl
								v-for="share in shares"
								v-show="has(share.field)"
								:key="share.field"
								v-model="form.values[share.field]"
								type="checkbox"
								:label="share.label"
								class="min-h-11"
								:disabled="!data.can_edit"
							/>
						</template>
					</div>
				</section>

				<section v-if="has('exclude_from_ai')" aria-labelledby="pd-ai">
					<SectionHead id="pd-ai" :title="__('AI features')" />
					<p class="mb-1 text-lg text-ink-gray-6 md:text-md">
						{{
							__(
								"The church's system can use AI to help staff: briefings, note drafts, report explanations and suggestions on new requests."
							)
						}}
					</p>
					<p class="mb-3 text-lg text-ink-gray-6 md:text-md">
						{{ data.notes.ai_state }}
					</p>
					<div class="border-t border-outline-gray-1 pt-4">
						<FormControl
							v-model="form.values.exclude_from_ai"
							type="checkbox"
							:label="__('Leave me out of the church\'s AI features')"
							:description="
								__(
									'Church staff still read your details in the church\'s system, and staff who use an AI chat or their own AI app read what their rights allow.'
								)
							"
							class="min-h-11"
							:disabled="!data.can_edit"
						/>
					</div>
				</section>

				<div
					v-if="data.can_edit"
					class="flex flex-col gap-2 border-t border-outline-gray-1 pt-6 sm:flex-row sm:justify-end"
				>
					<Button
						class="min-h-11"
						variant="outline"
						size="lg"
						:label="__('Cancel')"
						route="/household"
					/>
					<Button
						class="min-h-11"
						variant="solid"
						size="lg"
						type="submit"
						:loading="saving"
						:label="__('Save')"
					/>
				</div>
			</form>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Avatar, Button, FileUploader, FormControl, FrappeResponseError, toast } from "frappe-ui";
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { reportError, useAction, useRead } from "@/api";
import { boot } from "@/boot";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageIntro from "@/components/PageIntro.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { __ } from "@/translate";
import ContactRows, { type ContactRow } from "./components/ContactRows.vue";

interface Details {
	name: string;
	display_name: string;
	is_you: boolean;
	modified: string;
	can_edit: boolean;
	fields: string[];
	values: Record<string, any>;
	emails: ContactRow[];
	phones: ContactRow[];
	addresses: { name: string; text: string; address_type: string | null }[];
	options: {
		genders: string[];
		email_types: string[];
		phone_types: string[];
		marital_statuses: string[];
	};
	notes: { ai_state: string; directory_off: boolean };
}

const MAX_PHOTO_BYTES = 5 * 1024 * 1024;

const route = useRoute();
const router = useRouter();

/** /personal-details, /personal-details/list and /personal-details/<person>/edit all open one record. */
const requested = computed(() => {
	const rest = ([] as string[]).concat(
		(route.params.rest as string | string[] | undefined) ?? []
	);
	return rest[0] && !["list", "new"].includes(rest[0]) ? rest[0] : undefined;
});

const details = useRead<Details, Record<string, any>>("account.get_personal_details", {
	params: () => ({ person: requested.value }),
});
const action = useAction<Details, Record<string, any>>("account.save_personal_details", {
	onError: handleSaveError,
});
const form = ref<{
	values: Record<string, any>;
	emails: ContactRow[];
	phones: ContactRow[];
} | null>(null);
const stale = ref(false);
const saving = computed(() => action.loading);

const title = computed(() =>
	!details.data || details.data.is_you ? __("My Details") : details.data.display_name
);
const showsAnniversary = computed(() =>
	["Married", "Widowed"].includes(form.value?.values.marital_status)
);
const shares = [
	{ field: "share_email", label: __("Show email") },
	{ field: "share_phone", label: __("Show phone") },
	{ field: "share_address", label: __("Show address") },
	{ field: "share_birthday", label: __("Show birthday (day and month)") },
];

watch(
	() => details.data,
	(data) => {
		if (!data) return;
		form.value = reactive({
			values: { ...data.values },
			emails: data.emails.map((row) => ({ ...row })),
			phones: data.phones.map((row) => ({ ...row })),
		});
	},
	{ immediate: true }
);

function has(field: string): boolean {
	return Boolean(details.data?.fields.includes(field));
}

function validatePhoto(file: File): string | undefined {
	if (!file.type.startsWith("image/")) return __("Choose a picture.");
	if (file.size > MAX_PHOTO_BYTES) return __("Choose a picture under 5 MB.");
}

function reload() {
	stale.value = false;
	void details.reload();
}

function handleSaveError(error: unknown) {
	if (error instanceof FrappeResponseError && error.type === "TimestampMismatchError")
		stale.value = true;
	else reportError(error);
}

async function save() {
	if (!details.data || !form.value) return;
	const values: Record<string, unknown> = {};
	for (const field of details.data.fields.filter(
		(name) => name !== "emails" && name !== "phones"
	))
		values[field] = form.value.values[field];
	const result = await action
		.submit({
			person: details.data.name,
			modified: details.data.modified,
			values,
			emails: has("emails") ? form.value.emails : undefined,
			phones: has("phones") ? form.value.phones : undefined,
		})
		.catch(() => null);
	if (!result) return;
	toast.success(__("Your details were saved."));
	void router.push("/household");
}
</script>
