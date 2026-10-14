<!-- Carte avec photo commune aux aquariums et aux vivants (poissons, coraux, plantes...) -->
<template>
  <q-card flat bordered class="photo-card hover-card column no-wrap full-height overflow-hidden">
    <q-img :src="photo" :ratio="16 / 10" class="cursor-pointer" @click="emit('open')">
      <div class="absolute-top photo-card__overlay row items-start justify-between no-wrap q-pa-sm">
        <div class="text-subtitle1 text-weight-bold ellipsis q-pr-sm">{{ title }}</div>
        <q-badge v-if="badge" :color="badge.color" :label="badge.label" class="text-weight-bold q-px-sm q-py-xs" />
      </div>
    </q-img>

    <q-card-section class="col q-py-sm q-px-md">
      <div class="row items-center justify-between no-wrap">
        <div class="col ellipsis">
          <div v-if="subtitle" class="text-caption text-italic text-grey-9 ellipsis">{{ subtitle }}</div>
          <div v-if="caption" class="text-caption text-grey-7 ellipsis">{{ caption }}</div>
        </div>
        <div v-if="meta" class="row items-center no-wrap text-caption text-weight-bold text-grey-8 q-ml-sm">
          <q-icon :name="meta.icon" :color="meta.color ?? 'primary'" size="16px" class="q-mr-xs" />
          {{ meta.text }}
        </div>
      </div>
    </q-card-section>

    <q-separator />

    <q-card-actions class="q-px-sm q-py-xs">
      <q-btn flat dense color="primary" :label="openLabel ?? t('actions.details')" icon-right="chevron_right" class="text-weight-bold q-px-sm" @click="emit('open')" />
      <q-space />
      <slot name="actions" />
      <q-btn flat round dense size="sm" color="grey-7" icon="photo_library" @click="emit('gallery')">
        <q-tooltip>{{ t('actions.photos') }}</q-tooltip>
      </q-btn>
      <q-btn v-if="can.edit" flat round dense size="sm" color="grey-7" icon="edit" @click="emit('edit')">
        <q-tooltip>{{ t('actions.edit') }}</q-tooltip>
      </q-btn>
      <q-btn v-if="can.manage" flat round dense size="sm" color="negative" icon="delete" @click="emit('remove')">
        <q-tooltip>{{ t('actions.delete') }}</q-tooltip>
      </q-btn>
    </q-card-actions>
  </q-card>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import { usePermissions } from 'src/composables/usePermissions';

const { t } = useI18n();
const can = usePermissions();

defineProps<{
    photo: string;
    title: string;
    badge?: { label: string; color: string } | undefined;
    subtitle?: string | null | undefined;
    caption?: string | null | undefined;
    meta?: { icon: string; text: string; color?: string } | undefined;
    openLabel?: string | undefined;
}>();

const emit = defineEmits<{ open: []; gallery: []; edit: []; remove: [] }>();
</script>

<style scoped>
.photo-card__overlay {
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.6) 0%, rgba(0, 0, 0, 0) 100%);
  color: #fff;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.6);
}
</style>
