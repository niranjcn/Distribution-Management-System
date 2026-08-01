import Card from './Card';
import Button from './Button';
import { Search } from 'lucide-react';

const SEARCH_BY_OPTIONS = [
  { value: 'all', label: 'All Fields' },
  { value: 'name', label: 'Name' },
  { value: 'email', label: 'Email' },
  { value: 'phone', label: 'Phone' },
  { value: 'digital_id', label: 'Digital ID' },
  { value: 'broadband_id', label: 'Broadband ID' },
];

const ReportFilter = ({ searchBy, searchInput, onSearchByChange, onSearchInputChange, onSearch, onReset }) => (
  <Card className="!p-4">
    <div className="flex items-center gap-2 mb-3">
      <Search className="w-4 h-4 text-blue-600" />
      <h3 className="text-sm font-semibold text-gray-800">Filter Report</h3>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
      <div className="md:col-span-3">
        <select
          value={searchBy}
          onChange={(e) => onSearchByChange(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
        >
          {SEARCH_BY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </div>
      <div className="md:col-span-6">
        <input
          type="text"
          value={searchInput}
          onChange={(e) => onSearchInputChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              onSearch();
            }
          }}
          placeholder="Enter pattern to search..."
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
        />
      </div>
      <div className="md:col-span-3 flex gap-2">
        <Button onClick={onSearch} className="w-full">Search</Button>
        <Button variant="secondary" onClick={onReset}>Reset</Button>
      </div>
    </div>
  </Card>
);

export default ReportFilter;
