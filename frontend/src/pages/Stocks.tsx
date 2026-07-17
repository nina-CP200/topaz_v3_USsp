import { useEffect, useRef, useState } from 'react'
import { Button, Drawer, Input, Modal, Progress, Segmented, Select, Space, Spin, Table, message } from 'antd'
import { FileTextOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import { getAnalysisReport, getAnalysisStatus, getDailyAnalysis, refreshAnalysis } from '../api'
import type { DailyAnalysis, StockResult } from '../api'

const signalColor = (stock: StockResult) => stock.bearish_sweep ? 'var(--coral)' : stock.active_long_signal ? 'var(--teal)' : stock.signal_status === 'Market Hold' ? 'var(--accent)' : 'var(--text-muted)'
const pct = (value?: number) => value == null ? '-' : `${(value * 100).toFixed(0)}%`

export default function Stocks() {
  const [data, setData] = useState<DailyAnalysis | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [view, setView] = useState<string>('active')
  const [search, setSearch] = useState('')
  const [sector, setSector] = useState<string | undefined>()
  const [selected, setSelected] = useState<StockResult | null>(null)
  const [report, setReport] = useState('')
  const [reportOpen, setReportOpen] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = async () => {
    try { setData(await getDailyAnalysis()) } catch { message.error('暂无分析结果，请先刷新分析') } finally { setLoading(false) }
  }
  useEffect(() => {
    const timer = window.setTimeout(() => { void load() }, 0)
    return () => { window.clearTimeout(timer); if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const refresh = async () => {
    setRefreshing(true); setProgress(2)
    try {
      await refreshAnalysis()
      pollRef.current = setInterval(async () => {
        const status = await getAnalysisStatus().catch(() => null)
        if (!status) return
        if (status.status === 'done' || status.status === 'error') {
          if (pollRef.current) clearInterval(pollRef.current)
          pollRef.current = null; setRefreshing(false); setProgress(100); await load()
          if (status.status === 'error') message.error(`分析失败：${status.message}`)
        } else setProgress(value => Math.min(95, Math.max(value + 7, status.progress || 0)))
      }, 2200)
    } catch (error: unknown) { setRefreshing(false); message.error(error instanceof Error ? error.message : '触发分析失败') }
  }

  const results = data?.results || []
  const sectors = [...new Set(results.map(item => item.sector).filter(Boolean))].sort()
  const filtered = results.filter(item => {
    if (view === 'active' && !item.active_long_signal) return false
    if (view === 'blocked' && item.signal_status !== 'Market Hold') return false
    if (view === 'exit' && !item.bearish_sweep) return false
    if (search && !`${item.symbol} ${item.name}`.toLowerCase().includes(search.toLowerCase())) return false
    if (sector && item.sector !== sector) return false
    return true
  })

  const columns = [
    { title: '#', dataIndex: 'rank', width: 52, sorter: (a: StockResult, b: StockResult) => a.rank - b.rank },
    { title: 'Ticker', dataIndex: 'symbol', width: 98, render: (value: string) => <strong className="data-value">{value}</strong> },
    { title: '名称', dataIndex: 'name', width: 136 },
    { title: '行业', dataIndex: 'sector', width: 155 },
    { title: '价格', dataIndex: 'current_price', width: 92, render: (value: number) => <span className="data-value">${value?.toFixed(2)}</span> },
    { title: '日变动', dataIndex: 'change_pct', width: 90, sorter: (a: StockResult, b: StockResult) => a.change_pct - b.change_pct, render: (value: number) => <span className="data-value" style={{ color: value >= 0 ? 'var(--teal)' : 'var(--coral)' }}>{value >= 0 ? '+' : ''}{value?.toFixed(2)}%</span> },
    { title: '状态', key: 'status', width: 118, render: (_: unknown, item: StockResult) => <span className="signal-cell" style={{ color: signalColor(item) }}>{item.signal_status || 'No Signal'}</span> },
    { title: '评分', dataIndex: 'composite_score', width: 82, sorter: (a: StockResult, b: StockResult) => a.composite_score - b.composite_score, render: (value: number) => <span className="data-value">{value?.toFixed(1)}</span> },
    { title: '建议仓位', dataIndex: 'position_pct', width: 96, render: (value: number) => <span className="data-value">{pct(value)}</span> },
    { title: '入场 / 止损', key: 'levels', width: 148, render: (_: unknown, item: StockResult) => <span className="data-value">{item.entry_price ? `$${item.entry_price.toFixed(2)}` : '-'} <span className="muted-separator">/</span> <span style={{ color: 'var(--coral)' }}>{item.stop_loss ? `$${item.stop_loss.toFixed(2)}` : '-'}</span></span> },
  ]

  return <div>
    {refreshing && <div className="analysis-progress"><Progress percent={progress} size="small" showInfo={false} /><span>正在更新扫描结果…</span></div>}
    <div className="scanner-toolbar">
      <Segmented value={view} onChange={value => setView(String(value))} options={[{ label: '可建仓', value: 'active' }, { label: '等待市场', value: 'blocked' }, { label: '退出预警', value: 'exit' }, { label: '全量股票池', value: 'all' }]} />
      <Space wrap>
        <Input prefix={<SearchOutlined />} placeholder="Ticker / 名称" value={search} onChange={event => setSearch(event.target.value)} allowClear style={{ width: 190 }} />
        <Select placeholder="行业" allowClear value={sector} onChange={setSector} options={sectors.map(value => ({ label: value, value }))} style={{ width: 150 }} />
        <Button icon={<FileTextOutlined />} onClick={async () => { const result = await getAnalysisReport(); if (result.text) { setReport(result.text); setReportOpen(true) } else message.error(result.error || '暂无报告') }}>报告</Button>
        <Button type="primary" icon={<ReloadOutlined />} loading={refreshing} onClick={refresh}>刷新分析</Button>
      </Space>
    </div>
    <div className="scanner-summary"><span>{view === 'active' ? '仅显示通过 QQQ 市场门槛的有效入场信号。' : '点击任意行查看评分、触发条件和风险理由。'}</span><strong>{filtered.length} / {results.length}</strong></div>
    {loading ? <Spin size="large" style={{ display: 'block', marginTop: 100 }} /> : <Table dataSource={filtered} columns={columns} rowKey="symbol" size="small" pagination={{ pageSize: 50, showSizeChanger: false }} scroll={{ x: 1100 }} onRow={item => ({ onClick: () => setSelected(item), style: { cursor: 'pointer' } })} />}

    <Drawer title={selected ? `${selected.symbol} · ${selected.name}` : ''} open={Boolean(selected)} onClose={() => setSelected(null)} width={440}>
      {selected && <div className="stock-drawer">
        <div className="drawer-price">${selected.current_price.toFixed(2)} <span style={{ color: selected.change_pct >= 0 ? 'var(--teal)' : 'var(--coral)' }}>{selected.change_pct >= 0 ? '+' : ''}{selected.change_pct.toFixed(2)}%</span></div>
        <div className="drawer-grid"><div><span>综合评分</span><strong>{selected.composite_score.toFixed(1)}</strong></div><div><span>建议仓位</span><strong>{pct(selected.position_pct)}</strong></div><div><span>入场价</span><strong>{selected.entry_price ? `$${selected.entry_price.toFixed(2)}` : '-'}</strong></div><div><span>初始止损</span><strong style={{ color: 'var(--coral)' }}>{selected.stop_loss ? `$${selected.stop_loss.toFixed(2)}` : '-'}</strong></div></div>
        <div className="score-breakdown"><h3>评分构成</h3>{[['趋势', selected.trend_score], ['入场信号', selected.signal_score], ['成交量', selected.volume_score], ['波动率', selected.volatility_score], ['相对强弱', selected.relative_strength_score], ['动量', selected.momentum_score], ['风险扣分', selected.risk_penalty]].map(([label, value]) => <div key={String(label)}><span>{label}</span><strong>{typeof value === 'number' ? value.toFixed(1) : '-'}</strong></div>)}</div>
        <div className="reason-block"><h3>策略理由</h3>{selected.reasons?.length ? selected.reasons.map(reason => <p key={reason}>{reason}</p>) : <p>暂无额外说明。</p>}</div>
      </div>}
    </Drawer>
    <Modal title="每日研究报告" open={reportOpen} onCancel={() => setReportOpen(false)} footer={null} width={760}><pre className="report-preview">{report}</pre></Modal>
  </div>
}
