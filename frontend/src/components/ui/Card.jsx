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
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 sm:px-6 py-3 sm:py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            {Icon && (
              <div className="w-8 h-8 sm:w-10 sm:h-10 bg-green-50 rounded-lg flex items-center justify-center flex-shrink-0 border border-green-200">
                <Icon className="w-4 h-4 sm:w-5 sm:h-5 text-green-700" />
              </div>
            )}
            <div className="min-w-0">
              {title && <h3 className="text-base sm:text-lg font-semibold text-gray-800 truncate">{title}</h3>}
              {subtitle && <p className="text-xs sm:text-sm text-gray-500">{subtitle}</p>}
            </div>
          </div>
          {action && <div className="flex-shrink-0">{action}</div>}
        </div>
      )}
      <div className={padding ? 'p-4 sm:p-6' : ''}>{children}</div>
    </div>
  );
};

export default Card;
