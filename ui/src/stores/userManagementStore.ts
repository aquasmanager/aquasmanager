import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import type { ManagedUser, UserUpdate } from 'src/types/auth';

export const useUserManagementStore = defineStore('userManagement', () => {
  const users = ref<ManagedUser[]>([]);
  const loading = ref(false);

  async function fetchUsers() {
    loading.value = true;
    try {
      const { data } = await axios.get<ManagedUser[]>('/users/');
      users.value = data;
    } finally {
      loading.value = false;
    }
  }

  async function updateUser(id: number, payload: UserUpdate) {
    const { data } = await axios.patch<ManagedUser>(`/users/${id}`, payload);
    const index = users.value.findIndex((u) => u.id === id);
    if (index !== -1) {
      users.value[index] = data;
    }
    return data;
  }

  async function resetPassword(id: number, newPassword: string, mustChangePassword = true) {
    await axios.post(`/users/${id}/reset-password`, {
      new_password: newPassword,
      must_change_password: mustChangePassword,
    });
    await fetchUsers();
  }

  async function deleteUser(id: number) {
    await axios.delete(`/users/${id}`);
    users.value = users.value.filter((u) => u.id !== id);
  }

  return { users, loading, fetchUsers, updateUser, resetPassword, deleteUser };
});
