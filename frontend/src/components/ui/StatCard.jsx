/**
 * StatCard — KannurVision PDIC style
 * Bold left accent border, large colored number, faded icon circle on right.
 * Colorful and expressive — matches the reference image.
 */
const StatCard = ({ title, value, description, icon: Icon, color = 'blue' }) => {
  const colorConfig = {
    // Semantic device/network statuses
    total:   {
      border: 'border-l-slate-400',
      circle: 'bg-slate-100',
      icon:   'text-slate-400',
      value:  'text-slate-700',
      glow:   'from-slate-50',
    },
    online:  {
      border: 'border-l-green-500',
      circle: 'bg-green-100',
      icon:   'text-green-500',
      value:  'text-green-600',
      glow:   'from-green-50',
    },
    offline: {
      border: 'border-l-red-500',
      circle: 'bg-red-100',
      icon:   'text-red-400',
      value:  'text-red-600',
      glow:   'from-red-50',
    },
    pending: {
      border: 'border-l-orange-400',
      circle: 'bg-orange-100',
      icon:   'text-orange-400',
      value:  'text-orange-600',
      glow:   'from-orange-50',
    },
    // Named colors
    blue:   {
      border: 'border-l-blue-500',
      circle: 'bg-blue-100',
      icon:   'text-blue-400',
      value:  'text-blue-700',
      glow:   'from-blue-50',
    },
    green:  {
      border: 'border-l-green-500',
      circle: 'bg-green-100',
      icon:   'text-green-500',
      value:  'text-green-600',
      glow:   'from-green-50',
    },
    red:    {
      border: 'border-l-red-500',
      circle: 'bg-red-100',
      icon:   'text-red-400',
      value:  'text-red-600',
      glow:   'from-red-50',
    },
    yellow: {
      border: 'border-l-amber-400',
      circle: 'bg-amber-100',
      icon:   'text-amber-400',
      value:  'text-amber-600',
      glow:   'from-amber-50',
    },
    purple: {
      border: 'border-l-purple-500',
      circle: 'bg-purple-100',
      icon:   'text-purple-400',
      value:  'text-purple-600',
      glow:   'from-purple-50',
    },
    indigo: {
      border: 'border-l-indigo-500',
      circle: 'bg-indigo-100',
      icon:   'text-indigo-400',
      value:  'text-indigo-600',
      glow:   'from-indigo-50',
    },
    teal: {
      border: 'border-l-teal-500',
      circle: 'bg-teal-100',
      icon:   'text-teal-400',
      value:  'text-teal-600',
      glow:   'from-teal-50',
    },
  };

  const cfg = colorConfig[color] || colorConfig.blue;

  return (
    <div
      className={`
        relative bg-white rounded-2xl border border-gray-200 border-l-4 ${cfg.border}
        shadow-sm hover:shadow-md transition-shadow duration-200
        px-5 py-4 flex items-center justify-between gap-3 min-w-0
        overflow-hidden
      `}
    >
      {/* Subtle background glow */}
      <div className={`absolute inset-0 bg-gradient-to-br ${cfg.glow} to-white opacity-60 pointer-events-none`} />

      {/* Left — text stack */}
      <div className="relative flex flex-col gap-0.5 min-w-0">
        <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest truncate">
          {title}
        </span>
        <span className={`text-3xl sm:text-4xl font-bold leading-none ${cfg.value}`}>
          {value}
        </span>
        {description && (
          <span className="text-xs text-gray-400 mt-1">{description}</span>
        )}
      </div>

      {/* Right — large decorative icon circle */}
      {Icon && (
        <div className={`relative flex-shrink-0 w-14 h-14 rounded-full ${cfg.circle} flex items-center justify-center`}>
          <Icon className={`w-7 h-7 ${cfg.icon}`} strokeWidth={1.5} />
        </div>
      )}
    </div>
  );
};

export default StatCard;
