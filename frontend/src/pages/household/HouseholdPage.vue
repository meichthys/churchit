<template>
	<PageHead :crumbs="[{ label: __('My Household') }]">
		<template v-if="household.data?.add_child" #actions>
			<Button
				variant="outline"
				icon-left="lucide-plus"
				:label="__('Add a child')"
				@click="addingChild = true"
			/>
		</template>
	</PageHead>
	<PageBody>
		<Masthead
			:title="__('My Household')"
			:label="boot.church?.title"
			:dateline="dateline"
		/>
		<LoadState :resource="household" v-slot="{ data }">
			<div class="mt-8 grid gap-x-10 gap-y-10 md:grid-cols-12">
				<div class="md:col-span-8">
					<section aria-labelledby="household-people">
						<SectionHead
							id="household-people"
							:title="__('People')"
						/>
						<ul
							class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
						>
							<li
								v-for="member in data.members"
								:key="member.name"
								class="flex items-center gap-4 py-4"
								:class="isFresh(member.name) && 'is-fresh'"
							>
								<Avatar
									:label="member.display_name"
									size="xl"
									shape="circle"
								/>
								<div class="min-w-0 flex-1">
									<p class="text-xl-medium text-ink-gray-9">
										{{ member.display_name }}
										<span
											v-if="member.is_you"
											class="text-lg font-normal text-ink-gray-6"
											>{{ __("(you)") }}</span
										>
									</p>
									<Facts
										:facts="[
											member.household_role
												? __(member.household_role)
												: null,
											member.age
												? __('{0} years old', [
														member.age,
													])
												: null,
										]"
										class="mt-0.5 text-lg text-ink-gray-6 md:text-md"
									/>
								</div>
								<Button
									v-if="member.can_edit"
									variant="outline"
									size="lg"
									class="min-h-11"
									:label="__('Edit')"
									:aria-label="
										__('Edit {0}', [member.display_name])
									"
									:route="`/personal-details/${member.name}/edit`"
								/>
							</li>
						</ul>
						<p class="mt-4 text-lg text-ink-gray-6 md:text-md">
							{{
								data.add_child
									? __(
											"To add an adult or remove someone, contact the church office.",
										)
									: __(
											"To add or remove someone, contact the church office.",
										)
							}}
						</p>
						<div v-if="data.add_child" class="mt-5 md:hidden">
							<Button
								variant="outline"
								size="lg"
								class="min-h-11 w-full md:w-auto"
								icon-left="lucide-plus"
								:label="__('Add a child')"
								@click="addingChild = true"
							/>
						</div>
					</section>
				</div>

				<aside
					class="md:col-span-4 md:border-s md:border-outline-gray-1 md:ps-10"
				>
					<section
						v-if="data.family"
						aria-labelledby="household-photo"
					>
						<SectionHead
							id="household-photo"
							:title="data.family.title"
						/>
						<img
							v-if="data.family.photo"
							:src="data.family.photo"
							:alt="__('Photo of {0}', [data.family.title])"
							class="w-full rounded-6 object-cover"
							:class="isFresh(data.family.name) && 'is-fresh'"
						/>
						<p v-else class="t-dateline text-ink-gray-6">
							{{ __("No household photo yet.") }}
						</p>
						<p
							v-if="data.family.address"
							class="mt-4 text-lg text-ink-gray-8 md:text-md"
						>
							{{ data.family.address }}
						</p>
						<FileUploader
							v-if="data.can_change_photo"
							:file-types="'image/*'"
							doctype="Family"
							:docname="data.family.name"
							:private="false"
							:validate-file="validatePhoto"
							@success="
								(file) =>
									savePhoto(data.family!.name, file.file_url)
							"
							@failure="(message) => toast.error(String(message))"
						>
							<template
								#default="{ openFileSelector, uploading }"
							>
								<Button
									class="mt-4 min-h-11 w-full md:w-auto"
									variant="outline"
									size="lg"
									icon-left="lucide-camera"
									:loading="uploading || photoAction.loading"
									:label="
										data.family.photo
											? __('Change photo')
											: __('Add a photo')
									"
									@click="openFileSelector"
								/>
							</template>
						</FileUploader>
					</section>
					<section
						v-if="boot.check_in.enabled"
						class="mt-10"
						aria-labelledby="household-check-in"
					>
						<SectionHead
							id="household-check-in"
							:title="__('Check-in')"
						/>
						<p class="text-lg text-ink-gray-8 md:text-md">
							{{
								boot.check_in.open
									? __(
											"Check-in is open. Make your pass and show it at the door.",
										)
									: __(
											"Check-in opens shortly before the service.",
										)
							}}
						</p>
						<Button
							class="mt-4 min-h-11 w-full md:w-auto"
							variant="outline"
							size="lg"
							icon-left="lucide-qr-code"
							:label="__('Open the check-in pass')"
							route="/check-in"
						/>
					</section>
				</aside>
			</div>
		</LoadState>
	</PageBody>

	<AddChildSheet
		v-if="household.data?.add_child"
		v-model:open="addingChild"
		:last-name="household.data.add_child.last_name"
		:adult-age="household.data.add_child.adult_age"
		:today="household.data.add_child.today"
		@added="household.reload()"
	/>
</template>

<script setup lang="ts">
import { Avatar, Button, FileUploader, toast } from "frappe-ui";
import { computed, ref } from "vue";

import { useFrappeAction, useRead } from "@/api";
import { boot } from "@/boot";
import Facts from "@/components/Facts.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";
import { __ } from "@/translate";
import AddChildSheet from "./components/AddChildSheet.vue";

interface Member {
	name: string;
	display_name: string;
	household_role: string | null;
	age: number | null;
	is_you: boolean;
	can_edit: boolean;
}

interface Household {
	person: string;
	family: {
		name: string;
		title: string;
		photo: string | null;
		address: string | null;
	} | null;
	can_change_photo: boolean;
	members: Member[];
	add_child: {
		last_name: string | null;
		adult_age: number;
		today: string;
	} | null;
}

const MAX_PHOTO_BYTES = 5 * 1024 * 1024;

const household = useRead<Household>("household.get_household");
const photoAction = useFrappeAction<unknown, Record<string, any>>(
	"frappe.client.set_value",
);
const addingChild = ref(false);
const { mark, isFresh } = useFreshInk();

const dateline = computed(() => {
	const data = household.data;
	if (!data) return __("The people in your household");
	return (
		data.family?.address ||
		data.family?.title ||
		__("The people in your household")
	);
});

useLiveRefresh(["household"], (hint) => {
	const before = new Set(
		household.data?.members.map((member) => member.name),
	);
	Promise.resolve(household.reload()).then(() => {
		const added = household.data?.members.filter(
			(member) => !before.has(member.name),
		);
		if (hint && added?.length) added.forEach((member) => mark(member.name));
		else if (hint && household.data?.family)
			mark(household.data.family.name);
	});
});

function validatePhoto(file: File): string | undefined {
	if (!file.type.startsWith("image/")) return __("Choose a picture.");
	if (file.size > MAX_PHOTO_BYTES) return __("Choose a picture under 5 MB.");
}

async function savePhoto(family: string, fileUrl: string) {
	const isSaved = await photoAction
		.submit({
			doctype: "Family",
			name: family,
			fieldname: "photo",
			value: fileUrl,
		})
		.then(
			() => true,
			() => false,
		);
	if (!isSaved) return;

	await household.reload();
	toast.success(__("The household photo was changed."));
}
</script>
