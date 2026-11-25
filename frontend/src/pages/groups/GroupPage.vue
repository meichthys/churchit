<template>
	<PageHead
		:crumbs="[
			{ label: __('Groups'), route: '/groups' },
			{ label: group.data?.group_name || '' },
		]"
		back="/groups"
	>
		<template
			v-if="group.data?.is_leader && !isPageHidden('group-leader')"
			#actions
		>
			<Button
				variant="subtle"
				icon-left="lucide-user-round-cog"
				:label="__('Lead this group')"
				:route="`/group-leader?group=${group.data.name}`"
			/>
		</template>
	</PageHead>
	<PageBody>
		<LoadState :resource="group" v-slot="{ data }">
			<Masthead
				:title="data.group_name"
				:label="boot.church?.title"
				:dateline="data.meets || undefined"
			/>
			<div class="grid md:grid-cols-12 md:gap-x-12">
				<div class="md:col-span-8">
					<section class="mt-8" aria-labelledby="next-meeting">
						<SectionHead
							id="next-meeting"
							:title="__('Next meeting')"
						/>
						<div
							v-if="data.next_meeting"
							class="flex gap-5 border-t border-outline-gray-1 pt-6 md:gap-7"
						>
							<DateStack
								:date="data.next_meeting.date"
								size="lg"
								accent
							/>
							<div class="min-w-0 pt-1">
								<p class="text-xl-medium text-ink-gray-9">
									{{ data.next_meeting.title }}
								</p>
								<p class="mt-1 text-lg text-ink-gray-6">
									<TimeText
										v-if="data.next_meeting.time"
										:value="data.next_meeting.time"
									/>
									<template
										v-if="
											data.next_meeting.time &&
											data.next_meeting.place
										"
									>
										·
									</template>
									{{ data.next_meeting.place }}
								</p>
								<p class="mt-1 text-lg text-ink-gray-6">
									{{ data.next_meeting.date_label }}
								</p>
							</div>
						</div>
						<EmptyState
							v-else
							:title="__('No meeting is set')"
							:body="
								data.meets
									? __('The group meets {0}.', [data.meets])
									: __(
											'The church office sets the meetings of the group.',
										)
							"
						/>
					</section>

					<section
						v-if="data.description"
						class="mt-10"
						aria-labelledby="about-group"
					>
						<SectionHead
							id="about-group"
							:title="__('About this group')"
						/>
						<p
							class="whitespace-pre-line border-t border-outline-gray-1 pt-4 text-p-lg text-ink-gray-8"
						>
							{{ data.description }}
						</p>
					</section>

					<section
						v-if="data.show_files"
						class="mt-10"
						aria-labelledby="group-files"
					>
						<SectionHead id="group-files" :title="__('Files')" />
						<ul
							v-if="data.files.length"
							class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
						>
							<li v-for="file in data.files" :key="file.name">
								<IndexRow
									:title="file.title"
									:href="file.file_url"
									:facts="[__('Added {0}', [file.added_on])]"
									:fresh="isFresh(file.name)"
								>
									<template #prefix
										><span
											class="lucide-file-text size-6 shrink-0 text-ink-gray-5"
											aria-hidden="true"
									/></template>
								</IndexRow>
							</li>
						</ul>
						<EmptyState
							v-else
							:title="__('No files yet')"
							:body="__('A leader can add a file for the group.')"
						/>
					</section>

					<section
						v-if="data.later_meetings.length"
						class="mt-10"
						aria-labelledby="later-meetings"
					>
						<SectionHead
							id="later-meetings"
							:title="__('Later meetings')"
						/>
						<ul
							class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
						>
							<li
								v-for="meeting in data.later_meetings"
								:key="meeting.name"
								class="flex items-center gap-5 py-4"
							>
								<DateStack :date="meeting.date" />
								<div class="min-w-0">
									<p
										class="text-lg font-medium text-ink-gray-9"
									>
										{{ meeting.title }}
									</p>
									<p
										class="text-lg text-ink-gray-6 md:text-md"
									>
										<TimeText
											v-if="meeting.time"
											:value="meeting.time"
										/>
										<template
											v-if="meeting.time && meeting.place"
										>
											·
										</template>
										{{ meeting.place }}
									</p>
								</div>
							</li>
						</ul>
					</section>
				</div>

				<aside
					class="mt-10 md:col-span-4 md:mt-0 md:border-s md:border-outline-gray-1 md:ps-10"
				>
					<section class="md:mt-8" aria-labelledby="group-people">
						<SectionHead id="group-people" :title="__('People')" />
						<ul
							class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
						>
							<li
								v-for="member in data.members"
								:key="member.name"
								class="flex gap-3 py-3"
							>
								<Avatar
									:label="member.full_name"
									:image="member.photo || undefined"
									size="2xl"
									class="mt-0.5 shrink-0"
								/>
								<div class="min-w-0 flex-1">
									<p
										class="text-lg font-medium text-ink-gray-9"
									>
										{{ member.full_name }}
									</p>
									<p
										v-if="member.is_leader"
										class="text-lg text-ink-gray-6 md:text-md"
									>
										{{ __("Leader") }}
									</p>
									<ul
										v-if="member.email || member.phone"
										class="mt-1 text-lg md:text-md"
									>
										<li v-if="member.email">
											<a
												:href="`mailto:${member.email}`"
												class="inline-flex min-h-11 items-center text-ink-gray-8 underline decoration-outline-gray-3 underline-offset-4 [overflow-wrap:anywhere] md:min-h-0"
												>{{ atBreak(member.email)[0]
												}}<wbr />{{
													atBreak(member.email)[1]
												}}</a
											>
										</li>
										<li v-if="member.phone">
											<a
												:href="`tel:${member.phone}`"
												class="inline-flex min-h-11 items-center text-ink-gray-8 underline decoration-outline-gray-3 underline-offset-4 md:min-h-0"
												><bdi>{{
													member.phone
												}}</bdi></a
											>
										</li>
									</ul>
								</div>
							</li>
						</ul>
						<p
							v-if="
								!data.members.some((member) => member.is_leader)
							"
							class="t-dateline mt-3 text-ink-gray-6"
						>
							{{ __("This group has no leader yet.") }}
						</p>
						<Button
							v-if="
								data.is_leader && !isPageHidden('group-leader')
							"
							class="mt-4 min-h-11 md:hidden"
							variant="subtle"
							size="lg"
							icon-left="lucide-user-round-cog"
							:label="__('Lead this group')"
							:route="`/group-leader?group=${data.name}`"
						/>
					</section>

					<div class="mt-10 border-t border-outline-gray-1 pt-5">
						<template v-if="data.can_leave">
							<Button
								variant="outline"
								theme="red"
								size="lg"
								class="min-h-11"
								icon-left="lucide-log-out"
								:label="__('Leave this group')"
								@click="confirmLeave(data)"
							/>
						</template>
						<p v-else class="text-lg text-ink-gray-6 md:text-md">
							{{
								__(
									"You are the only leader of this group. Ask the church office to name another leader before you leave.",
								)
							}}
						</p>
					</div>
				</aside>
			</div>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Avatar, Button, dialog, toast } from "frappe-ui";
