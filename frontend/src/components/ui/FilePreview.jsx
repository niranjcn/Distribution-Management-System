import { useEffect, useState, useCallback } from 'react';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';
import Card from './Card';
import { Table } from 'lucide-react';

const FilePreview = ({ file }) => {
  const [headers, setHeaders] = useState([]);
  const [allRows, setAllRows] = useState([]);
  const [visibleRowCount, setVisibleRowCount] = useState(20);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!file) {
      setHeaders([]);
      setAllRows([]);
      setVisibleRowCount(20);
      return;
    }

    const parseFile = async () => {
      setLoading(true);
      setError(null);
      setVisibleRowCount(20);
      
      try {
        const fileName = file.name.toLowerCase();
        if (fileName.endsWith('.csv')) {
          Papa.parse(file, {
            header: true,
            skipEmptyLines: true,
            complete: (results) => {
              if (results.meta && results.meta.fields) {
                setHeaders(results.meta.fields);
                setAllRows(results.data);
              } else if (results.data && results.data.length > 0) {
                // Fallback if no headers parsed properly
                setHeaders(Object.keys(results.data[0]));
                setAllRows(results.data);
              }
              setLoading(false);
            },
            error: (err) => {
              setError(err.message || 'Failed to parse CSV');
              setLoading(false);
            }
          });
        } else if (fileName.endsWith('.xlsx') || fileName.endsWith('.xls')) {
          const reader = new FileReader();
          reader.onload = (e) => {
            try {
              const data = new Uint8Array(e.target.result);
              const workbook = XLSX.read(data, { type: 'array' });
              const firstSheetName = workbook.SheetNames[0];
              const worksheet = workbook.Sheets[firstSheetName];
              const json = XLSX.utils.sheet_to_json(worksheet, { defval: '' });
              
              if (json && json.length > 0) {
                setHeaders(Object.keys(json[0]));
                setAllRows(json);
              }
              setLoading(false);
            } catch (err) {
              setError('Failed to parse Excel file');
              setLoading(false);
            }
          };
          reader.onerror = () => {
            setError('Failed to read file');
            setLoading(false);
          };
          reader.readAsArrayBuffer(file);
        } else {
          setError('Unsupported file type for preview');
          setLoading(false);
        }
      } catch (err) {
        setError('Error reading file');
        setLoading(false);
      }
    };

    parseFile();
  }, [file]);

  const handleScroll = useCallback((e) => {
    const { scrollTop, clientHeight, scrollHeight } = e.currentTarget;
    // If we've scrolled within 50px of the bottom, load more
    if (scrollHeight - scrollTop <= clientHeight + 50) {
      setVisibleRowCount(prev => Math.min(prev + 20, allRows.length));
    }
  }, [allRows.length]);

  if (!file) return null;

  return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        <Table className="w-5 h-5 text-gray-500" />
        <h3 className="font-semibold text-gray-800">File Preview</h3>
        {!loading && !error && allRows.length > 0 && (
          <span className="text-xs text-gray-400 ml-2">
            (Showing {Math.min(visibleRowCount, allRows.length)} of {allRows.length} rows)
          </span>
        )}
      </div>

      {loading && <p className="text-sm text-gray-500">Loading preview...</p>}
      
      {error && <p className="text-sm text-red-500">{error}</p>}

      {!loading && !error && allRows.length === 0 && (
        <p className="text-sm text-gray-500">No data found in the file.</p>
      )}

      {!loading && !error && allRows.length > 0 && (
        <div 
          className="overflow-x-auto overflow-y-auto max-h-96 rounded-lg border border-gray-200"
          onScroll={handleScroll}
        >
          <table className="w-full text-sm text-left text-gray-600 relative">
            <thead className="text-xs text-gray-700 uppercase bg-gray-50 border-b border-gray-200 sticky top-0 z-10 shadow-sm">
              <tr>
                {headers.map((header, idx) => (
                  <th key={idx} className="px-4 py-3 font-medium whitespace-nowrap">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {allRows.slice(0, visibleRowCount).map((row, rowIndex) => (
                <tr key={rowIndex} className="hover:bg-gray-50">
                  {headers.map((header, colIndex) => (
                    <td key={colIndex} className="px-4 py-2 whitespace-nowrap">
                      {row[header] !== undefined && row[header] !== null ? String(row[header]) : ''}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
};

export default FilePreview;
