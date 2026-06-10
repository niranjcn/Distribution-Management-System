export const ROLES = {
  SUPER_ADMIN: 'super_admin',
  MD_DIRECTOR: 'md_director',
  MANAGER: 'manager',
  PDIC_STAFF: 'pdic_staff',
  SUB_DISTRIBUTION_MANAGER: 'sub_distribution_manager',
  SUB_DISTRIBUTOR: 'sub_distributor',
  CLUSTER: 'cluster',
  OPERATOR: 'operator',
};

export const normalizeRole = (role) => {
  if (!role) return '';
  const value = String(role).trim().toLowerCase();
  if (value === 'super_admin') return ROLES.SUPER_ADMIN;
  if (value === 'pdic_staff') return ROLES.PDIC_STAFF;
  if (value === 'staff') return ROLES.PDIC_STAFF;
  return value;
};

export const ROLE_LABELS = {
  [ROLES.SUPER_ADMIN]: 'Super Admin',
  [ROLES.MD_DIRECTOR]: 'MD/Director',
  [ROLES.MANAGER]: 'Manager',
  [ROLES.PDIC_STAFF]: 'PDIC Staff',
  [ROLES.SUB_DISTRIBUTION_MANAGER]: 'Sub Distribution MD/Manager',
  [ROLES.SUB_DISTRIBUTOR]: 'Sub Distributor',
  [ROLES.CLUSTER]: 'Cluster',
  [ROLES.OPERATOR]: 'Operator',
};

export const isForcedCredentialUpdateRequired = (user) =>
  Boolean(user?.force_email_change || user?.force_password_change);

