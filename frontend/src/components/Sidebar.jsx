import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useThemeStore } from '@/store';
import {
  LayoutDashboard,
  Users,
  FileText,
  Bug,
  Download,
  Settings,
  ChevronLeft,
  ChevronRight,
  Layers,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

const navItems = [
  {
    title: 'Dashboard',
    icon: LayoutDashboard,
    href: '/dashboard',
    description: 'Manage your epics',
  },
  {
    title: 'Personas',
    icon: Users,
    href: '/personas',
    description: 'User personas',
  },
  {
    title: 'Stories',
    icon: FileText,
    href: '/stories',
    description: 'User stories',
  },
  {
    title: 'Bugs',
    icon: Bug,
    href: '/bugs',
    description: 'Bug tracking',
  },
  {
    title: 'Export',
    icon: Download,
    href: '/export',
    description: 'Export data',
  },
];

const bottomNavItems = [
  {
    title: 'Settings',
    icon: Settings,
    href: '/settings',
    description: 'App settings',
  },
];

const Sidebar = ({ collapsed, onToggle }) => {
  const location = useLocation();
  const { theme } = useThemeStore();
  const logoSrc = theme === 'dark' ? '/logo-dark.png' : '/logo-light.png';

  const NavItem = ({ item, isActive }) => {
    const content = (
      <NavLink
        to={item.href}
        className={cn(
          'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
          'hover:bg-accent hover:text-accent-foreground',
          isActive && 'bg-primary/10 text-primary border-l-2 border-primary',
          collapsed && 'justify-center px-2'
        )}
      >
        <item.icon className={cn('h-5 w-5 flex-shrink-0', isActive && 'text-primary')} />
        {!collapsed && (
          <span className={cn('text-sm font-medium', isActive && 'text-primary')}>
            {item.title}
          </span>
        )}
      </NavLink>
    );

    if (collapsed) {
      return (
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger asChild>{content}</TooltipTrigger>
            <TooltipContent side="right" className="flex items-center gap-2">
              {item.title}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      );
    }

    return content;
  };

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-screen bg-card border-r border-border transition-all duration-300',
        collapsed ? 'w-16' : 'w-56'
      )}
    >
      <div className="flex h-full flex-col">
        {/* Logo */}
        <div className={cn(
          'flex items-center h-16 border-b border-border px-4',
          collapsed ? 'justify-center' : 'gap-2'
        )}>
          <img src={logoSrc} alt="JarlPM" className="h-8 w-auto" />
          {!collapsed && (
            <span className="text-lg font-bold text-foreground">JarlPM</span>
          )}
        </div>

        {/* Main Navigation */}
        <nav className="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavItem
              key={item.href}
              item={item}
              isActive={location.pathname === item.href || 
                (item.href === '/dashboard' && location.pathname.startsWith('/epic/'))}
            />
          ))}
        </nav>

        {/* Bottom Navigation */}
        <div className="border-t border-border px-2 py-4 space-y-1">
          {bottomNavItems.map((item) => (
            <NavItem
              key={item.href}
              item={item}
              isActive={location.pathname === item.href}
            />
          ))}
          
          {/* Collapse Toggle */}
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggle}
            className={cn(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg',
              'hover:bg-accent hover:text-accent-foreground',
              collapsed && 'justify-center px-2'
            )}
          >
            {collapsed ? (
              <ChevronRight className="h-5 w-5" />
            ) : (
              <>
                <ChevronLeft className="h-5 w-5" />
                <span className="text-sm font-medium">Collapse</span>
              </>
            )}
          </Button>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
