import { Role } from 'src/types/auth';
import { computed, reactive } from 'vue';
import { useAuthStore } from 'src/stores/authStore';
import { useLicenseStore } from 'src/stores/licenseStore';

const ROLE_LEVEL: Record<string, number> = { consult: 1, seller: 1, caretaker: 1, user: 2, manager: 3, admin: 4 };

/**
 * Droits de l'utilisateur connecté, calqués sur ceux de l'API :
 * - edit (utilisateur) : créer, modifier, piloter (modes, marche forcée, lumières...)
 * - manage (manager) : supprimer, gérer contrôleurs et règles, flasher
 * - admin : utilisateurs, notifications, sauvegardes, journal d'activité
 * - frags : gérer les boutures et leurs photos (aussi le rôle « bourse »)
 * - sell : vendre (cessions, certificats, vitrine) : frags + licence « bourse »
 * - bourse / assistant : fonctionnalités ouvertes par la licence (affichage)
 * - care : cocher les tâches, saisir les relevés, noter une consommation du stock
 *   (aussi le rôle « gardiennage », pour la personne qui garde les bacs)
 * Un compte « consultation » ne voit que la lecture. Un compte « bourse »
 * (seller) lit tout mais n'agit que sur les boutures : aucune fausse manip
 * possible sur les bacs quand il est ouvert devant du public.
 */
export function usePermissions() {
  const auth = useAuthStore();
  const license = useLicenseStore();
  const level = computed(() => ROLE_LEVEL[auth.role ?? ''] ?? 0);
  return reactive({
    edit: computed(() => level.value >= ROLE_LEVEL.user!),
    manage: computed(() => level.value >= ROLE_LEVEL.manager!),
    admin: computed(() => level.value >= ROLE_LEVEL.admin!),
    seller: computed(() => auth.role === Role.seller),
    bourse: computed(() => license.bourse),
    assistant: computed(() => license.has('assistant')),
    frags: computed(() => auth.role === Role.seller || level.value >= ROLE_LEVEL.user!),
    sell: computed(() => license.bourse && (auth.role === Role.seller || level.value >= ROLE_LEVEL.user!)),
    caretaker: computed(() => auth.role === Role.caretaker),
    care: computed(() => auth.role === Role.caretaker || level.value >= ROLE_LEVEL.user!),
  });
}
