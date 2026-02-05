import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { initiativeAPI } from '@/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { toast } from 'sonner';
import {
  Search,
  MoreHorizontal,
  Eye,
  Copy,
  Archive,
  Trash2,
  Sparkles,
  RefreshCw,
  FolderOpen,
  FileText,
  CheckCircle2,
  Clock,
  Edit3,
  ArchiveRestore,
} from 'lucide-react';

const STATUS_CONFIG = {
  draft: { 
    label: 'Draft', 
    color: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
    icon: Edit3
  },
  active: { 
    label: 'Active', 
    color: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
    icon: Clock
  },
  completed: { 
    label: 'Completed', 
    color: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
    icon: CheckCircle2
  },
  archived: { 
    label: 'Archived', 
    color: 'bg-muted text-muted-foreground border-muted',
    icon: Archive
  },
};

const Initiatives = () => {
  const navigate = useNavigate();
  const [initiatives, setInitiatives] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [summary, setSummary] = useState(null);
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 20,
    total: 0,
    hasMore: false,
  });
  
  // Delete confirmation dialog
  const [deleteDialog, setDeleteDialog] = useState({ open: false, initiative: null });

  const fetchInitiatives = async () => {
    try {
      setLoading(true);
      const params = {
        page: pagination.page,
        page_size: pagination.pageSize,
        sort_by: 'updated_at',
        sort_order: 'desc',
      };
      
      if (statusFilter && statusFilter !== 'all') {
        params.status = statusFilter;
      }
      
      if (searchQuery) {
        params.search = searchQuery;
      }
      
      const response = await initiativeAPI.list(params);
      setInitiatives(response.data.initiatives);
      setPagination(prev => ({
        ...prev,
        total: response.data.total,
        hasMore: response.data.has_more,
      }));
    } catch (error) {
      console.error('Failed to fetch initiatives:', error);
      toast.error('Failed to load initiatives');
    } finally {
      setLoading(false);
    }
  };

  const fetchSummary = async () => {
    try {
      const response = await initiativeAPI.getSummary();
      setSummary(response.data);
    } catch (error) {
      console.error('Failed to fetch summary:', error);
    }
  };

  useEffect(() => {
    fetchInitiatives();
    fetchSummary();
  }, [statusFilter, pagination.page]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (pagination.page === 1) {
        fetchInitiatives();
      } else {
        setPagination(prev => ({ ...prev, page: 1 }));
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleView = (epicId) => {
    navigate(`/epic/${epicId}`);
  };

  const handleDuplicate = async (initiative) => {
    try {
      const response = await initiativeAPI.duplicate(initiative.epic_id);
      toast.success(`Created "${response.data.title}"`);
      fetchInitiatives();
      fetchSummary();
    } catch (error) {
      console.error('Failed to duplicate:', error);
      toast.error('Failed to duplicate initiative');
    }
  };

  const handleArchive = async (initiative) => {
    try {
      await initiativeAPI.archive(initiative.epic_id);
      toast.success('Initiative archived');
      fetchInitiatives();
      fetchSummary();
    } catch (error) {
      console.error('Failed to archive:', error);
      toast.error('Failed to archive initiative');
    }
  };

  const handleUnarchive = async (initiative) => {
    try {
      await initiativeAPI.unarchive(initiative.epic_id);
      toast.success('Initiative restored');
      fetchInitiatives();
      fetchSummary();
    } catch (error) {
      console.error('Failed to restore:', error);
      toast.error('Failed to restore initiative');
    }
  };

  const handleDelete = async () => {
    if (!deleteDialog.initiative) return;
    
    try {
      await initiativeAPI.delete(deleteDialog.initiative.epic_id);
      toast.success('Initiative deleted');
      setDeleteDialog({ open: false, initiative: null });
      fetchInitiatives();
      fetchSummary();
    } catch (error) {
      console.error('Failed to delete:', error);
      toast.error('Failed to delete initiative');
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
      return 'Today';
    } else if (diffDays === 1) {
      return 'Yesterday';
    } else if (diffDays < 7) {
      return `${diffDays} days ago`;
    } else {
      return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric',
        year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
      });
    }
  };

  const StatusBadge = ({ status }) => {
    const config = STATUS_CONFIG[status] || STATUS_CONFIG.draft;
    const Icon = config.icon;
    return (
      <Badge variant="outline" className={`${config.color} gap-1`}>
        <Icon className="h-3 w-3" />
        {config.label}
      </Badge>
    );
  };

  return (
    <div className="space-y-6" data-testid="initiatives-page">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Initiative Library</h1>
          <p className="text-muted-foreground">
            Manage all your product initiatives in one place
          </p>
        </div>
        <Button 
          onClick={() => navigate('/new')} 
          className="gap-2"
          data-testid="new-initiative-btn"
        >
          <Sparkles className="h-4 w-4" />
          New Initiative
        </Button>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-card border rounded-lg p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <FolderOpen className="h-4 w-4" />
              Total
            </div>
            <div className="text-2xl font-bold mt-1">{summary.total}</div>
          </div>
          <div className="bg-card border rounded-lg p-4">
            <div className="flex items-center gap-2 text-amber-600 text-sm">
              <Edit3 className="h-4 w-4" />
              Draft
            </div>
            <div className="text-2xl font-bold mt-1">{summary.draft}</div>
          </div>
          <div className="bg-card border rounded-lg p-4">
            <div className="flex items-center gap-2 text-blue-600 text-sm">
              <Clock className="h-4 w-4" />
              Active
            </div>
            <div className="text-2xl font-bold mt-1">{summary.active}</div>
          </div>
          <div className="bg-card border rounded-lg p-4">
            <div className="flex items-center gap-2 text-emerald-600 text-sm">
              <CheckCircle2 className="h-4 w-4" />
              Completed
            </div>
            <div className="text-2xl font-bold mt-1">{summary.completed}</div>
          </div>
          <div className="bg-card border rounded-lg p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Archive className="h-4 w-4" />
              Archived
            </div>
            <div className="text-2xl font-bold mt-1">{summary.archived || 0}</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by title, tagline, or problem..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
            data-testid="search-input"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full sm:w-40" data-testid="status-filter">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="draft">Draft</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
          </SelectContent>
        </Select>
        <Button 
          variant="outline" 
          size="icon" 
          onClick={fetchInitiatives}
          data-testid="refresh-btn"
        >
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {/* Table */}
      <div className="border rounded-lg overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[35%]">Name</TableHead>
              <TableHead className="w-[15%]">Status</TableHead>
              <TableHead className="w-[15%] text-center">Updated</TableHead>
              <TableHead className="w-[20%] text-center hidden md:table-cell">Stories / Points</TableHead>
              <TableHead className="w-[15%] text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  <div className="flex items-center justify-center gap-2 text-muted-foreground">
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    Loading initiatives...
                  </div>
                </TableCell>
              </TableRow>
            ) : initiatives.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <FileText className="h-8 w-8" />
                    <p>No initiatives found</p>
                    {searchQuery || statusFilter !== 'all' ? (
                      <Button 
                        variant="link" 
                        onClick={() => { setSearchQuery(''); setStatusFilter('all'); }}
                      >
                        Clear filters
                      </Button>
                    ) : (
                      <Button 
                        variant="link" 
                        onClick={() => navigate('/new')}
                      >
                        Create your first initiative
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              initiatives.map((initiative) => (
                <TableRow 
                  key={initiative.epic_id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => handleView(initiative.epic_id)}
                  data-testid={`initiative-row-${initiative.epic_id}`}
                >
                  <TableCell>
                    <div className="space-y-1">
                      <div className="font-medium">{initiative.title}</div>
                      {initiative.tagline && (
                        <div className="text-sm text-muted-foreground line-clamp-1">
                          {initiative.tagline}
                        </div>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={initiative.status} />
                  </TableCell>
                  <TableCell className="text-center text-muted-foreground text-sm">
                    {formatDate(initiative.updated_at)}
                  </TableCell>
                  <TableCell className="text-center hidden md:table-cell">
                    <div className="flex items-center justify-center gap-2">
                      <span className="text-sm">
                        {initiative.stories_count} stories
                      </span>
                      {initiative.total_points > 0 && (
                        <Badge variant="secondary" className="text-xs">
                          {initiative.total_points} pts
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" data-testid={`actions-${initiative.epic_id}`}>
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => handleView(initiative.epic_id)}>
                          <Eye className="mr-2 h-4 w-4" />
                          View
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleDuplicate(initiative)}>
                          <Copy className="mr-2 h-4 w-4" />
                          Duplicate
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => handleArchive(initiative)}>
                          <Archive className="mr-2 h-4 w-4" />
                          Archive
                        </DropdownMenuItem>
                        <DropdownMenuItem 
                          onClick={() => setDeleteDialog({ open: true, initiative })}
                          className="text-destructive focus:text-destructive"
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {pagination.total > pagination.pageSize && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Showing {((pagination.page - 1) * pagination.pageSize) + 1} to{' '}
            {Math.min(pagination.page * pagination.pageSize, pagination.total)} of{' '}
            {pagination.total} initiatives
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.page === 1}
              onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!pagination.hasMore}
              onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialog.open} onOpenChange={(open) => setDeleteDialog({ open, initiative: null })}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Initiative?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete "{deleteDialog.initiative?.title}" and all its features, 
              stories, and related data. This action cannot be undone.
              <br /><br />
              <strong>Tip:</strong> Use Archive instead if you want to restore it later.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete Permanently
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default Initiatives;
