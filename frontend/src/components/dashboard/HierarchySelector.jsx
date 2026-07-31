import { useState, useEffect, useMemo } from 'react';
import { ChevronDown, Search, Users } from 'lucide-react';
import { dashboardAPI } from '../../services/api';

const HierarchySelector = ({ onSelect, selectedUserId }) => {
  const [scopeUsers, setScopeUsers] = useState({ sub_distributors: [], clusters: [], operators: [] });
  const [sdId, setSdId] = useState('');
  const [clusterId, setClusterId] = useState('');
  const [operatorId, setOperatorId] = useState('');
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    const fetchScopeUsers = async () => {
      try {
        setLoading(true);
        const res = await dashboardAPI.getScopeUsers();
        setScopeUsers(res.data || { sub_distributors: [], clusters: [], operators: [] });
      } catch (err) {
        console.error('Failed to load scope users:', err);
        setScopeUsers({ sub_distributors: [], clusters: [], operators: [] });
      } finally {
        setLoading(false);
      }
    };
    fetchScopeUsers();
  }, []);

  const searchLower = search.toLowerCase().trim();

  const matchesUser = (u, q) => {
    const identities = Array.isArray(u?.digital_ids) ? u.digital_ids : [];
    const hasIdentity = identities.some(di =>
      String(di?.digital_id || '').toLowerCase().includes(q) ||
      String(di?.broadband_id || '').toLowerCase().includes(q),
    );
    return (
      u.name.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q) ||
      hasIdentity
    );
  };

  const filteredSubDistributors = useMemo(() => {
    let list = scopeUsers.sub_distributors;
    if (searchLower) {
      list = list.filter((u) => matchesUser(u, searchLower));
    }
    return list;
  }, [scopeUsers.sub_distributors, searchLower]);

  const filteredClusters = scopeUsers.clusters.filter(
    (c) => (c.parent_id === sdId || (!sdId))
  ).filter((c) => {
    if (!searchLower || sdId) return true;
    return matchesUser(c, searchLower);
  });

  const filteredOperators = scopeUsers.operators.filter(
    (op) => (op.parent_id === clusterId || (!clusterId))
  ).filter((op) => {
    if (!searchLower || clusterId) return true;
    return matchesUser(op, searchLower);
  });

  const handleSdChange = (e) => {
    const val = e.target.value;
    setSdId(val);
    setClusterId('');
    setOperatorId('');
    if (val) {
      onSelect({ type: 'sub_distributor', id: val });
    } else {
      onSelect(null);
    }
  };

  const handleClusterChange = (e) => {
    const val = e.target.value;
    setClusterId(val);
    setOperatorId('');
    if (val) {
      onSelect({ type: 'cluster', id: val });
    } else if (sdId) {
      onSelect({ type: 'sub_distributor', id: sdId });
    } else {
      onSelect(null);
    }
  };

  const handleOperatorChange = (e) => {
    const val = e.target.value;
    setOperatorId(val);
    if (val) {
      onSelect({ type: 'operator', id: val });
    } else if (clusterId) {
      onSelect({ type: 'cluster', id: clusterId });
    } else if (sdId) {
      onSelect({ type: 'sub_distributor', id: sdId });
    } else {
      onSelect(null);
    }
  };

  const handleClear = () => {
    setSdId('');
    setClusterId('');
    setOperatorId('');
    onSelect(null);
  };

  if (loading) {
    return null;
  }

  const hasData = scopeUsers.sub_distributors.length > 0 || scopeUsers.clusters.length > 0 || scopeUsers.operators.length > 0;
  if (!hasData) {
    return null;
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-3 sm:p-4 shadow-sm animate-fadeIn">
      <div className="flex items-center gap-2 mb-3">
        <Users className="w-4 h-4 text-blue-600" />
        <span className="text-sm font-semibold text-gray-700">Scope Dashboard</span>
      </div>
      <div className="relative mb-3">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
        <input
          type="text"
          placeholder="Search by name or email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[160px]">
          <label className="block text-xs text-gray-500 mb-1">Sub-Distributor</label>
          <div className="relative">
            <select
              value={sdId}
              onChange={handleSdChange}
              className="w-full appearance-none bg-white border border-gray-300 rounded-lg px-3 py-2 pr-8 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">All Sub-Distributors</option>
              {filteredSubDistributors.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
        </div>

        <div className="flex-1 min-w-[160px]">
          <label className="block text-xs text-gray-500 mb-1">Cluster</label>
          <div className="relative">
            <select
              value={clusterId}
              onChange={handleClusterChange}
              className="w-full appearance-none bg-white border border-gray-300 rounded-lg px-3 py-2 pr-8 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50"
              disabled={!sdId}
            >
              <option value="">All Clusters</option>
              {filteredClusters.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
        </div>

        <div className="flex-1 min-w-[160px]">
          <label className="block text-xs text-gray-500 mb-1">Operator</label>
          <div className="relative">
            <select
              value={operatorId}
              onChange={handleOperatorChange}
              className="w-full appearance-none bg-white border border-gray-300 rounded-lg px-3 py-2 pr-8 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50"
              disabled={!clusterId}
            >
              <option value="">All Operators</option>
              {filteredOperators.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
        </div>

        {selectedUserId && (
          <button
            onClick={handleClear}
            className="px-3 py-2 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
};

export default HierarchySelector;
