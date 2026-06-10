import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import Input from '../components/ui/Input';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { Package, Plus, Edit, Trash2, Box } from 'lucide-react';
import { batchesAPI } from '../services/api';

const ViewBatches = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useNotifications();
  
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showBatchModal, setShowBatchModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [editingBatch, setEditingBatch] = useState(null);
  
  const [batchForm, setBatchForm] = useState({
    name: '',
    description: ''
  });

  const canManage = ['super_admin', 'distributor'].includes(user?.role);

  useEffect(() => {
    loadBatches();
  }, []);

  const loadBatches = async () => {
    try {
      setLoading(true);
      const response = await batchesAPI.getBatches();
      if (response.success) {
        setBatches(response.data);
      }
    } catch (error) {
      showToast(error.message || 'Failed to load batches', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateBatch = async (e) => {
    e.preventDefault();
    
    if (!batchForm.name.trim()) {
      showToast('Batch name is required', 'error');
      return;
    }

    try {
      if (editingBatch) {
        // Update existing batch
        const response = await batchesAPI.updateBatch(editingBatch.id, batchForm);
        if (response.success) {
          showToast('Batch updated successfully', 'success');
        }
      } else {
        // Create new batch
        const response = await batchesAPI.createBatch(batchForm);
        if (response.success) {
          showToast('Batch created successfully', 'success');
        }
      }
      
      setShowBatchModal(false);
      setBatchForm({ name: '', description: '' });
      setEditingBatch(null);
      await loadBatches();
    } catch (error) {
      showToast(error.message || 'Failed to save batch', 'error');
    }
  };

  const handleEditBatch = (batch) => {
    setEditingBatch(batch);
    setBatchForm({
      name: batch.name,
      description: batch.description || ''
    });
    setShowBatchModal(true);
  };

  const handleDeleteBatch = async () => {
    try {
      const response = await batchesAPI.deleteBatch(editingBatch.id);
      if (response.success) {
        showToast('Batch deleted successfully', 'success');
        setShowDeleteModal(false);
        setEditingBatch(null);
        await loadBatches();
      }
    } catch (error) {
      showToast(error.message || 'Failed to delete batch. Make sure all devices are removed first.', 'error');
    }
  };

  const handleBatchClick = (batch) => {
    // Navigate to devices page with the selected batch
    navigate(`/devices?batchId=${batch.id}`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading batches...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">All Batches</h1>
          <p className="text-gray-500 mt-1 text-sm sm:text-base">
            Manage device batches and collections
          </p>
        </div>
        {canManage && (
          <Button 
            icon={Plus}
            onClick={() => {
              setEditingBatch(null);
              setBatchForm({ name: '', description: '' });
              setShowBatchModal(true);
            }}
            className="w-full sm:w-auto"
          >
            Create Batch
          </Button>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Total Batches</p>
          <p className="text-2xl font-bold text-gray-800">{batches.length}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Total Devices</p>
          <p className="text-2xl font-bold text-blue-600">
            {batches.reduce((sum, batch) => sum + batch.device_count, 0)}
          </p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Average Devices/Batch</p>
          <p className="text-2xl font-bold text-green-600">
            {batches.length > 0 
              ? Math.round(batches.reduce((sum, batch) => sum + batch.device_count, 0) / batches.length)
              : 0
            }
          </p>
        </Card>
      </div>

      {/* Batches Grid */}
      {batches.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {batches.map((batch) => (
            <Card 
              key={batch.id}
              className="!p-0 overflow-hidden hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => handleBatchClick(batch)}
            >
              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                      <Package className="w-6 h-6 text-blue-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-800 text-lg">{batch.name}</h3>
                      <p className="text-sm text-gray-500">{batch.batch_id}</p>
                    </div>
                  </div>
                </div>
                
                {batch.description && (
                  <p className="text-sm text-gray-600 mb-4 line-clamp-2">
                    {batch.description}
                  </p>
                )}
                
                <div className="flex items-center justify-between pt-4 border-t border-gray-100">
                  <div className="flex items-center gap-2 text-gray-600">
                    <Box className="w-4 h-4" />
                    <span className="text-sm font-medium">{batch.device_count} devices</span>
                  </div>
                  
                  {canManage && (
                    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => handleEditBatch(batch)}
                        className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                        title="Edit Batch"
                      >
                        <Edit className="w-4 h-4 text-gray-600" />
                      </button>
                      <button
                        onClick={() => {
                          setEditingBatch(batch);
                          setShowDeleteModal(true);
                        }}
                        className="p-2 hover:bg-red-50 rounded-lg transition-colors"
                        title="Delete Batch"
                      >
                        <Trash2 className="w-4 h-4 text-red-600" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
              
              <div className="bg-gray-50 px-6 py-3 text-xs text-gray-500">
                Created by {batch.created_by_name} • {new Date(batch.created_at).toLocaleDateString()}
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="!p-8 text-center">
          <Package className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-800 mb-2">No Batches Yet</h3>
          <p className="text-gray-600 mb-4">Create your first batch to start organizing devices</p>
          {canManage && (
            <Button 
              icon={Plus}
              onClick={() => {
                setEditingBatch(null);
                setBatchForm({ name: '', description: '' });
                setShowBatchModal(true);
              }}
            >
              Create First Batch
            </Button>
          )}
        </Card>
      )}

      {/* Create/Edit Batch Modal */}
      <Modal
        isOpen={showBatchModal}
        onClose={() => {
          setShowBatchModal(false);
          setBatchForm({ name: '', description: '' });
          setEditingBatch(null);
        }}
        title={editingBatch ? 'Edit Batch' : 'Create New Batch'}
        size="md"
      >
        <form onSubmit={handleCreateBatch} className="space-y-4">
          <Input
            label="Batch Name"
            value={batchForm.name}
            onChange={(e) => setBatchForm({ ...batchForm, name: e.target.value })}
            placeholder="e.g., January 2026 Shipment"
            required
          />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description (Optional)
            </label>
            <textarea
              value={batchForm.description}
              onChange={(e) => setBatchForm({ ...batchForm, description: e.target.value })}
              placeholder="Add notes about this batch..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              rows="3"
            />
          </div>
          <div className="flex justify-end gap-2 pt-4">
            <Button 
              type="button"
              variant="secondary" 
              onClick={() => {
                setShowBatchModal(false);
                setBatchForm({ name: '', description: '' });
                setEditingBatch(null);
              }}
            >
              Cancel
            </Button>
            <Button type="submit">
              {editingBatch ? 'Update Batch' : 'Create Batch'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Batch Modal */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => {
          setShowDeleteModal(false);
          setEditingBatch(null);
        }}
        title="Delete Batch"
        size="sm"
        footer={
          <>
            <Button 
              variant="secondary" 
              onClick={() => {
                setShowDeleteModal(false);
                setEditingBatch(null);
              }}
            >
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDeleteBatch}>Delete</Button>
          </>
        }
      >
        <p className="text-gray-600">
          Are you sure you want to delete batch <span className="font-medium">{editingBatch?.name}</span>? 
          This action cannot be undone. All devices must be removed from this batch first.
        </p>
      </Modal>
    </div>
  );
};

export default ViewBatches;

