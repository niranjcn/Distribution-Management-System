import Skeleton, { SkeletonCircle, SkeletonText } from './Skeleton'

const StatCard = ({ title, value, description, icon: Icon, color = 'blue', loading = false }) => {
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

  if (loading) {
    return (
      <div className="stat-card relative bg-white rounded-2xl border border-gray-200 border-l-4 border-l-gray-200 shadow-sm px-5 py-4 overflow-hidden">
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-col gap-2 min-w-0 flex-1">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-8 w-28" />
            <Skeleton className="h-3 w-36" />
          </div>
          <SkeletonCircle size="w-14 h-14" />
        </div>
      </div>
    );
  }

  return (
    <div
      className={`
        stat-card relative bg-white rounded-2xl border border-gray-200 border-l-4 ${cfg.border}
        shadow-sm hover:shadow-md transition-shadow duration-200
        px-5 py-4 flex items-center justify-between gap-3 min-w-0
        overflow-hidden
      `}
    >
      {/* Subtle background glow */}
      <div className={`stat-card-glow absolute inset-0 bg-gradient-to-br ${cfg.glow} to-white opacity-60 pointer-events-none`} />

      {/* Left — text stack */}
      <div className="relative flex flex-col gap-0.5 min-w-0">
        <span className="stat-card-title text-[11px] font-semibold text-gray-400 uppercase tracking-widest truncate">
          {title}
        </span>
        <span className={`stat-card-value text-3xl sm:text-4xl font-bold leading-none ${cfg.value}`}>
          {value}
        </span>
        {description && (
          <span className="stat-card-desc text-xs text-gray-400 mt-1">{description}</span>
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
