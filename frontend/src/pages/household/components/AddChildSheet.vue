<template>
	<FormSheet
		v-model:open="open"
		:title="__('Add a child')"
		:description="__('Your child joins your household.')"
	>
		<form
			class="space-y-4 [&_input:not([type=checkbox])]:min-h-11 [&_select]:min-h-11 [&_input]:text-lg"
			@submit.prevent="submit"
		>
			<FormControl
				size="lg"
				v-model="firstName"
				:label="__('First name')"
				required
				maxlength="140"
				autocomplete="off"
			/>
			<FormControl
				size="lg"
				v-model="lastName"
				:label="__('Last name')"
				maxlength="140"
				autocomplete="off"
			/>
			<FormControl
				size="lg"
				v-model="birthday"
				type="date"
				:placeholder="__('Choose a date')"
				:label="__('Birthday')"
				:max="today"
				required
				:description="
					__('The church office adds anyone {0} or older.', [
						adultAge,
					])
				"
			/>
			<FormControl
				size="lg"
				v-model="gender"
				type="select"
				:label="__('Gender')"
				:options="[
					{ label: __('Female'), value: 'Female' },
					{ label: __('Male'), value: 'Male' },
				]"
				:placeholder="__('Choose one')"
				required
			/>
			<button
				type="submit"
				class="hidden"
				tabindex="-1"
				aria-hidden="true"
			/>
		</form>
		<template #actions>
			<Button
				variant="outline"
				size="lg"
				:label="__('Cancel')"
				@click="open = false"
			/>
			<Button
				variant="solid"
				size="lg"
				:label="__('Add child')"
				:loading="action.loading"
				:disabled="!canSubmit"
				@click="submit"
			/>
		</template>
	</FormSheet>
</template>

<script setup lang="ts">
import { Button, FormControl, toast } from "frappe-ui";
import { computed, ref, watch } from "vue";

import { useFrappeAction } from "@/api";
import FormSheet from "@/components/FormSheet.vue";
import { __ } from "@/translate";

const props = defineProps<{
	lastName: string | null;
	adultAge: number;
	today: string;
	familyTitle?: string | null;
}>();
const emit = defineEmits<{ added: [name: string] }>();
const open = defineModel<boolean>("open", { default: false });

const firstName = ref("");
const lastName = ref("");
const birthday = ref("");
const gender = ref<string | null>(null);
const action = useFrappeAction<string, Record<string, any>>(
	"churchit.church_people.member_access.add_household_child",
);

const canSubmit = computed(() =>
	Boolean(firstName.value.trim() && birthday.value && gender.value),
);

watch(open, (isOpen) => {
	if (!isOpen) return;
	firstName.value = "";
	lastName.value = props.lastName || "";
	birthday.value = "";
	gender.value = null;
});

async function submit() {
	if (!canSubmit.value) return;
	const name = await action
		.submit({
			first_name: firstName.value,
			last_name: lastName.value,
			birthday: birthday.value,
			gender: gender.value,
		})
		.catch(() => null);
	if (!name) return;
	toast.success(
		__("{0} was added to your household.", [firstName.value.trim()]),
	);
	open.value = false;
	emit("added", name as string);
}
</script>
