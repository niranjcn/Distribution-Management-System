const Skeleton = ({ className = '' }) => (
  <div
    className={`animate-pulse bg-gray-200 rounded ${className}`}
    aria-hidden="true"
  />
)

export const SkeletonCircle = ({ size = 'w-14 h-14', className = '' }) => (
  <div
    className={`animate-pulse bg-gray-200 rounded-full flex-shrink-0 ${size} ${className}`}
    aria-hidden="true"
  />
)

export const SkeletonText = ({ lines = 1, className = '' }) => (
  <div className={`space-y-2 ${className}`} aria-hidden="true">
    {Array.from({ length: lines }).map((_, i) => (
      <Skeleton
        key={i}
        className={`h-3 ${i === lines - 1 ? 'w-3/4' : 'w-full'}`}
      />
    ))}
  </div>
)

export default Skeleton
