import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { api } from '../services/api';
import { 
  Users,
  User,
  Plus,
  ArrowLeft,
  MapPin,
  Phone,
  Mail,
  Package,
  Trash2,
  Building2
} from 'lucide-react';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import StatusBadge from '../components/ui/StatusBadge';

const SubDistributionDetail = () => {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { showToast } = useNotifications();
  const [loading, setLoading] = useState(true);
  const [subDistribution, setSubDistribution] = useState(null);
  const [operators, setOperators] = useState([]);

  const canManage = ['super_admin', 'manager'].includes(user?.role);

  useEffect(() => {
    fetchSubDistribution();
    fetchOperators();
  }, [id]);

  const fetchSubDistribution = async () => {
    try {
      const response = await api.get(`/distributions/sub-distributions/${id}`);
      setSubDistribution(response.data);
    } catch (error) {
      showToast('Failed to fetch sub-distribution', 'error');
      console.error(error);
    }
  };

  const fetchOperators = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/distributions/sub-distributions/${id}/operators`);
      setOperators(response.data || []);
    } catch (error) {
      showToast('Failed to fetch operators', 'error');
      console.error(error);
      setOperators([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteOperator = async (operatorId, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this operator?')) return;
    
    try {
      await api.delete(`/distributions/operators/${operatorId}`);
      showToast('Operator deleted successfully', 'success');
      fetchOperators();
      fetchSubDistribution(); // Refresh count
    } catch (error) {
      showToast('Failed to delete operator', 'error');
      console.error(error);
    }
  };

  if (!subDistribution) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Breadcrumb */}
      <div className="flex items-center gap-3">
        <Button
          variant="secondary"
          size="sm"
          icon={ArrowLeft}
          onClick={() => navigate(`/distributions/${subDistribution.parent_distribution_id}`)}
        >
          Back
        </Button>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Building2 className="w-4 h-4" />
          <span>{subDistribution.parent_distribution_name}</span>
          <span>/</span>
          <Users className="w-4 h-4" />
          <span className="font-semibold text-gray-800">{subDistribution.name}</span>
        </div>
      </div>

      {/* Sub-Distribution Info Card */}
      <Card>
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <Users className="w-8 h-8 text-green-600" />
            <div>
              <h1 className="text-2xl font-bold text-gray-800">{subDistribution.name}</h1>
              <p className="text-sm text-gray-500">{subDistribution.sub_distribution_id}</p>
            </div>
          </div>
          <StatusBadge status={subDistribution.status} />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {subDistribution.location && (
            <div className="flex items-center gap-2 text-gray-600">
              <MapPin className="w-5 h-5" />
              <span>{subDistribution.location}</span>
            </div>
          )}
          {subDistribution.contact_person && (
            <div className="flex items-center gap-2 text-gray-600">
              <User className="w-5 h-5" />
              <span>{subDistribution.contact_person}</span>
            </div>
          )}
          {subDistribution.contact_number && (
            <div className="flex items-center gap-2 text-gray-600">
              <Phone className="w-5 h-5" />
              <span>{subDistribution.contact_number}</span>
            </div>
          )}
          {subDistribution.email && (
            <div className="flex items-center gap-2 text-gray-600">
              <Mail className="w-5 h-5" />
              <span>{subDistribution.email}</span>
            </div>
          )}
        </div>

        {subDistribution.notes && (
          <div className="mt-4 pt-4 border-t">
            <p className="text-sm text-gray-600">{subDistribution.notes}</p>
          </div>
        )}

        <div className="mt-4 pt-4 border-t">
          <div className="flex items-center gap-6 text-sm">
            <div className="flex items-center gap-2 text-gray-600">
              <User className="w-4 h-4" />
              <span>{subDistribution.operator_count} Operators</span>
            </div>
            <div className="flex items-center gap-2 text-gray-600">
              <Package className="w-4 h-4" />
              <span>{subDistribution.device_count} Devices</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Operators Section */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-800">Operators</h2>
          <p className="text-gray-500 mt-1">Manage operators under {subDistribution.name}</p>
        </div>
        {canManage && (
          <Button 
            icon={Plus} 
            onClick={() => navigate('/distributions/create', { 
              state: { 
                entityType: 'operator', 
                parentSubDistId: subDistribution.id,
                parentSubDistName: subDistribution.name
              } 
            })}
          >
            Create Operator
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
            {operators.map(operator => (
              <Card key={operator.id}>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <User className="w-5 h-5 text-purple-600" />
                    <h3 className="font-semibold text-gray-800">{operator.name}</h3>
                  </div>
                  <StatusBadge status={operator.status} size="sm" />
                </div>

                <div className="space-y-2 mb-3">
                  {operator.location && (
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <MapPin className="w-4 h-4" />
                      <span>{operator.location}</span>
                    </div>
                  )}
                  {operator.contact_number && (
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <Phone className="w-4 h-4" />
                      <span>{operator.contact_number}</span>
                    </div>
                  )}
                  {operator.email && (
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <Mail className="w-4 h-4" />
                      <span>{operator.email}</span>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                  <div className="flex items-center gap-1 text-sm text-gray-500">
                    <Package className="w-4 h-4" />
                    <span>{operator.device_count} Devices</span>
                  </div>
                  
                  {canManage && (
                    <button
                      onClick={(e) => handleDeleteOperator(operator.id, e)}
                      className="p-1 text-red-600 hover:bg-red-50 rounded"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </Card>
            ))}
          </div>

          {operators.length === 0 && (
            <div className="text-center py-12">
              <User className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No operators found</p>
              {canManage && (
                <Button 
                  className="mt-4" 
                  onClick={() => navigate('/distributions/create', { 
                    state: { 
                      entityType: 'operator',
                      parentSubDistId: subDistribution.id,
                      parentSubDistName: subDistribution.name
                    } 
                  })}
                >
                  Create First Operator
                </Button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default SubDistributionDetail;

