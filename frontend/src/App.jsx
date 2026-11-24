import { Provider } from 'react-redux'
import { BrowserRouter } from 'react-router-dom'
import { ToastContainer } from 'react-toastify'
import 'react-toastify/dist/ReactToastify.css'
import { store } from './store'
import AppRoutes from './routes/AppRoutes'
import { readCspNonce } from './utils/cspNonce'

// react-toastify inserts one <style> element; the server's CSP nonce lets it
// through without allowing inline styles in general.
const cspNonce = readCspNonce()

function App() {
  return (
    <Provider store={store}>
      <BrowserRouter>
        <AppRoutes />
        <ToastContainer
          position="bottom-right"
          autoClose={3500}
          hideProgressBar
          toastClassName="!font-sans !text-sm !rounded-none"
          nonce={cspNonce}
        />
      </BrowserRouter>
    </Provider>
  )
}

export default App
