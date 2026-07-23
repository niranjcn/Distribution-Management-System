import { Component } from 'react';
import { AlertTriangle } from 'lucide-react';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error(`[ErrorBoundary] ${this.props.name || 'Section'} crashed:`, error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="bg-white rounded-xl shadow-sm border border-red-200 p-6">
          <div className="flex flex-col items-center justify-center gap-2 text-center">
            <div className="w-10 h-10 bg-red-50 rounded-lg flex items-center justify-center border border-red-200">
              <AlertTriangle className="w-5 h-5 text-red-500" />
            </div>
            <p className="text-sm font-medium text-gray-800">{this.props.name || 'Section'} unavailable</p>
            <p className="text-xs text-gray-400">Something went wrong loading this section.</p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
