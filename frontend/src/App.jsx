import { Provider } from 'react-redux'
import { BrowserRouter } from 'react-router-dom'
import { ToastContainer } from 'react-toastify'
import 'react-toastify/dist/ReactToastify.css'
import { store } from './store'
import AppRoutes from './routes/AppRoutes'

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
        />
      </BrowserRouter>
    </Provider>
  )
}

export default App
