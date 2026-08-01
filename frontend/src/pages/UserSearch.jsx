import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { usersAPI, dashboardAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { Search, Users, Building2, UserCog, HardHat, Loader2, ChevronRight } from 'lucide-react';

const ROLE_ICONS = {
  sub_distributor: Building2,
  cluster: UserCog,
  operator: HardHat,
};

const ROLE_LABELS = {
  sub_distributor: 'Sub Distributor',
  cluster: 'Cluster',
  operator: 'Operator',
  sub_distribution_manager: 'Sub Distribution Manager',
};

const UserSearch = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { showToast } = useNotifications();
  const initialQuery = searchParams.get('q') || '';
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [users, setUsers] = useState([]);

  useEffect(() => {
    usersAPI.getUsers({ page_size: 10000 }).then(res => {
      const all = Array.isArray(res.data) ? res.data : [];
      setUsers(all.filter(u => ['sub_distributor', 'cluster', 'operator', 'sub_distribution_manager'].includes(u.role)));
    }).catch(() => {});
  }, []);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const q = query.trim().toLowerCase();
      const filtered = users.filter(u => {
        const identities = Array.isArray(u?.digital_ids) ? u.digital_ids : [];
        const hasIdentity = identities.some(di =>
          String(di?.digital_id || '').toLowerCase().includes(q) ||
          String(di?.broadband_id || '').toLowerCase().includes(q),
        );
        return (
          u.name?.toLowerCase().includes(q) ||
          String(u.id).includes(q) ||
          u.email?.toLowerCase().includes(q) ||
          hasIdentity
        );
      });
      setResults(filtered);
    } catch {
      showToast('Search failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSearch();
  };

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      <div className="bg-gradient-to-br from-green-50 to-emerald-50/30 border border-green-200 rounded-2xl p-6 sm:p-8 shadow-sm">
        <div className="flex items-center gap-3 mb-1">
          <Users className="w-7 h-7 text-green-600" />
          <h1 className="text-2xl sm:text-3xl font-bold text-green-900">View User Dashboard</h1>
        </div>
        <p className="text-green-700 text-sm sm:text-base mt-1">Search for a sub-distributor, cluster, or operator to view their dashboard.</p>
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name, digital ID, broadband ID, or email..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none text-sm"
          />
        </div>
        <button
          onClick={handleSearch}
          disabled={loading || !query.trim()}
          className="px-6 py-3 bg-green-600 text-white rounded-xl hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm flex items-center gap-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
          Search
        </button>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 animate-spin text-green-600" />
        </div>
      )}

      {!loading && searched && results.length === 0 && (
        <div className="text-center py-16 text-gray-500">
          <Users className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p className="text-lg font-medium">No users found</p>
          <p className="text-sm mt-1">Try a different search term.</p>
        </div>
      )}

      {!loading && results.length > 0 && (
        <div className="grid gap-3">
          <p className="text-sm text-gray-500 font-medium">{results.length} user{results.length !== 1 ? 's' : ''} found</p>
          {results.map((u) => {
            const Icon = ROLE_ICONS[u.role] || Users;
            return (
              <div
                key={u.id}
                onClick={() => navigate(`/view-as/${u.id}`)}
                className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm hover:shadow-md hover:border-green-300 cursor-pointer transition-all flex items-center gap-4 group"
              >
                <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
                  <Icon className="w-6 h-6 text-green-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-900 truncate">{u.name || 'Unnamed'}</p>
                  <p className="text-sm text-gray-500">ID: {u.id} &middot; {ROLE_LABELS[u.role] || u.role}</p>
                  {u.email && <p className="text-xs text-gray-400 truncate">{u.email}</p>}
                </div>
                <ChevronRight className="w-5 h-5 text-gray-300 group-hover:text-green-500 transition-colors flex-shrink-0" />
              </div>
            );
          })}
        </div>
      )}

      {!searched && !loading && (
        <div className="text-center py-16 text-gray-400">
          <Users className="w-16 h-16 mx-auto mb-4 text-gray-200" />
          <p className="text-lg">Enter a name or ID to find a user</p>
          <p className="text-sm mt-1">View their dashboard as they see it</p>
        </div>
      )}
    </div>
  );
};

export default UserSearch;
