import { Switch, Route, Redirect } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import RBACRoute from './components/RBACRoute'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Orders from './pages/Orders'
import Reservations from './pages/Reservations'
import Reports from './pages/Reports'
import Settings from './pages/Settings.tsx'
import Payments from './pages/Payments'
import Users from './pages/Users'
import MenuLayout from './pages/menu/MenuLayout'
import Items from './pages/menu/Items'
import Modifiers from './pages/menu/Modifiers'
import Stock from './pages/menu/Stock'
import Availability from './pages/menu/Availability'
import POS from './pages/POS'
import Coupons from './pages/Coupons'
import Loyalty from './pages/Loyalty'
import LiveDashboard from './pages/LiveDashboard'
import SyncBar from './components/SyncBar'
import { useEffect } from 'react'
import { useSyncStore } from './lib/sync'
import { idb, cacheOrders, cacheReservationsFor, cacheMenu, syncQueue } from './lib/db'

const client = new QueryClient()

export default function App() {
  const setOnline = useSyncStore((s) => s.setOnline)
  const setPending = useSyncStore((s) => s.setPending)
  const setLastSync = useSyncStore((s) => s.setLastSync)

  // Minimal wiring: monitor online/offline and attempt sync on reconnect
  useEffect(() => {
    function updateOnline() { setOnline(navigator.onLine) }
    window.addEventListener('online', updateOnline)
    window.addEventListener('offline', updateOnline)
    updateOnline()
    // initialize pending count
    idb.keys('queue').then((ks) => setPending(ks.length)).catch(() => {})
    return () => {
      window.removeEventListener('online', updateOnline)
      window.removeEventListener('offline', updateOnline)
    }
  }, [setOnline, setPending])

  // Simple periodic cache refresh (orders/reservations/menu)
  useEffect(() => {
    let stop = false
    async function run() {
      try {
        const today = new Date().toISOString().slice(0,10)
        await Promise.all([
          cacheOrders('pending'),
          cacheOrders('in_progress'),
          cacheOrders('served'),
          cacheReservationsFor(today),
          cacheMenu(),
        ])
        setLastSync(Date.now())
      } catch {}
      if (!stop) setTimeout(run, 30000)
    }
    run()
    return () => { stop = true }
  }, [setLastSync])

  // Try syncing queued jobs on regain connectivity
  useEffect(() => {
    function onOnline() {
      if (navigator.onLine) {
        syncQueue().then(async () => {
          const ks = await idb.keys('queue')
          setPending(ks.length)
          setLastSync(Date.now())
        }).catch(() => {})
      }
    }
    window.addEventListener('online', onOnline)
    return () => window.removeEventListener('online', onOnline)
  }, [setPending, setLastSync])
  return (
    <QueryClientProvider client={client}>
        <Switch>
          <Route path="/login" component={Login} />
          <ProtectedRoute>
            <Layout>
              <Switch>
                <Route exact path="/">
                  <Redirect to="/admin/dashboard" />
                </Route>
                <RBACRoute path="/admin/dashboard" roles={['Manager','Cashier','Kitchen','Host']} component={Dashboard} />
                <Route exact path="/live">
                  <Redirect to="/admin/liveDashboard" />
                </Route>
                <Route exact path="/admin/live">
                  <Redirect to="/admin/liveDashboard" />
                </Route>
                <RBACRoute path="/admin/orders" roles={['Manager','Cashier','Kitchen','Host']} component={Orders} />
                <RBACRoute path="/admin/payments" roles={['Manager','Cashier']} component={Payments} />
                <RBACRoute path="/admin/reservations" roles={['Manager','Host']} component={Reservations} />
                <RBACRoute path="/admin/pos" roles={['Manager','Cashier','Host']} component={POS} />
                <RBACRoute path="/admin/menu">
                  <MenuLayout>
                    <Switch>
                      <RBACRoute exact path="/admin/menu">
                        <Redirect to="/admin/menu/items" />
                      </RBACRoute>
                      <RBACRoute path="/admin/menu/items" roles={['Manager']} component={Items} />
                      <RBACRoute path="/admin/menu/modifiers" roles={['Manager']} component={Modifiers} />
                      <RBACRoute path="/admin/menu/stock" roles={['Manager','Cashier']} component={Stock} />
                      <RBACRoute path="/admin/menu/availability" roles={['Manager']} component={Availability} />
                    </Switch>
                  </MenuLayout>
                </RBACRoute>
                <RBACRoute path="/admin/coupons" roles={['Manager']} component={Coupons} />
                <RBACRoute path="/admin/loyalty" roles={['Manager','Cashier']} component={Loyalty} />
                <RBACRoute exact path="/admin/reports" roles={['Manager','Cashier','Kitchen','Host']} component={Reports} />
                <RBACRoute path="/admin/reports/daily-sales" roles={['Manager','Cashier']} component={Reports} />
                <RBACRoute path="/admin/reports/shift-close" roles={['Manager','Cashier']} component={Reports} />
                <RBACRoute path="/admin/reports/menu-performance" roles={['Manager']} component={Reports} />
                <RBACRoute path="/admin/reports/audit-logs" roles={['Manager']} component={Reports} />
                <RBACRoute path="/admin/settings" roles={['Manager']} component={Settings} />
                <RBACRoute path="/admin/users" roles={['Manager']} component={Users} />
                <RBACRoute path="/admin/liveDashboard" roles={['Manager','Cashier','Kitchen','Host']} component={LiveDashboard} />
              </Switch>
            </Layout>
            <SyncBar />
          </ProtectedRoute>
        </Switch>
    </QueryClientProvider>
  )
}
