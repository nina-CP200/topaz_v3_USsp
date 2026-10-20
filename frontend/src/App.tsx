import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import AppLayout from './components/AppLayout'
import Dashboard from './pages/Dashboard'
import Stocks from './pages/Stocks'
import Portfolio from './pages/Portfolio'
import Settings from './pages/Settings'
import './styles/global.css'

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#d4a44c',
          colorBgContainer: '#181816',
          colorBgElevated: '#1e1e1c',
          colorBgLayout: '#0f0f0f',
          colorBorder: '#2a2a28',
          colorBorderSecondary: '#202020',
          colorText: '#e8e6e1',
          colorTextSecondary: '#9a9890',
          colorTextTertiary: '#5e5c56',
          colorSuccess: '#4ec9a8',
          colorError: '#e07057',
          colorWarning: '#d4a44c',
          colorInfo: '#6b9fd4',
          borderRadius: 6,
          fontFamily: "'DM Sans', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif",
          fontSize: 13,
          lineHeight: 1.5,
        },
        components: {
          Menu: {
            colorItemBg: 'transparent',
            colorItemBgHover: 'rgba(212, 164, 76, 0.08)',
            colorItemBgSelected: 'rgba(212, 164, 76, 0.12)',
            colorItemText: '#7a7870',
            colorItemTextHover: '#d4a44c',
            colorItemTextSelected: '#d4a44c',
          },
          Layout: {
            bodyBg: '#0f0f0f',
            headerBg: '#131312',
            siderBg: '#131312',
          },
          Table: {
            headerBg: '#1a1a18',
            headerColor: '#5e5c56',
            rowHoverBg: '#1e1e1c',
            borderColor: '#202020',
          },
          Card: {
            colorBgContainer: '#181816',
          },
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/stocks" element={<Stocks key="stocks" />} />
            <Route path="/watchlist" element={<Stocks key="watchlist" watchlistOnly />} />
            <Route path="/portfolio" element={<Portfolio />} />
            <Route path="/research" element={<Navigate to="/stocks" replace />} />
            <Route path="/about" element={<Navigate to="/stocks" replace />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  )
}
