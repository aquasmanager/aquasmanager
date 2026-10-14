<!-- Liste déroulante standard (outlined + dense, valeur émise directement) -->
<template>
  <q-select
    outlined
    dense
    emit-value
    map-options
    v-bind="$attrs"
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <template v-for="(_, slotName) in $slots" #[slotName]="scope">
      <slot :name="slotName" v-bind="scope || {}" />
    </template>
  </q-select>
</template>

<script setup lang="ts">
import { type PropType } from 'vue';

defineOptions({
  name: 'AppSelect',
  inheritAttrs: false
});

defineProps({
  modelValue: {
    type: [String, Number, Object, Array] as PropType<string | number | object | null>,
    default: null
  }
});

defineEmits(['update:modelValue']);
</script>
