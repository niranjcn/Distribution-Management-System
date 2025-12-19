import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import Card from '../components/ui/Card';
import StatusBadge from '../components/ui/StatusBadge';
import Timeline from '../components/ui/Timeline';
import Button from '../components/ui/Button';
import { devices, deviceHistory } from '../data/mockData';
import { Search, Box, MapPin, Clock, User, Download, ChevronRight } from 'lucide-react';

const TrackDevice = () => {
  const [searchParams] = useSearchParams();
  const initialQuery = searchParams.get('q') || searchParams.get('mac') || '';
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [searchResult, setSearchResult] = useState(initialQuery ? findDevice(initialQuery) : null);
  const [searched, setSearched] = useState(!!initialQuery);

  function findDevice(query) {
    return devices.find(d => 
      d.macAddress.toLowerCase().includes(query.toLowerCase()) ||
      d.serialNumber.toLowerCase().includes(query.toLowerCase()) ||
      d.id.toLowerCase() === query.toLowerCase()
    );
  }

  const handleSearch = (e) => {
    e.preventDefault();
    setSearched(true);
    setSearchResult(findDevice(searchQuery));
  };

  const getDeviceHistory = (deviceId) => {
    const history = deviceHistory[deviceId];
    if (!history) return [];
    return history.map((item, index) => ({
      title: item.action,
      description: item.notes,
      timestamp: item.timestamp,
      user: item.user,
      status: index === history.length - 1 ? 'current' : 'completed'
    }));
  };

  const getLocationColor = (location) => {
    switch (location) {
      case 'main-distribution': return 'bg-blue-100 text-blue-800';
      case 'sub-distributor': return 'bg-purple-100 text-purple-800';
      case 'operator': return 'bg-green-100 text-green-800';
      case 'in-transit': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Track Device</h1>
        <p className="text-gray-500 mt-1">Search and track device journey through the distribution chain</p>
      </div>

      {/* Search Form */}
      <Card>
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter MAC address, serial number, or device ID..."
              className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <Button type="submit" size="lg">
            Track Device
          </Button>
        </form>

        {/* Quick Search Examples */}
        <div className="mt-4 pt-4 border-t border-gray-100">
          <p className="text-sm text-gray-500 mb-2">Try these examples:</p>
          <div className="flex flex-wrap gap-2">
            {['AA:BB:CC:DD:EE:01', 'AA:BB:CC:DD:EE:02', 'SN-2024-001'].map(example => (
              <button
                key={example}
                type="button"
                onClick={() => {
                  setSearchQuery(example);
                  setSearched(true);
                  setSearchResult(findDevice(example));
                }}
                className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded-full text-gray-700"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Search Results */}
      {searched && (
        <>
          {searchResult ? (
            <div className="space-y-6">
              {/* Device Info Card */}
              <Card>
                <div className="flex flex-col lg:flex-row lg:items-start gap-6">
                  <div className="flex items-center gap-4">
                    <div className="w-20 h-20 bg-blue-100 rounded-xl flex items-center justify-center">
                      <Box className="w-10 h-10 text-blue-600" />
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-gray-800">{searchResult.model}</h2>
                      <p className="text-gray-500">{searchResult.manufacturer}</p>
                      <div className="flex gap-2 mt-2">
                        <StatusBadge status={searchResult.condition} />
                        <StatusBadge status={searchResult.status} />
                      </div>
                    </div>
                  </div>

                  <div className="flex-1 grid grid-cols-2 lg:grid-cols-4 gap-4 lg:border-l lg:border-gray-200 lg:pl-6">
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wider">MAC Address</p>
                      <p className="font-mono font-medium text-gray-800">{searchResult.macAddress}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wider">Serial Number</p>
                      <p className="font-medium text-gray-800">{searchResult.serialNumber}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wider">Hardware Ver.</p>
                      <p className="font-medium text-gray-800">{searchResult.hardwareVersion}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wider">Firmware Ver.</p>
                      <p className="font-medium text-gray-800">{searchResult.firmwareVersion}</p>
                    </div>
                  </div>
                </div>
              </Card>

              {/* Current Location */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <Card className="lg:col-span-1">
                  <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
                    <MapPin className="w-5 h-5 text-gray-500" />
                    Current Location
                  </h3>
                  <div className={`p-4 rounded-lg ${getLocationColor(searchResult.currentLocation)}`}>
                    <p className="text-sm font-medium uppercase tracking-wider opacity-75">
                      {searchResult.currentLocation.replace('-', ' ')}
                    </p>
                    <p className="text-lg font-bold mt-1">{searchResult.currentHolder}</p>
                  </div>

                  <div className="mt-4 space-y-3">
                    <div className="flex items-center gap-3 text-sm">
                      <Clock className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-600">Registered: {searchResult.registeredAt}</span>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <User className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-600">By: {searchResult.registeredBy}</span>
                    </div>
                  </div>

                  <Button variant="outline" className="w-full mt-4" icon={Download}>
                    Export History
                  </Button>
                </Card>

                {/* Device Journey */}
                <Card className="lg:col-span-2">
                  <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
                    <Clock className="w-5 h-5 text-gray-500" />
                    Device Journey
                  </h3>
                  
                  {deviceHistory[searchResult.id] ? (
                    <Timeline items={getDeviceHistory(searchResult.id)} />
                  ) : (
                    <div className="text-center py-8">
                      <Clock className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                      <p className="text-gray-500">No journey history available for this device</p>
                    </div>
                  )}
                </Card>
              </div>

              {/* Distribution Flow */}
              <Card title="Distribution Flow">
                <div className="flex flex-col sm:flex-row items-center justify-center gap-4 py-4">
                  <div className="text-center">
                    <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto">
                      <Box className="w-8 h-8 text-blue-600" />
                    </div>
                    <p className="text-sm font-medium text-gray-800 mt-2">NOC</p>
                    <p className="text-xs text-gray-500">Source</p>
                  </div>
                  
                  <ChevronRight className="w-6 h-6 text-gray-300 rotate-90 sm:rotate-0" />
                  
                  <div className={`text-center ${searchResult.currentLocation === 'main-distribution' ? 'ring-2 ring-blue-500 rounded-lg p-2' : ''}`}>
                    <div className="w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center mx-auto">
                      <Box className="w-8 h-8 text-indigo-600" />
                    </div>
                    <p className="text-sm font-medium text-gray-800 mt-2">Main Dist.</p>
                    <p className="text-xs text-gray-500">Distribution</p>
                  </div>
                  
                  <ChevronRight className="w-6 h-6 text-gray-300 rotate-90 sm:rotate-0" />
                  
                  <div className={`text-center ${searchResult.currentLocation === 'sub-distributor' ? 'ring-2 ring-blue-500 rounded-lg p-2' : ''}`}>
                    <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto">
                      <Box className="w-8 h-8 text-purple-600" />
                    </div>
                    <p className="text-sm font-medium text-gray-800 mt-2">Sub Dist.</p>
                    <p className="text-xs text-gray-500">Regional</p>
                  </div>
                  
                  <ChevronRight className="w-6 h-6 text-gray-300 rotate-90 sm:rotate-0" />
                  
                  <div className={`text-center ${searchResult.currentLocation === 'operator' ? 'ring-2 ring-blue-500 rounded-lg p-2' : ''}`}>
                    <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto">
                      <User className="w-8 h-8 text-green-600" />
                    </div>
                    <p className="text-sm font-medium text-gray-800 mt-2">Operator</p>
                    <p className="text-xs text-gray-500">End User</p>
                  </div>
                </div>
              </Card>
            </div>
          ) : (
            <Card>
              <div className="text-center py-12">
                <Box className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-800 mb-2">No Device Found</h3>
                <p className="text-gray-500 max-w-md mx-auto">
                  We couldn't find a device matching "{searchQuery}". Please check the MAC address, 
                  serial number, or device ID and try again.
                </p>
              </div>
            </Card>
          )}
        </>
      )}

      {!searched && (
        <Card>
          <div className="text-center py-12">
            <Search className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-800 mb-2">Track Your Device</h3>
            <p className="text-gray-500 max-w-md mx-auto">
              Enter a MAC address, serial number, or device ID above to track the device's 
              journey through the distribution chain.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
};

export default TrackDevice;
