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
  Gauge,
  Calendar,
  FileEdit,
  LayoutGrid,
  Users2,
  Sparkles,
  Library,
  Target,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Separator } from '@/components/ui/separator';

const navSections = [
  {
    title: 'Planning',
    items: [
      {
        title: 'Dashboard',
        icon: LayoutDashboard,
        href: '/dashboard',
        description: 'Manage your epics',
      },
      {
        title: 'Initiatives',
        icon: Library,
        href: '/initiatives',
        description: 'Initiative library',
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
    ],
  },
  {
    title: 'Analysis',
    items: [
      {
        title: 'Personas',
        icon: Users,
        href: '/personas',
        description: 'User personas',
      },
      {
        title: 'Lean Canvas',
        icon: LayoutGrid,
        href: '/lean-canvas',
        description: 'Business model',
      },
      {
        title: 'Scoring',
        icon: Gauge,
        href: '/scoring',
        description: 'MoSCoW & RICE',
      },
    ],
  },
  {
    title: 'Delivery',
    items: [
      {
        title: 'Delivery Reality',
        icon: Target,
        href: '/delivery-reality',
        description: 'Capacity & scope',
      },
      {
        title: 'Sprints',
        icon: Calendar,
        href: '/sprints',
        description: 'Sprint planning',
      },
      {
        title: 'Poker',
        icon: Users2,
        href: '/poker',
        description: 'Story estimation',
      },
      {
        title: 'PRD',
        icon: FileEdit,
        href: '/prd',
        description: 'Generate PRD',
      },
      {
        title: 'Export',
        icon: Download,
        href: '/export',
        description: 'Export data',
      },
    ],
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
          'flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200',
          'hover:bg-accent hover:text-accent-foreground',
          isActive && 'bg-primary/10 text-primary',
          collapsed && 'justify-center px-2'
        )}
      >
        <item.icon className={cn('h-4 w-4 flex-shrink-0', isActive && 'text-primary')} />
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

  const isItemActive = (href) => {
    if (href === '/dashboard') {
      return location.pathname === '/dashboard' || location.pathname.startsWith('/epic/');
    }
    return location.pathname === href || location.pathname.startsWith(href + '/');
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

        {/* New Initiative Button */}
        <div className={cn('px-2 py-4', collapsed && 'px-1')}>
          <NavLink to="/new">
            <Button 
              className={cn(
                'w-full bg-primary hover:bg-primary/90 text-primary-foreground',
                collapsed ? 'px-2' : 'gap-2'
              )}
              data-testid="new-initiative-button"
            >
              <Sparkles className="h-4 w-4" />
              {!collapsed && 'New Initiative'}
            </Button>
          </NavLink>
        </div>

        {/* Main Navigation */}
        <nav className="flex-1 px-2 py-4 overflow-y-auto">
          {navSections.map((section, sectionIndex) => (
            <div key={section.title} className="mb-4">
              {!collapsed && (
                <h3 className="px-3 mb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  {section.title}
                </h3>
              )}
              <div className="space-y-1">
                {section.items.map((item) => (
                  <NavItem
                    key={item.href}
                    item={item}
                    isActive={isItemActive(item.href)}
                  />
                ))}
              </div>
              {sectionIndex < navSections.length - 1 && collapsed && (
                <Separator className="my-3" />
              )}
            </div>
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
              'w-full flex items-center gap-3 px-3 py-2 rounded-lg',
              'hover:bg-accent hover:text-accent-foreground',
              collapsed && 'justify-center px-2'
            )}
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4" />
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
