<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
    <q-card style="width: 480px; max-width: 90vw; border-radius: 12px; overflow: hidden" v-if="invertebrate">
      <div class="relative-position">
        <q-img :src="mainPhotoUrl(PhotoEntityType.invertebrates, invertebrate.id)" ratio="16/9">
          <div class="absolute-full bg-gradient-overlay flex items-end q-pa-md">
            <div class="full-width">
              <div class="text-h5 text-weight-bold text-white text-shadow">{{ invertebrate.name }}</div>
              <div class="text-subtitle2 text-italic text-white text-shadow">{{ invertebrate.scientific_name }}</div>
            </div>
          </div>
        </q-img>
        <q-btn icon="close" flat round dense color="white" class="absolute-top-right q-ma-sm" v-close-popup />
      </div>

      <q-card-section>
        <div class="row q-col-gutter-md">
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="category" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.familyLabel') }}</div>
                <div class="text-weight-medium">{{ invertebrate.family || '—' }}</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="public" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.originLabel') }}</div>
                <div class="text-weight-medium">{{ invertebrate.origin || '—' }}</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="event" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.acquiredOnLabel') }}</div>
                <div class="text-weight-medium">{{ formattedDate }}</div>
              </div>
            </div>
          </div>
        </div>
      </q-card-section>

      <q-separator />
      <q-card-section>
        <SpecimenDocuments entity-type="invertebrates" :entity-id="invertebrate.id" />
      </q-card-section>

      <q-separator />

      <q-card-actions align="right">
        <q-btn flat :label="t('common.close')" color="grey-8" v-close-popup />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import { computed } from 'vue';
import { formatDate } from 'src/utils/format';
import SpecimenDocuments from 'src/components/SpecimenDocuments.vue';
import type { Invertebrate } from 'src/types/invertebrate';
import { PhotoEntityType } from 'src/types/photo';
import { mainPhotoUrl } from 'src/stores/photoStore';

const { t } = useI18n();

const props = defineProps<{
  modelValue: boolean;
  invertebrate: Invertebrate | null;
}>();

defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
}>();

const formattedDate = computed(() => formatDate(props.invertebrate?.date_acquisition, '—'));
</script>

<style scoped>
.bg-gradient-overlay {
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0) 0%, rgba(0, 0, 0, 0.75) 100%);
}
.text-shadow {
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.6);
}
</style>
