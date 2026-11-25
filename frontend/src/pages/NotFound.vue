<template>
	<div
		class="mx-auto flex max-w-md flex-col items-center gap-3 px-6 py-24 text-center"
	>
		<span
			class="lucide-compass size-8 text-ink-gray-5"
			aria-hidden="true"
		/>
		<h1 class="text-xl-semibold text-ink-gray-9">
			{{ __("This page is not here") }}
		</h1>
		<p class="text-p-base text-ink-gray-6">
			{{ __("It may have moved, or the church may have turned it off.") }}
		</p>
		<Button :label="__('Go to Home')" route="/" />
	</div>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
</script>
