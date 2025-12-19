const Card = ({ 
  children, 
  className = '', 
  title, 
  subtitle, 
  icon: Icon, 
  action,
  padding = true 
}) => {
  return (
    <div className={`bg-white rounded-xl shadow-sm border border-gray-200 ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            {Icon && (
              <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                <Icon className="w-5 h-5 text-blue-600" />
              </div>
            )}
            <div>
              {title && <h3 className="text-lg font-semibold text-gray-800">{title}</h3>}
              {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
            </div>
          </div>
          {action}
        </div>
      )}
      <div className={padding ? 'p-6' : ''}>{children}</div>
    </div>
  );
};

export default Card;
