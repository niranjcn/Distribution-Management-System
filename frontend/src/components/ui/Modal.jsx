import { X } from 'lucide-react';

const Modal = ({ isOpen, onClose, title, children, size = 'md', footer }) => {
  if (!isOpen) return null;

  const sizeClasses = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
    full: 'max-w-6xl',
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-end sm:items-center justify-center p-0 sm:p-4">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black/40 transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div
          className={`relative bg-white rounded-t-xl sm:rounded-xl shadow-xl w-full ${sizeClasses[size]} animate-fadeIn max-h-[90vh] sm:max-h-[85vh] flex flex-col border border-gray-200`}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-gray-200 flex-shrink-0">
            <h3 className="text-base sm:text-lg font-semibold text-gray-800">{title}</h3>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-400" />
            </button>
          </div>

          {/* Content */}
          <div className="px-4 sm:px-6 py-4 overflow-y-auto flex-1">{children}</div>

          {/* Footer */}
          {footer && (
            <div className="flex items-center justify-end gap-3 px-4 sm:px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-xl flex-shrink-0">
              {footer}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Modal;
