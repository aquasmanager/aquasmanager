export enum Role {
  consult = 'consult',
  seller = 'seller',
  caretaker = 'caretaker',
  user = 'user',
  manager = 'manager',
  admin = 'admin',
}

export interface RouteMeta {
  minRole?: 'consult' | 'seller' | 'caretaker' | 'user' | 'manager' | 'admin';
  // Fonctionnalité soumise à licence (page inaccessible sans elle)
  feature?: 'bourse' | 'assistant';
}

export interface RegisterForm {
  username: string;
  password: string;
  confirmPassword: string;
  role: Role;
  mustChangePassword: boolean;
}

export interface LoginForm {
  username: string;
  password: string;
}

export interface User {
  id: number;
  username: string;
  role: Role;
}

export interface TokenUser {
  user_id: number;
  username: string;
  role: Role;
}

export interface Login {
  access_token: string;
  token_type: string;
  role: Role;
  must_change_password: boolean;
  language?: 'fr' | 'en';
}

export interface Me {
  user_id: number;
  username: string;
  role: Role;
  must_change_password: boolean;
  language?: 'fr' | 'en';
}

export interface PasswordChange {
  current_password: string;
  new_password: string;
}

export interface ManagedUser {
  id: number;
  username: string;
  role: Role;
  must_change_password: boolean;
}

export interface UserUpdate {
  username?: string;
  role?: Role;
}