import { useRoute, useRouter } from "vue-router";

import { useFrappeAction, useRead } from "@/api";
import { boot, isPageHidden } from "@/boot";
import DateStack from "@/components/DateStack.vue";
import EmptyState from "@/components/EmptyState.vue";
import IndexRow from "@/components/IndexRow.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import TimeText from "@/components/TimeText.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";

import type { GroupDetail } from "./types";
import { __ } from "@/translate";

const route = useRoute();
const router = useRouter();

const group = useRead<GroupDetail, { group: string }>("groups.get_group", {
	params: () => ({ group: String(route.params.name) }),
	refetch: true,
});
const leave = useFrappeAction<unknown, Record<string, unknown>>(
	"churchit.church_people.group_api.leave_group",
);
const { mark, isFresh } = useFreshInk();

/** An email address in two parts, so that a narrow column breaks it after its @. */
function atBreak(email: string): [string, string] {
	const at = email.lastIndexOf("@") + 1;
	return [email.slice(0, at), email.slice(at)];
}

function confirmLeave(data: GroupDetail) {
	dialog.danger({
		title: __("Leave {0}?", [data.group_name]),
		message: __("A leader can add you again."),
		confirmLabel: __("Leave group"),
		cancelLabel: __("Stay"),
		onConfirm: async () => {
			await leave.submit({ group: data.name });
			toast.success(__("You left {0}.", [data.group_name]));
			router.push("/groups");
		},
	});
}

useLiveRefresh(["groups", "group-files"], async () => {
	const files = new Set(group.data?.files.map((file) => file.name));
	await group.reload();

	const added =
		group.data?.files.filter((file) => !files.has(file.name)) ?? [];
	added.forEach((file) => mark(file.name));
});
</script>
