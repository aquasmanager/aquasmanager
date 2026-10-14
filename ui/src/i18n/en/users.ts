import type fr from '../fr/users';

// Account management (administrators)
const users: typeof fr = {
  title: 'Users',
  subtitle: 'Accounts and access rights to the application',
  create: 'Create a user',
  you: 'you',
  mustChange: 'Must change their password at next sign-in',
  resetPassword: 'Reset the password',
  columns: { username: 'User', role: 'Role' },
  createSubmit: 'Create',
  username: 'Username *',
  password: 'Password *',
  confirmPassword: 'Confirm the password *',
  role: 'Role *',
  forceChangeFirst: 'Require a password change at first sign-in',
  editTitle: 'Edit the user',
  newPassword: 'New password *',
  reset: 'Reset',
  forceChangeNext: 'Require a change at next sign-in',
  errors: {
    usernameMin: '4 characters minimum',
    passwordMin: '8 characters minimum',
    confirm: 'Confirm the password',
    role: 'Role required',
    mismatch: 'Passwords do not match',
  },
  notify: {
    created: 'User {name} created.',
    createFailed: 'Unable to create the user.',
    updated: 'User updated.',
    updateFailed: 'Update failed.',
    checkPassword: 'Check the new password (8 characters minimum, both identical).',
    reset: 'Password reset.',
    resetFailed: 'Reset failed.',
  },
  item: 'the user {name}',
  deleteMessage: 'Delete the user {name}? They will be signed out immediately. This cannot be undone.',
};

export default users;
