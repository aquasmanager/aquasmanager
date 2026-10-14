/**
 * Spécimen ciblé par l'adresse (?specimen=<id>), par exemple depuis un document
 * d'achat : la liste n'affiche que lui, jusqu'à ce que l'utilisateur retire le filtre.
 */
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

export function useSpecimenFocus() {
  const route = useRoute();
  const router = useRouter();
  const focusId = computed(() => {
    const raw = Number(route.query.specimen);
    return Number.isInteger(raw) && raw > 0 ? raw : null;
  });

  function clearFocus() {
    const query = { ...route.query };
    delete query.specimen;
    void router.replace({ query });
  }

  function focused<T extends { id: number }>(rows: T[]): T[] | null {
    return focusId.value === null ? null : rows.filter((row) => row.id === focusId.value);
  }

  return { focusId, clearFocus, focused };
}
