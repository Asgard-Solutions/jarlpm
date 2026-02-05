import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import ThemeToggle from '@/components/ThemeToggle';
import { useAuthStore } from '@/store';
import { personaAPI, epicAPI } from '@/api';
import {
  Users, ArrowLeft, Settings, Search, Loader2, Trash2,
  User, Target, AlertTriangle, Sparkles, Quote, MapPin,
  Briefcase, RefreshCw, Edit3, CheckCircle2, X, ImageIcon
} from 'lucide-react';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';

const Personas = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuthStore();
  const [theme, setTheme] = useState('light');
  const logoSrc = theme === 'dark' ? '/logo-dark.png' : '/logo-light.png';

  // State
  const [personas, setPersonas] = useState([]);
  const [epics, setEpics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Filters
  const [epicFilter, setEpicFilter] = useState(searchParams.get('epic') || 'all');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Dialogs
  const [showDetailDialog, setShowDetailDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [selectedPersona, setSelectedPersona] = useState(null);
  
  // Edit form
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);
  
  // Actions
  const [deleting, setDeleting] = useState(false);
  const [regeneratingImage, setRegeneratingImage] = useState(false);

  // Theme detection
  useEffect(() => {
    const root = document.documentElement;
    const observer = new MutationObserver(() => {
      setTheme(root.classList.contains('dark') ? 'dark' : 'light');
    });
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    setTheme(root.classList.contains('dark') ? 'dark' : 'light');
    return () => observer.disconnect();
  }, []);

  // Load personas
  const loadPersonas = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (epicFilter && epicFilter !== 'all') params.epic_id = epicFilter;
      if (searchQuery) params.search = searchQuery;
      
      const response = await personaAPI.list(params);
      setPersonas(response.data || []);
    } catch (err) {
      setError('Failed to load personas');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [epicFilter, searchQuery]);

  // Load epics for filter dropdown
  const loadEpics = useCallback(async () => {
    try {
      const response = await epicAPI.list();
      // Only show locked/completed epics
      const completedEpics = (response.data || []).filter(e => e.current_stage === 'epic_locked');
      setEpics(completedEpics);
    } catch (err) {
      console.error('Failed to load epics:', err);
    }
  }, []);

  useEffect(() => {
    if (user) {
      loadPersonas();
      loadEpics();
    }
  }, [user, loadPersonas, loadEpics]);

  // Filter personas client-side (search already handled by API, but also filter by epic)
  const filteredPersonas = personas.filter(p => {
    if (epicFilter !== 'all' && p.epic_id !== epicFilter) return false;
    if (searchQuery) {
      const sq = searchQuery.toLowerCase();
      return p.name.toLowerCase().includes(sq) ||
             p.role.toLowerCase().includes(sq) ||
             (p.representative_quote && p.representative_quote.toLowerCase().includes(sq));
    }
    return true;
  });

  // Open detail dialog
  const openDetail = (persona) => {
    setSelectedPersona(persona);
    setShowDetailDialog(true);
  };

  // Open edit dialog
  const openEdit = (persona) => {
    setSelectedPersona(persona);
    setEditForm({
      name: persona.name,
      role: persona.role,
      age_range: persona.age_range || '',
      location: persona.location || '',
      tech_proficiency: persona.tech_proficiency || '',
      goals_and_motivations: persona.goals_and_motivations || [],
      pain_points: persona.pain_points || [],
      key_behaviors: persona.key_behaviors || [],
      jobs_to_be_done: persona.jobs_to_be_done || [],
      product_interaction_context: persona.product_interaction_context || '',
      representative_quote: persona.representative_quote || '',
    });
    setShowEditDialog(true);
  };

  // Save edits
  const handleSave = async () => {
    if (!selectedPersona) return;
    
    try {
      setSaving(true);
      await personaAPI.update(selectedPersona.persona_id, editForm);
      setShowEditDialog(false);
      loadPersonas();
    } catch (err) {
      setError('Failed to save persona');
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  // Delete persona
  const handleDelete = async (personaId) => {
    if (!window.confirm('Are you sure you want to delete this persona?')) return;
    
    try {
      setDeleting(true);
      await personaAPI.delete(personaId);
      setShowDetailDialog(false);
      setSelectedPersona(null);
      loadPersonas();
    } catch (err) {
      setError('Failed to delete persona');
    } finally {
      setDeleting(false);
    }
  };

  // Regenerate portrait
  const handleRegeneratePortrait = async (personaId) => {
    try {
      setRegeneratingImage(true);
      await personaAPI.regeneratePortrait(personaId);
      loadPersonas();
      if (selectedPersona?.persona_id === personaId) {
        const response = await personaAPI.get(personaId);
        setSelectedPersona(response.data);
      }
    } catch (err) {
      setError('Failed to regenerate portrait');
    } finally {
      setRegeneratingImage(false);
    }
  };

  // Update array field in edit form
  const updateArrayField = (field, index, value) => {
    const updated = [...(editForm[field] || [])];
    updated[index] = value;
    setEditForm({ ...editForm, [field]: updated });
  };

  const addArrayItem = (field) => {
    setEditForm({ ...editForm, [field]: [...(editForm[field] || []), ''] });
  };

  const removeArrayItem = (field, index) => {
    const updated = (editForm[field] || []).filter((_, i) => i !== index);
    setEditForm({ ...editForm, [field]: updated });
  };

  // Get epic title by ID
  const getEpicTitle = (epicId) => {
    const epic = epics.find(e => e.epic_id === epicId);
    return epic?.title || 'Unknown Epic';
  };

  if (!user) {
    navigate('/');
    return null;
  }

  return (
    <div className="flex flex-col overflow-hidden -m-6" style={{ height: 'calc(100vh - 4rem)' }} data-testid="personas-page">
      {/* Page Title Bar */}
      <div className="flex-shrink-0 border-b border-border bg-background/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-4 h-14">
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={() => navigate('/dashboard')} 
              className="text-muted-foreground hover:text-foreground"
              data-testid="back-btn"
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <span className="text-lg font-semibold text-foreground">User Personas</span>
          </div>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="flex-shrink-0 border-b border-border bg-muted/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex items-center gap-4 flex-wrap">
            {/* Search */}
            <div className="relative flex-1 min-w-[200px] max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search personas..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
                data-testid="search-input"
              />
            </div>
            
            {/* Epic Filter */}
            <Select value={epicFilter} onValueChange={setEpicFilter}>
              <SelectTrigger className="w-[200px]" data-testid="epic-filter">
                <SelectValue placeholder="Filter by Epic" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Epics</SelectItem>
                {epics.map(epic => (
                  <SelectItem key={epic.epic_id} value={epic.epic_id}>
                    {epic.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            <div className="text-sm text-muted-foreground">
              {filteredPersonas.length} persona{filteredPersonas.length !== 1 ? 's' : ''}
            </div>
          </div>
        </div>
      </div>

      {/* Personas Grid */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {error && (
            <div className="mb-4 p-3 bg-destructive/10 border border-destructive/30 rounded-lg text-destructive text-sm">
              {error}
              <Button variant="ghost" size="sm" onClick={() => setError(null)} className="ml-2">
                Dismiss
              </Button>
            </div>
          )}
          
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredPersonas.length === 0 ? (
            <EmptyState
              icon={Users}
              title="No personas yet"
              description={
                searchQuery || epicFilter !== 'all'
                  ? 'No personas match your filters. Try adjusting search or epic filter.'
                  : 'Generate personas from a completed Epic to get started.'
              }
              actionLabel="Go to Dashboard"
              onAction={() => navigate('/dashboard')}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredPersonas.map((persona) => (
                <PersonaCard 
                  key={persona.persona_id} 
                  persona={persona}
                  epicTitle={getEpicTitle(persona.epic_id)}
                  onClick={() => openDetail(persona)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Detail Dialog */}
      {selectedPersona && (
        <PersonaDetailDialog
          persona={selectedPersona}
          epicTitle={getEpicTitle(selectedPersona.epic_id)}
          open={showDetailDialog}
          onClose={() => {
            setShowDetailDialog(false);
            setSelectedPersona(null);
          }}
          onEdit={() => {
            setShowDetailDialog(false);
            openEdit(selectedPersona);
          }}
          onDelete={() => handleDelete(selectedPersona.persona_id)}
          onRegeneratePortrait={() => handleRegeneratePortrait(selectedPersona.persona_id)}
          deleting={deleting}
          regeneratingImage={regeneratingImage}
        />
      )}

      {/* Edit Dialog */}
      {selectedPersona && (
        <PersonaEditDialog
          persona={selectedPersona}
          editForm={editForm}
          setEditForm={setEditForm}
          open={showEditDialog}
          onClose={() => {
            setShowEditDialog(false);
            setSelectedPersona(null);
          }}
          onSave={handleSave}
          saving={saving}
          updateArrayField={updateArrayField}
          addArrayItem={addArrayItem}
          removeArrayItem={removeArrayItem}
        />
      )}
    </div>
  );
};

// Persona Card Component
const PersonaCard = ({ persona, epicTitle, onClick }) => {
  return (
    <Card 
      className="cursor-pointer hover:border-primary/50 transition-colors overflow-hidden"
      onClick={onClick}
      data-testid={`persona-card-${persona.persona_id}`}
    >
      <div className="flex">
        {/* Portrait */}
        <div className="w-24 h-32 flex-shrink-0 bg-muted flex items-center justify-center overflow-hidden">
          {persona.portrait_image_base64 ? (
            <img 
              src={`data:image/png;base64,${persona.portrait_image_base64}`}
              alt={persona.name}
              className="w-full h-full object-cover"
            />
          ) : (
            <User className="w-10 h-10 text-muted-foreground" />
          )}
        </div>
        
        {/* Content */}
        <CardContent className="p-3 flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1">
            <div className="min-w-0">
              <h3 className="font-semibold text-foreground truncate">{persona.name}</h3>
              <p className="text-sm text-muted-foreground truncate">{persona.role}</p>
            </div>
            <Badge variant="outline" className={`text-xs flex-shrink-0 ${
              persona.source === 'human_modified' ? 'bg-amber-500/20 text-amber-400' : 'bg-violet-500/20 text-violet-400'
            }`}>
              {persona.source === 'human_modified' ? 'Edited' : 'AI'}
            </Badge>
          </div>
          
          {persona.representative_quote && (
            <p className="text-xs text-muted-foreground italic line-clamp-2 mb-2">
              &ldquo;{persona.representative_quote}&rdquo;
            </p>
          )}
          
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="truncate">{epicTitle}</span>
          </div>
        </CardContent>
      </div>
    </Card>
  );
};

// Persona Detail Dialog
const PersonaDetailDialog = ({ 
  persona, epicTitle, open, onClose, onEdit, onDelete, 
  onRegeneratePortrait, deleting, regeneratingImage 
}) => {
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Users className="w-5 h-5 text-primary" />
            User Persona
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto">
          <div className="flex gap-6">
            {/* Portrait */}
            <div className="flex-shrink-0">
              <div className="w-40 h-48 bg-muted rounded-lg overflow-hidden relative group">
                {persona.portrait_image_base64 ? (
                  <img 
                    src={`data:image/png;base64,${persona.portrait_image_base64}`}
                    alt={persona.name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <User className="w-16 h-16 text-muted-foreground" />
                  </div>
                )}
                <Button 
                  variant="secondary"
                  size="sm"
                  className="absolute bottom-2 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => { e.stopPropagation(); onRegeneratePortrait(); }}
                  disabled={regeneratingImage}
                  data-testid="regenerate-portrait-btn"
                >
                  {regeneratingImage ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                </Button>
              </div>
              <div className="mt-2 text-center">
                <Badge variant="outline" className={`${
                  persona.source === 'human_modified' ? 'bg-amber-500/20 text-amber-400' : 'bg-violet-500/20 text-violet-400'
                }`}>
                  {persona.source === 'human_modified' ? 'Human Modified' : 'AI Generated'}
                </Badge>
              </div>
            </div>

            {/* Details */}
            <div className="flex-1 space-y-4">
              <div>
                <h2 className="text-2xl font-bold text-foreground">{persona.name}</h2>
                <p className="text-lg text-muted-foreground flex items-center gap-2">
                  <Briefcase className="w-4 h-4" />
                  {persona.role}
                </p>
              </div>

              <div className="flex flex-wrap gap-3 text-sm">
                {persona.age_range && (
                  <span className="flex items-center gap-1 text-muted-foreground">
                    <User className="w-4 h-4" /> {persona.age_range}
                  </span>
                )}
                {persona.location && (
                  <span className="flex items-center gap-1 text-muted-foreground">
                    <MapPin className="w-4 h-4" /> {persona.location}
                  </span>
                )}
                {persona.tech_proficiency && (
                  <Badge variant="outline">{persona.tech_proficiency} Tech</Badge>
                )}
              </div>

              {persona.representative_quote && (
                <div className="p-3 bg-muted/50 rounded-lg border-l-4 border-primary">
                  <Quote className="w-4 h-4 text-muted-foreground mb-1" />
                  <p className="italic text-foreground">&ldquo;{persona.representative_quote}&rdquo;</p>
                </div>
              )}

              <div className="text-xs text-muted-foreground">
                From Epic: <span className="text-foreground">{epicTitle}</span>
              </div>
            </div>
          </div>

          {/* Detailed sections */}
          <div className="grid grid-cols-2 gap-4 mt-6">
            {persona.goals_and_motivations?.length > 0 && (
              <DetailSection 
                title="Goals & Motivations" 
                icon={<Target className="w-4 h-4 text-green-500" />}
                items={persona.goals_and_motivations}
              />
            )}
            
            {persona.pain_points?.length > 0 && (
              <DetailSection 
                title="Pain Points" 
                icon={<AlertTriangle className="w-4 h-4 text-red-500" />}
                items={persona.pain_points}
              />
            )}
            
            {persona.key_behaviors?.length > 0 && (
              <DetailSection 
                title="Key Behaviors" 
                icon={<Sparkles className="w-4 h-4 text-blue-500" />}
                items={persona.key_behaviors}
              />
            )}
            
            {persona.jobs_to_be_done?.length > 0 && (
              <DetailSection 
                title="Jobs to Be Done" 
                icon={<CheckCircle2 className="w-4 h-4 text-violet-500" />}
                items={persona.jobs_to_be_done}
              />
            )}
          </div>

          {persona.product_interaction_context && (
            <div className="mt-4 p-3 bg-muted/30 rounded-lg">
              <h4 className="font-semibold text-foreground text-sm mb-1">Product Interaction Context</h4>
              <p className="text-sm text-muted-foreground">{persona.product_interaction_context}</p>
            </div>
          )}
        </div>

        <DialogFooter className="border-t border-border pt-4 mt-4">
          <div className="flex items-center justify-between w-full">
            <Button 
              variant="destructive" 
              size="sm"
              onClick={onDelete}
              disabled={deleting}
              data-testid="delete-persona-btn"
            >
              {deleting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Trash2 className="w-4 h-4 mr-2" />}
              Delete
            </Button>
            
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={onEdit} data-testid="edit-persona-btn">
                <Edit3 className="w-4 h-4 mr-2" />
                Edit
              </Button>
              <Button variant="outline" onClick={onClose}>
                Close
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// Detail Section Component
const DetailSection = ({ title, icon, items }) => (
  <div>
    <h4 className="font-semibold text-foreground text-sm flex items-center gap-2 mb-2">
      {icon} {title}
    </h4>
    <ul className="space-y-1">
      {items.map((item, i) => (
        <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
          <span className="text-muted-foreground mt-1">•</span>
          {item}
        </li>
      ))}
    </ul>
  </div>
);

// Persona Edit Dialog
const PersonaEditDialog = ({ 
  persona, editForm, setEditForm, open, onClose, onSave, saving,
  updateArrayField, addArrayItem, removeArrayItem 
}) => {
  const arrayFields = [
    { key: 'goals_and_motivations', label: 'Goals & Motivations' },
    { key: 'pain_points', label: 'Pain Points' },
    { key: 'key_behaviors', label: 'Key Behaviors' },
    { key: 'jobs_to_be_done', label: 'Jobs to Be Done' },
  ];

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Edit3 className="w-5 h-5 text-primary" />
            Edit Persona: {persona.name}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={editForm.name || ''}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="role">Role</Label>
              <Input
                id="role"
                value={editForm.role || ''}
                onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label htmlFor="age_range">Age Range</Label>
              <Input
                id="age_range"
                placeholder="e.g., 25-34"
                value={editForm.age_range || ''}
                onChange={(e) => setEditForm({ ...editForm, age_range: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="location">Location</Label>
              <Input
                id="location"
                placeholder="e.g., Urban, USA"
                value={editForm.location || ''}
                onChange={(e) => setEditForm({ ...editForm, location: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="tech_proficiency">Tech Proficiency</Label>
              <Select 
                value={editForm.tech_proficiency || ''} 
                onValueChange={(v) => setEditForm({ ...editForm, tech_proficiency: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="High">High</SelectItem>
                  <SelectItem value="Medium">Medium</SelectItem>
                  <SelectItem value="Low">Low</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <Label htmlFor="quote">Representative Quote</Label>
            <Textarea
              id="quote"
              placeholder="A quote that captures their perspective..."
              value={editForm.representative_quote || ''}
              onChange={(e) => setEditForm({ ...editForm, representative_quote: e.target.value })}
              rows={2}
            />
          </div>

          <div>
            <Label htmlFor="context">Product Interaction Context</Label>
            <Textarea
              id="context"
              placeholder="When and why they use this product..."
              value={editForm.product_interaction_context || ''}
              onChange={(e) => setEditForm({ ...editForm, product_interaction_context: e.target.value })}
              rows={2}
            />
          </div>

          {arrayFields.map(({ key, label }) => (
            <div key={key}>
              <div className="flex items-center justify-between mb-2">
                <Label>{label}</Label>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => addArrayItem(key)}
                  type="button"
                >
                  + Add
                </Button>
              </div>
              {(editForm[key] || []).map((item, idx) => (
                <div key={idx} className="flex gap-2 mb-2">
                  <Input
                    value={item}
                    onChange={(e) => updateArrayField(key, idx, e.target.value)}
                    className="flex-1"
                  />
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={() => removeArrayItem(key, idx)}
                    type="button"
                  >
                    <X className="w-4 h-4 text-destructive" />
                  </Button>
                </div>
              ))}
              {(!editForm[key] || editForm[key].length === 0) && (
                <p className="text-sm text-muted-foreground italic">No items. Click &quot;+ Add&quot; to add one.</p>
              )}
            </div>
          ))}
        </div>

        <DialogFooter className="border-t border-border pt-4">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={onSave} disabled={saving} data-testid="save-persona-btn">
            {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle2 className="w-4 h-4 mr-2" />}
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default Personas;
