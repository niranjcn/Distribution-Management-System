const Input = ({ 
  label, 
  error, 
  helperText,
  className = '',
  ...props 
}) => {
  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-gray-600 mb-1.5">
          {label}
          {props.required && <span className="text-red-500 ml-1">*</span>}
        </label>
      )}
      <input
        className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-green-500/20 focus:border-green-600 transition-colors ${
          error ? 'border-red-300 bg-red-50 text-red-900' : 'border-gray-300 bg-white text-gray-800'
        }`}
        {...props}
      />
      {error && (
        <p className="mt-1 text-sm text-red-600">{error}</p>
      )}
      {helperText && !error && (
        <p className="mt-1 text-sm text-gray-400">{helperText}</p>
      )}
    </div>
  );
};

export default Input;
