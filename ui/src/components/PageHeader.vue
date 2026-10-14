<!-- En-tête commun : titre de page (ou de section d'onglet), sous-titre et actions à droite -->
<template>
  <div class="page-header row items-center justify-between q-col-gutter-sm" :class="section ? 'q-mb-md' : 'q-mb-lg'">
    <div class="page-header__title col-12 col-sm row items-center no-wrap">
      <q-avatar v-if="icon && !section && $q.screen.gt.xs" size="44px" color="blue-1" text-color="primary" :icon="icon" class="q-mr-md" />
      <div class="col">
        <!-- Mobile : le titre est déjà dans la barre du haut (page) ou le sélecteur de section (onglet) -->
        <div v-if="$q.screen.gt.sm" class="text-weight-bold" :class="section ? 'text-h6' : 'text-h5'">{{ title }}</div>
        <div v-if="subtitle" class="text-grey-7" :class="$q.screen.gt.xs ? 'text-body2' : 'text-caption'">{{ subtitle }}</div>
      </div>
    </div>
    <div v-if="$slots.actions" class="page-header__side col-12 col-sm-auto">
      <div class="page-header__actions row items-center justify-end gap-sm">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string;
  subtitle?: string | undefined;
  icon?: string | undefined;
  // En-tête d'un onglet (titre plus petit, sans icône)
  section?: boolean | undefined;
}>();
</script>

<style scoped>
/*
 * Tablette et ordinateur : le titre garde au moins 280 px ; quand les boutons
 * ne tiennent plus à côté, ils passent à la ligne (alignés à droite).
 */
@media (min-width: 600px) {
  .page-header__title {
    flex: 1 1 280px;
    min-width: 280px;
  }

  .page-header__side {
    flex: 0 1 auto;
    max-width: 100%;
  }

  .page-header__actions {
    flex-wrap: wrap;
  }
}

/*
 * Téléphone : recherche sur toute la largeur, boutons deux par ligne quand
 * leur texte tient, sinon un par ligne (le dernier seul prend toute la largeur).
 */
@media (max-width: 599.98px) {
  .page-header__actions {
    justify-content: stretch;
  }

  .page-header__actions > :deep(.q-field) {
    flex: 1 1 100%;
    width: 100% !important;
    max-width: none !important;
  }

  /* Au moins une demi-ligne, la largeur du texte sinon : deux boutons trop longs pour
     tenir côte à côte passent l'un sous l'autre au lieu d'être coupés (« Ajouter un é… ») */
  .page-header__actions > :deep(.q-btn),
  .page-header__actions > :deep(.q-btn-dropdown) {
    flex: 1 1 auto;
    min-width: calc(50% - 4px);
    max-width: 100%;
  }

  .page-header__actions > :deep(.q-btn .q-btn__content) {
    flex-wrap: nowrap;
  }

  .page-header__actions > :deep(.q-btn .block) {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}
</style>
