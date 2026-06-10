import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { api } from '../services/api';
import { 
  Building2, 
  Users,
  Plus,
  ArrowLeft,
  MapPin,
  Phone,
  Mail,
  Package,
  Trash2,
  Edit,
  User
} from 'lucide-react';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import StatusBadge from '../components/ui/StatusBadge';

const DistributionDetail = () => {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { showToast } = useNotifications();
  const [loading, setLoading] = useState(true);
  const [distribution, setDistribution] = useState(null);
  const [subDistributions, setSubDistributions] = useState([]);

  const canManage = ['super_admin', 'manager'].includes(user?.role);

  useEffect(() => {
    fetchDistribution();
    fetchSubDistributions();
  }, [id]);

  const fetchDistribution = async () => {
    try {
      const response = await api.get(`/distributions/${id}`);
      setDistribution(response.data);
    } catch (error) {
      showToast('Failed to fetch distribution', 'error');
      console.error(error);
    }
  };

  const fetchSubDistributions = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/distributions/${id}/sub-distributions`);
      setSubDistributions(response.data || []);
    } catch (error) {
      showToast('Failed to fetch sub-distributions', 'error');
      console.error(error);
      setSubDistributions([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSubDistribution = async (subDistId, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this sub-distribution and all its operators?')) return;
    
    try {
      await api.delete(`/distributions/sub-distributions/${subDistId}`);
      showToast('Sub-distribution deleted successfully', 'success');
      fetchSubDistributions();
      fetchDistribution(); // Refresh count
    } catch (error) {
      showToast('Failed to delete sub-distribution', 'error');
      console.error(error);
    }
  };

  if (!distribution) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button
          variant="secondary"
          size="sm"
          icon={ArrowLeft}
          onClick={() => navigate('/distributions')}
        >
          Back to Distributions
        </Button>
      </div>

      {/* Distribution Info Card */}
      <Card>
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <Building2 className="w-8 h-8 text-blue-600" />
            <div>
              <h1 className="text-2xl font-bold text-gray-800">{distribution.name}</h1>
              <p className="text-sm text-gray-500">{distribution.distribution_id}</p>
            </div>
          </div>
          <StatusBadge status={distribution.status} />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {distribution.location && (
            <div className="flex items-center gap-2 text-gray-600">
              <MapPin className="w-5 h-5" />
              <span>{distribution.location}</span>
            </div>
          )}
          {distribution.contact_person && (
            <div className="flex items-center gap-2 text-gray-600">
              <User className="w-5 h-5" />
              <span>{distribution.contact_person}</span>
            </div>
          )}
          {distribution.contact_number && (
            <div className="flex items-center gap-2 text-gray-600">
              <Phone className="w-5 h-5" />
              <span>{distribution.contact_number}</span>
            </div>
          )}
          {distribution.email && (
            <div className="flex items-center gap-2 text-gray-600">
              <Mail className="w-5 h-5" />
              <span>{distribution.email}</span>
            </div>
          )}
        </div>

        {distribution.notes && (
          <div className="mt-4 pt-4 border-t">
            <p className="text-sm text-gray-600">{distribution.notes}</p>
          </div>
        )}

        <div className="mt-4 pt-4 border-t">
          <div className="flex items-center gap-6 text-sm">
            <div className="flex items-center gap-2 text-gray-600">
              <Users className="w-4 h-4" />
              <span>{distribution.sub_distribution_count} Sub-Distributions</span>
            </div>
            <div className="flex items-center gap-2 text-gray-600">
              <Package className="w-4 h-4" />
              <span>{distribution.device_count} Devices</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Sub-Distributions Section */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-800">Sub-Distributions</h2>
          <p className="text-gray-500 mt-1">Manage sub-distributions under {distribution.name}</p>
        </div>
        {canManage && (
          <Button 
            icon={Plus} 
            onClick={() => navigate('/distributions/create', { 
              state: { 
                entityType: 'sub-distribution',
                parentId: distribution.id,
                parentName: distribution.name
              } 
            })}
          >
            Create Sub-Distribution
          </Button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {subDistributions.map(subDist => (
              <Card
                key={subDist.id}
                className="cursor-pointer hover:shadow-lg transition-shadow"
                onClick={() => navigate(`/distributions/sub-distributions/${subDist.id}`)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Users className="w-5 h-5 text-green-600" />
                    <h3 className="font-semibold text-gray-800">{subDist.name}</h3>
                  </div>
                  <StatusBadge status={subDist.status} size="sm" />
                </div>

                {subDist.location && (
                  <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
                    <MapPin className="w-4 h-4" />
                    <span>{subDist.location}</span>
                  </div>
                )}

                <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                  <div className="flex items-center gap-4 text-sm text-gray-500">
                    <div className="flex items-center gap-1">
                      <User className="w-4 h-4" />
                      <span>{subDist.operator_count} Operators</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Package className="w-4 h-4" />
                      <span>{subDist.device_count} Devices</span>
                    </div>
                  </div>
                  
                  {canManage && (
                    <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                      <button
                        onClick={(e) => handleDeleteSubDistribution(subDist.id, e)}
                        className="p-1 text-red-600 hover:bg-red-50 rounded"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              </Card>
            ))}
          </div>

          {subDistributions.length === 0 && (
            <div className="text-center py-12">
              <Users className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No sub-distributions found</p>
              {canManage && (
                <Button 
                  className="mt-4" 
                  onClick={() => navigate('/distributions/create', { 
                    state: { 
                      entityType: 'sub-distribution', 
                      parentId: distribution.id,
                      parentName: distribution.name
                    } 
                  })}
                >
                  Create First Sub-Distribution
                </Button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default DistributionDetail;

