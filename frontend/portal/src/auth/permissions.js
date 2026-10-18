export function hasPermission(user, permission) {
  return !!user && ((user.is_staff && user.is_superuser) || user.permissions?.includes(permission));
}

export function workspaceRoles(user) {
  if (!user) return [];
  if (user.role === 'hod' && user.is_staff && user.is_superuser) return ['hod'];
  if (user.role === 'staff' && user.is_staff) {
    return user.adviser_levels?.length ? ['staff', 'adviser'] : ['staff'];
  }
  return user.role === 'student' && !user.is_staff ? ['student'] : [];
}

export function workspaceHome(user) {
  return `/portal/${workspaceRoles(user)[0] || 'student'}/dashboard`;
}
