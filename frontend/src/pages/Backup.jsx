import { useEffect, useState } from 'react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { reportsAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { Download, Database, FileSpreadsheet, FileText, Upload, FileArchive, RefreshCw } from 'lucide-react';

const Backup = () => {
  const { showToast } = useNotifications();
  const [format, setFormat] = useState('xlsx');
  const [downloadingDevices, setDownloadingDevices] = useState(false);
  const [downloadingTracking, setDownloadingTracking] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [uploadingDocument, setUploadingDocument] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [dbSchedule, setDbSchedule] = useState({
    frequency: 'daily',
    day_of_week: 0,
    day_of_month: 1,
    time_of_day: '02:00',
    last_run_at: null,
  });
  const [loadingDbSchedule, setLoadingDbSchedule] = useState(false);
  const [savingDbSchedule, setSavingDbSchedule] = useState(false);
  // ===== TEST HELPER: trigger monthly backup (remove when done) =====
  const [triggeringBackup, setTriggeringBackup] = useState(false);
  // ===== END TEST HELPER =====

  const weekDays = [
    { value: 0, label: 'Monday' },
    { value: 1, label: 'Tuesday' },
    { value: 2, label: 'Wednesday' },
    { value: 3, label: 'Thursday' },
    { value: 4, label: 'Friday' },
    { value: 5, label: 'Saturday' },
    { value: 6, label: 'Sunday' },
  ];
  const monthDays = Array.from({ length: 31 }, (_, index) => index + 1);

  const extractFilename = (contentDisposition, fallback) => {
    const match = /filename="?([^\";]+)"?/i.exec(contentDisposition || '');
    return (match && match[1]) || fallback;
  };

  const downloadBlob = (blob, filename) => {
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(url);
  };

  const formatFileSize = (bytes = 0) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const loadDocuments = async () => {
    setLoadingDocuments(true);
    try {
      const response = await reportsAPI.listBackupDocuments();
      setDocuments(Array.isArray(response?.data) ? response.data : []);
    } catch (error) {
      showToast(error.message || 'Failed to load backup documents', 'error');
    } finally {
      setLoadingDocuments(false);
    }
  };

  const loadDbSchedule = async () => {
    setLoadingDbSchedule(true);
    try {
      const response = await reportsAPI.getDbBackupSchedule();
      if (response?.data) {
        setDbSchedule({
          frequency: response.data.frequency || 'daily',
          day_of_week: response.data.day_of_week ?? 0,
          day_of_month: response.data.day_of_month ?? 1,
          time_of_day: response.data.time_of_day || '02:00',
          last_run_at: response.data.last_run_at || null,
        });
      }
    } catch (error) {
      showToast(error.message || 'Failed to load database backup schedule', 'error');
    } finally {
      setLoadingDbSchedule(false);
    }
  };

  const handleSaveDbSchedule = async () => {
    setSavingDbSchedule(true);
    try {
      const payload = {
        frequency: dbSchedule.frequency,
        day_of_week: dbSchedule.frequency === 'weekly' ? dbSchedule.day_of_week : null,
        day_of_month: dbSchedule.frequency === 'monthly' ? dbSchedule.day_of_month : null,
        time_of_day: dbSchedule.time_of_day,
      };
      const response = await reportsAPI.updateDbBackupSchedule(payload);
      if (response?.data) {
        setDbSchedule({
          frequency: response.data.frequency || 'daily',
          day_of_week: response.data.day_of_week ?? 0,
          day_of_month: response.data.day_of_month ?? 1,
          time_of_day: response.data.time_of_day || '02:00',
          last_run_at: response.data.last_run_at || null,
        });
      }
      showToast('Database backup schedule updated', 'success');
    } catch (error) {
      showToast(error.message || 'Failed to update database backup schedule', 'error');
    } finally {
      setSavingDbSchedule(false);
    }
  };

  const handleDeviceBackupDownload = async () => {
    setDownloadingDevices(true);
    try {
      const { blob, contentDisposition } = await reportsAPI.downloadDeviceBackup(format);
      const fallbackName = `device-backup.${format}`;
      const fileName = extractFilename(contentDisposition, fallbackName);
      downloadBlob(blob, fileName);

      showToast('Backup generated and downloaded successfully', 'success');
    } catch (error) {
      showToast(error.message || 'Failed to download backup', 'error');
    } finally {
      setDownloadingDevices(false);
    }
  };

  const handleTrackingBackupDownload = async () => {
    setDownloadingTracking(true);
    try {
      const { blob, contentDisposition } = await reportsAPI.downloadReturnsDefectsBackup(format);
      const fallbackName = `returns-defects-backup.${format}`;
      const fileName = extractFilename(contentDisposition, fallbackName);
      downloadBlob(blob, fileName);

      showToast('Returns and defects backup downloaded successfully', 'success');
    } catch (error) {
      showToast(error.message || 'Failed to download returns/defects backup', 'error');
    } finally {
      setDownloadingTracking(false);
    }
  };

  const handleUploadDocument = async () => {
    if (!selectedFile) {
      showToast('Please choose a file first', 'error');
      return;
    }

    setUploadingDocument(true);
    try {
      await reportsAPI.uploadBackupDocument(selectedFile);
      showToast('File uploaded successfully', 'success');
      setSelectedFile(null);
      await loadDocuments();
    } catch (error) {
      showToast(error.message || 'Failed to upload file', 'error');
    } finally {
      setUploadingDocument(false);
    }
  };

  const handleDownloadDocument = async (storedName, fallbackFileName) => {
    try {
      const { blob, contentDisposition } = await reportsAPI.downloadBackupDocument(storedName);
      const fileName = extractFilename(contentDisposition, fallbackFileName);
      downloadBlob(blob, fileName);
      showToast('File downloaded successfully', 'success');
    } catch (error) {
      showToast(error.message || 'Failed to download file', 'error');
    }
  };

  // ===== TEST HELPER: trigger monthly backup (remove when done) =====
  const handleTriggerMonthlyBackup = async () => {
    setTriggeringBackup(true);
    try {
      const response = await reportsAPI.triggerMonthlyBackup();
      const month = response?.data?.month || '';
      showToast(`Monthly backup generated${month ? ` (${month})` : ''} successfully`, 'success');
    } catch (error) {
      showToast(error.message || 'Failed to trigger monthly backup', 'error');
    } finally {
      setTriggeringBackup(false);
    }
  };
  // ===== END TEST HELPER =====

  useEffect(() => {
    loadDocuments();
    loadDbSchedule();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Backup</h1>
        <p className="text-gray-500">
          Download a full backup of all devices including journey path from source to current location.
        </p>
      </div>

      {/* ===== TEST HELPER: Trigger Monthly Backup (remove when done) ===== */}
      <Card>
        <div className="space-y-4">
          <div className="flex items-start gap-3 text-gray-700">
            <Database className="w-5 h-5 mt-0.5 text-violet-600" />
            <div>
              <p className="font-medium">Trigger Monthly Backup</p>
              <p className="text-sm text-gray-500 mt-1">
                Generate and upload this month&apos;s device + returns/defects backup to Google Drive now.
                Testing only — the scheduler normally runs this on the 1st of each month.
              </p>
            </div>
          </div>
          <div className="pt-1">
            <Button icon={RefreshCw} loading={triggeringBackup} onClick={handleTriggerMonthlyBackup}>
              {triggeringBackup ? 'Generating Monthly Backup...' : 'Trigger Monthly Backup'}
            </Button>
          </div>
        </div>
      </Card>
      {/* ===== END TEST HELPER ===== */}

      <Card>
        <div className="space-y-5">
          <div className="flex items-start gap-3 text-gray-700">
            <Database className="w-5 h-5 mt-0.5 text-blue-600" />
            <div>
              <p className="font-medium">Included in backup</p>
              <p className="text-sm text-gray-500 mt-1">
                Device details, starting point, path traversed through hierarchy levels, and current location.
              </p>
            </div>
          </div>

          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">File format</p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setFormat('xlsx')}
                className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors ${
                  format === 'xlsx'
                    ? 'border-blue-600 bg-blue-50 text-blue-700'
                    : 'border-gray-300 text-gray-600 hover:bg-gray-50'
                }`}
              >
                <FileSpreadsheet className="w-4 h-4" />
                XLSX
              </button>
              <button
                type="button"
                onClick={() => setFormat('csv')}
                className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors ${
                  format === 'csv'
                    ? 'border-blue-600 bg-blue-50 text-blue-700'
                    : 'border-gray-300 text-gray-600 hover:bg-gray-50'
                }`}
              >
                <FileText className="w-4 h-4" />
                CSV
              </button>
            </div>
          </div>

          <div className="pt-2">
            <Button icon={Download} loading={downloadingDevices} onClick={handleDeviceBackupDownload}>
              {downloadingDevices ? 'Generating Device Backup...' : 'Download Device Backup'}
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <div className="space-y-5">
          <div className="flex items-start gap-3 text-gray-700">
            <Database className="w-5 h-5 mt-0.5 text-orange-600" />
            <div>
              <p className="font-medium">Returns and defects tracking backup</p>
              <p className="text-sm text-gray-500 mt-1">
                Downloads a separate file containing all return records and defect reports for audit and tracking.
              </p>
            </div>
          </div>

          <div className="pt-2">
            <Button icon={Download} loading={downloadingTracking} onClick={handleTrackingBackupDownload}>
              {downloadingTracking ? 'Generating Tracking Backup...' : 'Download Returns + Defects Backup'}
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <div className="space-y-5">
          <div className="flex items-start gap-3 text-gray-700">
            <Database className="w-5 h-5 mt-0.5 text-emerald-600" />
            <div>
              <p className="font-medium">MySQL database backup</p>
              <p className="text-sm text-gray-500 mt-1">
                Schedule full database dumps and upload them to Google Drive via rclone. Time uses the backend container clock.
              </p>
            </div>
          </div>

          {loadingDbSchedule ? (
            <p className="text-sm text-gray-500">Loading backup schedule...</p>
          ) : (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-3">
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-2">Frequency</p>
                  <select
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={dbSchedule.frequency}
                    onChange={(event) =>
                      setDbSchedule((prev) => ({
                        ...prev,
                        frequency: event.target.value,
                      }))
                    }
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>

                <div>
                  <p className="text-sm font-medium text-gray-700 mb-2">Time of day</p>
                  <input
                    type="time"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={dbSchedule.time_of_day}
                    onChange={(event) =>
                      setDbSchedule((prev) => ({
                        ...prev,
                        time_of_day: event.target.value,
                      }))
                    }
                  />
                </div>

                {dbSchedule.frequency === 'weekly' && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">Day of week</p>
                    <select
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      value={dbSchedule.day_of_week}
                      onChange={(event) =>
                        setDbSchedule((prev) => ({
                          ...prev,
                          day_of_week: Number(event.target.value),
                        }))
                      }
                    >
                      {weekDays.map((day) => (
                        <option key={day.value} value={day.value}>
                          {day.label}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {dbSchedule.frequency === 'monthly' && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">Day of month</p>
                    <select
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      value={dbSchedule.day_of_month}
                      onChange={(event) =>
                        setDbSchedule((prev) => ({
                          ...prev,
                          day_of_month: Number(event.target.value),
                        }))
                      }
                    >
                      {monthDays.map((day) => (
                        <option key={day} value={day}>
                          {day}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <Button
                  icon={RefreshCw}
                  loading={savingDbSchedule}
                  onClick={handleSaveDbSchedule}
                  disabled={savingDbSchedule}
                >
                  {savingDbSchedule ? 'Saving...' : 'Save Schedule'}
                </Button>
                <p className="text-xs text-gray-500">
                  {dbSchedule.last_run_at
                    ? `Last run: ${new Date(dbSchedule.last_run_at).toLocaleString()}`
                    : 'Last run: Not yet'}
                </p>
              </div>
            </div>
          )}
        </div>
      </Card>

      <Card>
        <div className="space-y-5">
          <div className="flex items-start gap-3 text-gray-700">
            <FileArchive className="w-5 h-5 mt-0.5 text-emerald-600" />
            <div>
              <p className="font-medium">Backup document vault</p>
              <p className="text-sm text-gray-500 mt-1">
                Upload important backup files and download them later. Access is restricted to Super Admin, Manager, and MD/Director.
              </p>
            </div>
          </div>

          <div className="border border-gray-200 rounded-lg p-4 space-y-3 bg-white/60">
            <p className="text-sm font-medium text-gray-700">Upload file</p>
            <input
              type="file"
              onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
              className="block w-full text-sm text-gray-600 file:mr-3 file:rounded-md file:border file:border-gray-300 file:bg-white file:px-3 file:py-1.5 file:text-sm file:text-gray-700 hover:file:bg-gray-50"
            />
            <div className="flex flex-wrap gap-2">
              <Button
                icon={Upload}
                loading={uploadingDocument}
                onClick={handleUploadDocument}
                disabled={!selectedFile || uploadingDocument}
              >
                {uploadingDocument ? 'Uploading...' : 'Upload to Vault'}
              </Button>
              <Button
                variant="outline"
                icon={RefreshCw}
                onClick={loadDocuments}
                disabled={loadingDocuments}
              >
                Refresh List
              </Button>
            </div>
          </div>

          <div className="border border-gray-200 rounded-lg divide-y divide-gray-200 bg-white/60">
            <div className="px-4 py-3 flex items-center justify-between">
              <p className="text-sm font-medium text-gray-700">Stored files</p>
              <span className="text-xs text-gray-500">{documents.length} file(s)</span>
            </div>

            {loadingDocuments ? (
              <p className="px-4 py-6 text-sm text-gray-500">Loading files...</p>
            ) : documents.length === 0 ? (
              <p className="px-4 py-6 text-sm text-gray-500">No files uploaded yet.</p>
            ) : (
              documents.map((doc) => (
                <div key={doc.stored_name} className="px-4 py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-gray-800 break-all">{doc.file_name}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {formatFileSize(doc.size)} • {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleString() : 'Unknown date'}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    icon={Download}
                    onClick={() => handleDownloadDocument(doc.stored_name, doc.file_name)}
                  >
                    Download
                  </Button>
                </div>
              ))
            )}
          </div>
        </div>
      </Card>
    </div>
  );
};

export default Backup;
