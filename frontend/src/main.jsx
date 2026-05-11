import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { installGlobalDateFormatting } from './utils/dateFormatting'

const noop = () => {}
if (typeof console !== 'undefined') {
  ['log', 'debug', 'info', 'warn', 'error'].forEach((method) => {
    if (typeof console[method] === 'function') {
      console[method] = noop
    }
  })
}

installGlobalDateFormatting()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
