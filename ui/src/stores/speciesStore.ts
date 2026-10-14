import { defineStore } from 'pinia';
import axios from 'axios';
import type { SpeciesByKind, SpeciesInputByKind, SpeciesKind } from 'src/types/species';

type SpeciesOf<K extends SpeciesKind> = SpeciesByKind[K];
type InputOf<K extends SpeciesKind> = SpeciesInputByKind[K];

export const useSpeciesStore = defineStore('species', () => {
  async function search<K extends SpeciesKind>(
    kind: K,
    q?: string,
    aquariumId?: number | null,
    compatibleOnly = false,
  ): Promise<SpeciesOf<K>[]> {
    const { data } = await axios.get<SpeciesOf<K>[]>(`/species/${kind}`, {
      params: {
        ...(q ? { q } : {}),
        ...(aquariumId ? { aquarium_id: aquariumId, compatible_only: compatibleOnly } : {}),
      },
    });
    return data;
  }

  async function create<K extends SpeciesKind>(kind: K, payload: InputOf<K>): Promise<SpeciesOf<K>> {
    const { data } = await axios.post<SpeciesOf<K>>(`/species/${kind}`, payload);
    return data;
  }

  async function update<K extends SpeciesKind>(kind: K, id: number, payload: Partial<InputOf<K>>): Promise<SpeciesOf<K>> {
    const { data } = await axios.patch<SpeciesOf<K>>(`/species/${kind}/${id}`, payload);
    return data;
  }

  async function remove(kind: SpeciesKind, id: number) {
    await axios.delete(`/species/${kind}/${id}`);
  }

  return { search, create, update, remove };
});
