import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';

const Toast = ({ message, type = 'success', onClose }) => {
  const icons = {
    success: <CheckCircle className="w-5 h-5 text-green-600" />,
    error: <XCircle className="w-5 h-5 text-red-600" />,
    warning: <AlertTriangle className="w-5 h-5 text-orange-500" />,
    info: <Info className="w-5 h-5 text-blue-600" />,
  };

  const bgColors = {
    success: 'bg-green-50 border-green-200',
    error: 'bg-red-50 border-red-200',
    warning: 'bg-orange-50 border-orange-200',
    info: 'bg-blue-50 border-blue-200',
  };

  const textColors = {
    success: 'text-green-800',
    error: 'text-red-800',
    warning: 'text-orange-800',
    info: 'text-blue-800',
  };

  return (
    <div className={`flex items-center gap-3 px-4 py-3 rounded-lg border shadow-md animate-slideIn ${bgColors[type]}`}>
      {icons[type]}
      <p className={`text-sm font-medium ${textColors[type]}`}>{message}</p>
    </div>
  );
};

export default Toast;
