import { Check, Circle, Clock } from 'lucide-react';

const Timeline = ({ items }) => {
  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return (
          <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
            <Check className="w-4 h-4 text-green-600" />
          </div>
        );
      case 'current':
        return (
          <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
            <Clock className="w-4 h-4 text-blue-600 animate-pulse" />
          </div>
        );
      default:
        return (
          <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">
            <Circle className="w-4 h-4 text-gray-400" />
          </div>
        );
    }
  };

  return (
    <div className="space-y-0">
      {items.map((item, index) => (
        <div key={index} className="flex gap-4">
          <div className="flex flex-col items-center">
            {getStatusIcon(item.status)}
            {index < items.length - 1 && (
              <div
                className={`w-0.5 flex-1 my-2 ${
                  item.status === 'completed' ? 'bg-green-300' : 'bg-gray-200'
                }`}
              />
            )}
          </div>
          <div className={`pb-8 ${index === items.length - 1 ? 'pb-0' : ''}`}>
            <p className="text-sm font-medium text-gray-800">{item.title}</p>
            {item.description && (
              <p className="text-sm text-gray-500 mt-1">{item.description}</p>
            )}
            {item.timestamp && (
              <p className="text-xs text-gray-400 mt-1">{item.timestamp}</p>
            )}
            {item.user && (
              <p className="text-xs text-gray-500 mt-1">By: {item.user}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

export default Timeline;
