import { onUnmounted, ref, watch, type Ref } from 'vue';

// Titre affiché dans l'en-tête mobile quand une page a un titre dynamique
// (ex : nom de l'aquarium) ; sinon l'en-tête utilise meta.title de la route.
const dynamicTitle = ref<string | null>(null);
// Page qui a posé le titre : une page qui se ferme n'efface pas celui de la suivante
let owner: symbol | null = null;

export function useDynamicTitle() {
  return dynamicTitle;
}

export function usePageTitle(title: Ref<string | null | undefined>) {
  const me = Symbol('page-title');
  watch(
    title,
    (value) => {
      owner = me;
      dynamicTitle.value = value ?? null;
    },
    { immediate: true },
  );
  onUnmounted(() => {
    if (owner === me) {
      owner = null;
      dynamicTitle.value = null;
    }
  });
}
