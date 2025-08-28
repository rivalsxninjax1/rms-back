import { BrowserRouter, Switch, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Menu from './pages/Menu'
import Orders from './pages/Orders'
import Inventory from './pages/Inventory'
import Reservations from './pages/Reservation'
import Reports from './pages/Reports'
import Settings from './pages/Settings.tsx'

const client = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <Switch>
          <Route path="/login" component={Login} />
          <ProtectedRoute>
            <Layout>
              <Switch>
                <Route exact path="/" component={Dashboard} />
                <Route path="/menu" component={Menu} />
                <Route path="/orders" component={Orders} />
                <Route path="/inventory" component={Inventory} />
                <Route path="/reservations" component={Reservations} />
                <Route path="/reports" component={Reports} />
                <Route path="/settings" component={Settings} />
              </Switch>
            </Layout>
          </ProtectedRoute>
        </Switch>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
