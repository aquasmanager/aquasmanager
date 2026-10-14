<!-- Champ texte standard (outlined + dense) ; icon = icône à gauche (ex. search) -->
<template>
  <q-input
    outlined
    dense
    v-bind="$attrs"
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <template v-if="icon" #prepend>
      <q-icon :name="icon" size="20px" color="grey-6" />
    </template>
    <template v-for="(_, slotName) in $slots" #[slotName]="scope">
      <slot :name="slotName" v-bind="scope || {}" />
    </template>
  </q-input>
</template>

<script setup lang="ts">
import { type PropType } from 'vue';

defineOptions({
  name: 'AppInput',
  inheritAttrs: false
});

defineProps({
  modelValue: {
    type: [String, Number, null] as PropType<string | number | null>,
    default: ''
  },
  icon: {
    type: String,
    default: undefined
  }
});

defineEmits(['update:modelValue']);
</script>
