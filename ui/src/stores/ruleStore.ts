import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import { type Rule, type RuleCreate } from '../types/rule';
import { API_URL } from 'src/utils/runtimeConfig';

const apiUrl = API_URL;

export const useRuleStore = defineStore(
  'rule',
  () => {
    const rules = ref<Rule[]>([]);
    const total = ref<number>();

    async function fetch() {
      const res = await axios.get<Rule[] | { rules: Rule[]; total?: number }>(`${apiUrl}/rules`);
      // Gère à la fois le cas où l'API renvoie directement un tableau ou un objet paginé
      if (Array.isArray(res.data)) {
        rules.value = res.data;
        total.value = res.data.length;
      } else {
        rules.value = res.data.rules;
        total.value = res.data.total;
      }
    }

    async function add(data: RuleCreate): Promise<Rule> {
      const res = await axios.post<Rule>(`${apiUrl}/rules/`, data);
      rules.value.push(res.data);
      if (total.value !== undefined) total.value++;
      return res.data;
    }

    async function update(id: number, data: Partial<RuleCreate>): Promise<Rule> {
      const res = await axios.patch<Rule>(`${apiUrl}/rules/${id}`, data);
      const i = rules.value.findIndex((rule) => rule.id === id);
      if (i !== -1) rules.value[i] = res.data;
      return res.data;
    }

    async function remove(id: number) {
      await axios.delete(`${apiUrl}/rules/${id}`);
      rules.value = rules.value.filter((rule) => rule.id !== id);
      if (total.value !== undefined && total.value > 0) total.value--;
    }

    function getById(id: number): Rule | undefined {
      return rules.value.find((rule) => Number(rule.id) === id);
    }

    function getByEquipmentId(equipment_id: number): Rule[] {
      return rules.value.filter((rule) => Number(rule.equipment_id) === Number(equipment_id));
    }

    return {
      rules,
      total,
      fetch,
      add,
      update,
      remove,
      getById,
      getByEquipmentId,
    };
  },
  {
    persist: {
      key: 'rules-store',
      storage: localStorage,
    },
  },
);
