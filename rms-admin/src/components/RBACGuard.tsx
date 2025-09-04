import { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

// Define role types
type Role = 'Manager' | 'Cashier' | 'Kitchen' | 'Host';
type Permission = 'read' | 'write' | 'delete' | 'admin';

interface User {
  id: string;
  roles: Role[];
  locationId?: string;
  permissions?: Permission[];
}

interface RouteRoleMapping {
  roles: Role[];
  locationScoped?: boolean;
  permissions?: Permission[];
}

// Route-to-role mappings with location scoping
const ROUTE_ROLE_MAPPINGS: Record<string, RouteRoleMapping> = {
  '/admin/dashboard': {
    roles: ['Manager', 'Cashier', 'Kitchen', 'Host'],
    locationScoped: true
  },
  '/admin/orders': {
    roles: ['Manager', 'Cashier', 'Kitchen'],
    locationScoped: true,
    permissions: ['read', 'write']
  },
  '/admin/payments': {
    roles: ['Manager'],
    locationScoped: true,
    permissions: ['read', 'write', 'admin']
  },
  '/admin/reservations': {
    roles: ['Manager', 'Host'],
    locationScoped: true
  },
  '/admin/menu': {
    roles: ['Manager'],
    locationScoped: false
  },
  '/admin/menu/items': {
    roles: ['Manager'],
    locationScoped: false
  },
  '/admin/menu/modifiers': {
    roles: ['Manager', 'Kitchen'],
    locationScoped: true,
    permissions: ['read', 'write']
  },
  '/admin/menu/stock': {
    roles: ['Manager', 'Kitchen'],
    locationScoped: true,
    permissions: ['read', 'write']
  },
  '/admin/menu/availability': {
    roles: ['Manager', 'Kitchen'],
    locationScoped: true,
    permissions: ['read', 'write']
  },
  '/admin/coupons': {
    roles: ['Manager', 'Cashier'],
    locationScoped: true
  },
  '/admin/loyalty': {
    roles: ['Manager'],
    locationScoped: true
  },
  '/admin/reports': {
    roles: ['Manager'],
    locationScoped: false
  },
  '/admin/reports/daily-sales': {
    roles: ['Manager', 'Cashier'],
    locationScoped: false
  },
  '/admin/reports/shift-close': {
    roles: ['Manager', 'Cashier'],
    locationScoped: false
  },
  '/admin/reports/menu-performance': {
    roles: ['Manager'],
    locationScoped: true
  },
  '/admin/reports/audit-logs': {
    roles: ['Manager'],
    locationScoped: false,
    permissions: ['admin']
  },
  '/admin/settings': {
    roles: ['Manager'],
    locationScoped: false
  },
  '/admin/users': {
    roles: ['Manager'],
    locationScoped: false
  }
};

// Mock user data - in real app, this would come from auth context or JWT decode
const mockUser: User = {
  id: '1',
  roles: ['Manager'],
  locationId: 'loc-1',
  permissions: ['read', 'write', 'delete', 'admin']
};

// Check if user has required role
function hasRole(user: User, requiredRoles: Role[]): boolean {
  return requiredRoles.some(role => user.roles.includes(role));
}

// Check if user has required permission
function hasPermission(user: User, requiredPermissions: Permission[]): boolean {
  if (!requiredPermissions || requiredPermissions.length === 0) return true;
  if (!user.permissions) return false;
  return requiredPermissions.some(permission => user.permissions!.includes(permission));
}

// Check location scoping
function hasLocationAccess(user: User, locationScoped: boolean, targetLocationId?: string): boolean {
  if (!locationScoped) return true;
  if (!targetLocationId) return true;
  return user.locationId === targetLocationId;
}

// Main access check function
function checkAccess(user: User, mapping: RouteRoleMapping, targetLocationId?: string): boolean {
  const roleCheck = hasRole(user, mapping.roles);
  const permissionCheck = hasPermission(user, mapping.permissions || []);
  const locationCheck = hasLocationAccess(user, mapping.locationScoped || false, targetLocationId);
  
  return roleCheck && permissionCheck && locationCheck;
}

export function checkRouteAccess(pathname: string, user: User = mockUser): boolean {
  const mapping = ROUTE_ROLE_MAPPINGS[pathname];
  if (!mapping) return true; // Allow access to unmapped routes
  
  return checkAccess(user, mapping);
}

// RBAC Guard Component
interface RBACGuardProps {
  children: ReactNode;
  fallback?: ReactNode;
}

export function RBACGuard({ children, fallback = <div>Access Denied</div> }: RBACGuardProps) {
  const location = useLocation();
  const { isAuthenticated } = useAuth();
  
  if (!isAuthenticated) {
    return <>{fallback}</>;
  }
  
  const hasAccess = checkRouteAccess(location.pathname);
  
  return hasAccess ? <>{children}</> : <>{fallback}</>;
}

// Example usage in App.tsx:
// <RBACRoute path="/menu/modifiers" roles={['Manager', 'Kitchen']} component={Modifiers} />
// <RBACRoute path="/payments" roles={['Manager']} component={Payments} />
// <RBACRoute path="/reports" roles={['Manager']} component={Reports} />

export default RBACGuard;