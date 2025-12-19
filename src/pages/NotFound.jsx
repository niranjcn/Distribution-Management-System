import { Link } from 'react-router-dom';
import Button from '../components/ui/Button';
import { Home, ArrowLeft } from 'lucide-react';

const NotFound = () => {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="text-center">
        <div className="mb-8">
          <h1 className="text-9xl font-bold text-gray-200">404</h1>
          <div className="relative -mt-20">
            <h2 className="text-2xl font-bold text-gray-800 mb-2">Page Not Found</h2>
            <p className="text-gray-500 max-w-md mx-auto">
              Sorry, we couldn't find the page you're looking for. 
              It might have been moved or doesn't exist.
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link to="/">
            <Button icon={Home}>
              Go to Dashboard
            </Button>
          </Link>
          <Button variant="outline" icon={ArrowLeft} onClick={() => window.history.back()}>
            Go Back
          </Button>
        </div>

        <div className="mt-12 text-gray-400">
          <p className="text-sm">
            If you think this is a mistake, please contact support.
          </p>
        </div>
      </div>
    </div>
  );
};

export default NotFound;
