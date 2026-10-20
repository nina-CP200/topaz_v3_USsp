import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  DashboardOutlined,
  StockOutlined,
  WalletOutlined,
  SettingOutlined,
} from '@ant-design/icons'

const navItems = [
  { path: '/dashboard', icon: <DashboardOutlined />, label: '每日决策' },
  { path: '/stocks', icon: <StockOutlined />, label: '市场扫描' },
  { path: '/portfolio', icon: <WalletOutlined />, label: '我的组合' },
  { path: '/settings', icon: <SettingOutlined />, label: '设置' },
]

const pageTitleMap: Record<string, string> = {
  '/dashboard': '每日决策',
  '/stocks': '市场扫描',
  '/portfolio': '我的组合',
  '/settings': '设置',
}

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const currentPath = location.pathname
  const pageTitle = pageTitleMap[currentPath] || 'Topaz-Next'

  return (
    <div className="app-shell" style={{
      display: 'flex',
      height: '100vh',
      overflow: 'hidden',
    }}>
      {/* Sidebar */}
      <aside className="app-sidebar" style={{
        width: 240,
        minWidth: 240,
        background: 'var(--bg-sidebar)',
        display: 'flex',
        flexDirection: 'column',
        borderRight: '1px solid var(--border)',
      }}>
        {/* Logo Area */}
        <div style={{
          padding: '16px 16px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <div style={{
            width: 32,
            height: 32,
            borderRadius: 'var(--radius-sm)',
            background: 'linear-gradient(135deg, var(--accent), #c08a30)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 2px 8px rgba(212, 164, 76, 0.25)',
          }}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M3 9L7.5 13.5L15 4.5" stroke="#0f0f0f" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <div style={{
              color: 'var(--text-primary)',
              fontWeight: 700,
              fontSize: 14,
              fontFamily: 'var(--font-display)',
              letterSpacing: '0.01em',
              lineHeight: 1.2,
            }}>
              Topaz US
            </div>
            <div style={{
              color: 'var(--text-muted)',
              fontSize: 10,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
            }}>
              MOON ACCUMULATION
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav style={{
          flex: 1,
          padding: '12px 8px',
          overflowY: 'auto',
        }}>
          {navItems.map(item => {
            const isActive = currentPath === item.path
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  width: '100%',
                  padding: '8px 12px',
                  marginBottom: 2,
                  border: 'none',
                  borderRadius: 'var(--radius-sm)',
                  background: isActive
                    ? 'rgba(212, 164, 76, 0.1)' : 'transparent',
                  color: isActive ? 'var(--accent)' : 'var(--text-muted)',
                  fontSize: 13,
                  fontWeight: isActive ? 600 : 400,
                  fontFamily: 'var(--font-sans)',
                  cursor: 'pointer',
                  transition: 'all 180ms ease',
                  textAlign: 'left',
                  outline: 'none',
                }}
                onMouseEnter={e => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.03)'
                    e.currentTarget.style.color = 'var(--text-secondary)'
                  }
                }}
                onMouseLeave={e => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.color = 'var(--text-muted)'
                  }
                }}
              >
                <span style={{
                  fontSize: 15,
                  opacity: isActive ? 1 : 0.5,
                  transition: 'opacity 180ms ease',
                }}>{item.icon}</span>
                <span>{item.label}</span>
                {isActive && (
                  <div style={{
                    marginLeft: 'auto',
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: 'var(--accent)',
                    boxShadow: '0 0 8px rgba(212, 164, 76, 0.4)',
                  }} />
                )}
              </button>
            )
          })}
        </nav>

        {/* Footer */}
        <div style={{
          padding: '12px 16px',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 6,
        }}>
          <div style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: '#4ec9a8',
            boxShadow: '0 0 6px rgba(78, 201, 168, 0.4)',
          }} />
          <span style={{
            fontSize: 10,
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
            letterSpacing: '0.04em',
          }}>
            SYSTEM ONLINE
          </span>
        </div>
      </aside>

      {/* Main Content */}
      <div className="app-main" style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
      }}>
        {/* Header */}
        <header className="app-header" style={{
          height: 52,
          minHeight: 52,
          background: 'var(--bg-sidebar)',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <h1 style={{
              margin: 0,
              fontSize: 16,
              fontWeight: 700,
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-display)',
              letterSpacing: '0.01em',
            }}>
              {pageTitle}
            </h1>
          </div>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}>
              <div className="status-pulse" style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: '#4ec9a8',
              }} />
              <span style={{
                fontSize: 11,
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
                letterSpacing: '0.04em',
              }}>
                {new Date().toLocaleDateString('zh-CN', {
                  year: 'numeric',
                  month: '2-digit',
                  day: '2-digit',
                }).replace(/\//g, '.')}
              </span>
            </div>
          </div>
        </header>

        {/* Content Area */}
        <main className="app-content" style={{
          flex: 1,
          overflow: 'auto',
          padding: '20px 24px',
          background: 'var(--bg-base)',
        }}>
          <div className="page-enter">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
