/**
 * Équipements pilotés par des règles (niveau, seuil, plage horaire) : seul
 * cas où le mode auto / manuel a un effet. En AUTO les règles agissent ; en
 * MANUEL elles l'ignorent (sauf les règles de sécurité). Un équipement
 * qu'aucune règle ne pilote s'allume et se coupe directement, sans mode.
 */
import { computed, onMounted } from 'vue';
import { useRuleStore } from 'src/stores/ruleStore';
import { useEquipmentGroupStore } from 'src/stores/equipmentGroupStore';

export function useEquipmentAutomation() {
  const ruleStore = useRuleStore();
  const groupStore = useEquipmentGroupStore();

  onMounted(() => {
    // Listes partagées : chargées une fois (sans bloquer l'affichage)
    if (!ruleStore.rules.length) void ruleStore.fetch().catch(() => undefined);
    if (!groupStore.groups.length) void groupStore.fetch().catch(() => undefined);
  });

  const automatedIds = computed(() => {
    const ids = new Set<number>();
    for (const rule of ruleStore.rules) {
      if (!rule.is_active || rule.is_safety_lock || (rule.action !== 'ON' && rule.action !== 'OFF')) continue;
      if (rule.equipment_id) ids.add(rule.equipment_id);
      if (rule.group_id) {
        const group = groupStore.groups.find((g) => g.id === rule.group_id);
        for (const eq of group?.equipments ?? []) ids.add(eq.id);
      }
    }
    return ids;
  });

  function isAutomated(equipmentId: number): boolean {
    return automatedIds.value.has(equipmentId);
  }

  return { isAutomated };
}
