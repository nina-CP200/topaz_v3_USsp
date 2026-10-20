import { isAxiosError } from 'axios'
import { Link } from 'react-router-dom'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Button, Drawer, Input, Modal, Progress, Segmented, Select, Space, Spin, Switch, Table, Tabs, Tooltip, message } from 'antd'
import { FileTextOutlined, ReloadOutlined, SearchOutlined, StarFilled, StarOutlined, PlusOutlined } from '@ant-design/icons'
import { getAnalysisReport, getAnalysisStatus, getDailyAnalysis, refreshAnalysis, getWatchlist, addToWatchlist, removeFromWatchlist, searchWatchlistSymbols, getWatchlistAnalysis } from '../api'
import type { DailyAnalysis, HorizonAnalysis, HorizonKey, StockResult, TechnicalSignal, MoonAnalysis, SymbolSearchResult } from '../api'

const periods: HorizonKey[] = ['short', 'medium', 'long']
const periodLabels = { short: '短期', medium: '中期', long: '长期' }
const directionLabels = { bullish: '看涨', bearish: '看跌', neutral: '中性', unavailable: '数据不足' }
function Signal({ signal, mixed = false }: { signal?: TechnicalSignal; mixed?: boolean }) {
  const direction = signal?.direction || 'unavailable'
  return <Tooltip title={signal?.reason || '暂无该周期分析，请刷新分析以更新记录。'}><span className={`technical-signal signal-${direction}`}>{mixed && direction === 'neutral' ? '中性 / 分歧' : directionLabels[direction]}</span></Tooltip>
}
const indicatorRows = [
  { key: 'williams' as const, label: '威廉 %R' },
  { key: 'macd' as const, label: 'MACD' },
  { key: 'ma' as const, label: 'MA 交叉' },
  { key: 'cci' as const, label: 'CCI' },
]
function MoonConclusion({ analysis }: { analysis?: MoonAnalysis }) {
  return <Tooltip title={analysis?.reason || '暂无 Moon 判断，请刷新分析。'}><span className={`technical-signal signal-${analysis?.direction || 'unavailable'}`}>{analysis?.label || '数据不足'}{analysis?.direction === 'bullish' || analysis?.direction === 'bearish' ? ` · ${directionLabels[analysis.direction]}` : ''}</span></Tooltip>
}
function HorizonDetail({ analysis }: { analysis?: HorizonAnalysis }) {
  if (!analysis) return <p>暂无该周期分析。请刷新分析以生成记录。</p>
  return <div className="horizon-detail">
    <div className="horizon-verdict"><Signal mixed signal={analysis.summary} /><span>{analysis.window} · 日线参数组</span></div>
    <p className="horizon-summary">{analysis.summary.reason}</p>
    {indicatorRows.map(row => <section className="indicator-explanation" key={row.key}>
      <div className="indicator-heading"><h3>{row.label}</h3><Signal signal={analysis.signals[row.key]} /></div>
      <p>{analysis.signals[row.key].reason}</p>
    </section>)}
  </div>
}

export default function Stocks({ watchlistOnly = false }: { watchlistOnly?: boolean }) {
  const [addOpen, setAddOpen] = useState(false)
  const [symbolQuery, setSymbolQuery] = useState('')
  const [symbolResults, setSymbolResults] = useState<SymbolSearchResult[]>([])
  const [symbolSearching, setSymbolSearching] = useState(false)
  const [symbolWarning, setSymbolWarning] = useState('')
  const [customResults, setCustomResults] = useState<StockResult[]>([])
  const [customLoading, setCustomLoading] = useState(false)
  const [customError, setCustomError] = useState(false)
  const searchRequest = useRef(0)
  const [watchlist, setWatchlist] = useState<string[]>([])
  const [watchlistReady, setWatchlistReady] = useState(false)
  const [watchlistError, setWatchlistError] = useState(false)
  const [onlyWatchlist, setOnlyWatchlist] = useState(false)
  const [savingSymbol, setSavingSymbol] = useState<string | null>(null)
  const watchlistMutation = useRef(false)
  const showWatchlist = watchlistOnly || onlyWatchlist
  const [data, setData] = useState<DailyAnalysis | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [horizon, setHorizon] = useState<HorizonKey>('medium')
  const [view, setView] = useState<string>('all')
  const [search, setSearch] = useState('')
  const [sector, setSector] = useState<string | undefined>()
  const [selected, setSelected] = useState<StockResult | null>(null)
  const [report, setReport] = useState('')
  const [reportOpen, setReportOpen] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadCustomAnalysis = useCallback(async () => {
    setCustomLoading(true)
    try { setCustomResults((await getWatchlistAnalysis()).results); setCustomError(false) }
    catch { setCustomError(true) }
    finally { setCustomLoading(false) }
  }, [])
  const searchSymbols = async () => {
    const query = symbolQuery.trim()
    if (!query) return
    const request = ++searchRequest.current
    setSymbolSearching(true); setSymbolWarning(''); setSymbolResults([])
    try {
      const result = await searchWatchlistSymbols(query)
      if (request === searchRequest.current) { setSymbolResults(result.results); setSymbolWarning(result.warning || (result.results.length ? '' : '没有找到匹配标的，可核对代码后直接添加。')) }
    } catch { if (request === searchRequest.current) setSymbolWarning('在线搜索失败，可输入完整代码直接添加或稍后重试。') }
    finally { if (request === searchRequest.current) setSymbolSearching(false) }
  }
  const load = useCallback(async () => {
    void loadCustomAnalysis()
    try { setData(await getDailyAnalysis()) } catch { message.error('暂无分析结果，请先刷新分析') } finally { setLoading(false) }
  }, [loadCustomAnalysis])
  const loadWatchlist = async () => {
    try {
      const result = await getWatchlist()
      setWatchlist(result.symbols); setWatchlistReady(true); setWatchlistError(false)
    } catch { setWatchlistError(true) }
  }
  const toggleWatchlist = async (symbol: string, forceAdd = false) => {
    if (!watchlistReady || watchlistMutation.current) return
    watchlistMutation.current = true
    setSavingSymbol(symbol)
    const removing = !forceAdd && watchlist.includes(symbol)
    try {
      const result = await (removing ? removeFromWatchlist(symbol) : addToWatchlist(symbol))
      setWatchlist(result.symbols)
      message.success(removing ? `${symbol} 已移出自选` : `${symbol} 已加入自选`)
      if (!removing) void loadCustomAnalysis()
    } catch (error: unknown) { message.error(isAxiosError(error) ? error.response?.data?.detail || '自选保存失败，请重试' : '自选保存失败，请重试') }
    finally { watchlistMutation.current = false; setSavingSymbol(null) }
  }
  const favoriteButton = (symbol: string, withLabel = false) => {
    const saved = watchlist.includes(symbol)
    return <Button type="text" className={saved ? 'watchlist-star is-saved' : 'watchlist-star'} aria-label={`${saved ? '移出自选' : '加入自选'} ${symbol}`} aria-pressed={saved} icon={saved ? <StarFilled /> : <StarOutlined />} disabled={!watchlistReady || Boolean(savingSymbol)} loading={savingSymbol === symbol} onClick={event => { event.stopPropagation(); void toggleWatchlist(symbol) }}>{withLabel ? saved ? '已加入自选' : '加入自选' : null}</Button>
  }
  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); void loadWatchlist() }, 0)
    return () => { window.clearTimeout(timer); if (pollRef.current) clearInterval(pollRef.current) }
  }, [load])

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

  const baseResults = data?.results || []
  const results = showWatchlist ? [...baseResults, ...customResults.filter(item => !baseResults.some(base => base.symbol === item.symbol))] : baseResults
  const sectors = [...new Set(results.map(item => item.sector).filter(Boolean))].sort()
  const missingWatchlist = watchlist.filter(symbol => !results.some(item => item.symbol === symbol))
  const filtered = results.filter(item => {
    if (showWatchlist && !watchlist.includes(item.symbol)) return false
    if (view === 'active' && !item.active_long_signal) return false
    if (view === 'blocked' && item.signal_status !== 'Market Hold') return false
    if (view === 'exit' && !item.bearish_sweep) return false
    if (search && !`${item.symbol} ${item.name}`.toLowerCase().includes(search.toLowerCase())) return false
    if (sector && item.sector !== sector) return false
    return true
  })

  const columns = [
    { title: '自选', key: 'watchlist', width: 52, render: (_: unknown, item: StockResult) => favoriteButton(item.symbol) },
    { title: '#', dataIndex: 'rank', width: 44, sorter: (a: StockResult, b: StockResult) => a.rank - b.rank },
    { title: 'Ticker', dataIndex: 'symbol', width: 82, render: (value: string) => <strong className="data-value">{value}</strong> },
    { title: '名称', dataIndex: 'name', width: 120 },
    { title: '价格', dataIndex: 'current_price', width: 92, render: (value: number) => <span className="data-value">${value?.toFixed(2)}</span> },
    { title: '日变动', dataIndex: 'change_pct', width: 90, sorter: (a: StockResult, b: StockResult) => a.change_pct - b.change_pct, render: (value: number) => <span className="data-value" style={{ color: value >= 0 ? 'var(--teal)' : 'var(--coral)' }}>{value >= 0 ? '+' : ''}{value?.toFixed(2)}%</span> },
    { title: 'Moon Accumulation', key: 'moon', width: 155, render: (_: unknown, item: StockResult) => <MoonConclusion analysis={item.moon_analysis} /> },
    ...periods.map(period => ({ title: `${periodLabels[period]}判断`, key: period, width: 116, render: (_: unknown, item: StockResult) => <Signal mixed signal={item.technical_analysis?.horizons[period]?.summary} /> })),
    ...indicatorRows.map(row => ({
      title: row.label, key: row.key, width: 112,
      render: (_: unknown, item: StockResult) => <Signal signal={item.technical_analysis?.horizons[horizon]?.signals[row.key]} />,
    })),
  ]

  return <div className="market-scanner">
    {showWatchlist && customError && <Alert type="warning" showIcon message="自选标的分析加载失败，已保存的收藏不受影响。" action={<Button size="small" onClick={() => { void loadCustomAnalysis() }}>重试分析</Button>} style={{ marginBottom: 12 }} />}
    {watchlistError && <Alert type="warning" showIcon message="自选列表读取失败" description="收藏操作暂不可用，请重试加载。" action={<Button size="small" onClick={() => { void loadWatchlist() }}>重试</Button>} style={{ marginBottom: 12 }} />}
    {showWatchlist && missingWatchlist.length > 0 && <Alert type="info" showIcon message={customLoading ? "正在加载自选标的行情与分析…" : "部分自选股票暂无分析结果"} description={<div>行情缺失或加载失败，可重试分析；刚上市的标的可能需要更多历史数据。{missingWatchlist.map(symbol => <Button key={symbol} size="small" type="text" disabled={Boolean(savingSymbol)} onClick={() => { void toggleWatchlist(symbol) }}>{symbol} · 移出自选</Button>)}</div>} style={{ marginBottom: 12 }} />}
    {refreshing && <div className="analysis-progress"><Progress percent={progress} size="small" showInfo={false} /><span>正在更新扫描结果…</span></div>}
    <div className="scanner-toolbar">
      <Segmented value={view} onChange={value => setView(String(value))} options={[{ label: '可建仓', value: 'active' }, { label: '等待市场', value: 'blocked' }, { label: '退出预警', value: 'exit' }, { label: watchlistOnly ? '全部自选' : '全量股票池', value: 'all' }]} />
      <Space wrap>
        <Input prefix={<SearchOutlined />} placeholder="筛选列表：代码 / 名称" value={search} onChange={event => setSearch(event.target.value)} allowClear style={{ width: 190 }} />
        <Select placeholder="行业" allowClear value={sector} onChange={setSector} options={sectors.map(value => ({ label: value, value }))} style={{ width: 150 }} />
        <Button icon={<FileTextOutlined />} onClick={async () => { const result = await getAnalysisReport(); if (result.text) { setReport(result.text); setReportOpen(true) } else message.error(result.error || '暂无报告') }}>报告</Button>
        <Button type="primary" icon={<ReloadOutlined />} loading={refreshing} onClick={refresh}>刷新分析</Button>
      </Space>
    </div>
    <div className="watchlist-toolbar"><Button icon={<PlusOutlined />} disabled={!watchlistReady} onClick={() => setAddOpen(true)}>搜索 / 添加标的</Button>{watchlistOnly ? <span>我的自选 · {watchlist.length} 只</span> : <label><Switch checked={onlyWatchlist} onChange={setOnlyWatchlist} disabled={!watchlistReady} /> 仅看自选（{watchlist.length}）</label>}<span>支持纳指 100 之外的美股；自选自动保存在本机。</span>{watchlistOnly && <Link to="/stocks">去市场扫描添加</Link>}</div>
    <div className="horizon-toolbar"><Segmented aria-label="指标分析周期" value={horizon} onChange={value => setHorizon(value as HorizonKey)} options={periods.map(value => ({ label: `${periodLabels[value]}指标`, value }))} /><span>短期约 1–4 周 · 中期约 1–3 个月 · 长期约 3–12 个月；均以日线分别计算</span></div>
    <div className="scanner-summary"><span>{view === 'active' ? '仅显示通过 QQQ 市场门槛的有效入场信号。' : 'Moon 显示日线形态结论；四项技术指标显示当前所选周期的方向。悬停或点击股票查看依据。'}</span><strong>{showWatchlist ? '按各标的行情截至日分析' : data?.date || '暂无分析记录'} · {filtered.length} / {showWatchlist ? watchlist.length : results.length}</strong></div>
    {loading || (showWatchlist && !watchlistReady && !watchlistError) ? <Spin size="large" style={{ display: 'block', marginTop: 100 }} /> : <Table dataSource={filtered} columns={columns} rowKey="symbol" size="small" locale={{ emptyText: showWatchlist && watchlistError ? '自选列表未能加载，请先重试。' : showWatchlist && !watchlist.length ? <div>还没有自选股票。点击“搜索 / 添加标的”搜索名称或股票代码。{watchlistOnly && <p><Link to="/stocks">去市场扫描</Link></p>}</div> : showWatchlist ? '当前筛选条件下没有自选股票' : '当前筛选条件下没有股票' }} pagination={{ pageSize: 50, showSizeChanger: false }} scroll={{ x: 1432 }} onRow={item => ({ onClick: () => setSelected(item), style: { cursor: 'pointer' } })} />}

    <Drawer title={selected ? `${selected.symbol} · ${selected.name}` : ''} extra={selected ? favoriteButton(selected.symbol, true) : null} open={Boolean(selected)} onClose={() => setSelected(null)} width="min(620px, 100vw)">
      {selected && <div className="stock-drawer">
        <div className="drawer-price">${selected.current_price.toFixed(2)} <span style={{ color: selected.change_pct >= 0 ? 'var(--teal)' : 'var(--coral)' }}>{selected.change_pct >= 0 ? '+' : ''}{selected.change_pct.toFixed(2)}%</span></div>
        <div className="indicator-caption">行情截至 {selected.technical_analysis?.as_of || '暂无'} · {selected.technical_analysis?.bars ?? 0} 根日线 · 分析时间 {selected.analysis_date || data?.date || '暂无'}</div>
        <section className="moon-assessment"><div className="indicator-heading"><h3>Moon Accumulation · 日线形态</h3><MoonConclusion analysis={selected.moon_analysis} /></div><p>{selected.moon_analysis?.reason || '暂无 Moon 判断，请刷新分析。'}</p></section>
        <Tabs key={selected.symbol} defaultActiveKey={horizon} items={periods.map(period => ({ key: period, label: <span>{periodLabels[period]} <Signal mixed signal={selected.technical_analysis?.horizons[period]?.summary} /></span>, children: <HorizonDetail analysis={selected.technical_analysis?.horizons[period]} /> }))} />
        <div className="reason-block"><h3>判断规则</h3><p>四项指标至少三项同向才给出该周期看涨或看跌；否则为中性 / 分歧。任一项数据不足时，该周期不作综合判断。长期均线交叉至少需要 201 根日线。</p><p>这些周期是本工具的观察范围与参数约定，不是收益预测。超买不自动等于看跌，超卖不自动等于看涨。Moon 单独沿用现有日线策略，优先提示退出风险，并检查 QQQ 市场门槛；不计入四项技术指标的周期投票。</p><p>“当日”指行情截至日期。旧记录按原分析日期补算；缺少行情时请刷新分析。</p></div>
      </div>}
    </Drawer>
    <Modal title="搜索并添加自选标的" open={addOpen} onCancel={() => setAddOpen(false)} footer={null} width={560}>
      <p className="indicator-caption">按股票代码或英文名称搜索美股 / ETF，支持纳指 100 之外的标的。</p>
      <Input.Search aria-label="搜索标的代码或名称" placeholder="例如 KO、JPM，或公司英文名称" maxLength={80} value={symbolQuery} onChange={event => { setSymbolQuery(event.target.value); ++searchRequest.current; setSymbolSearching(false); setSymbolResults([]); setSymbolWarning('') }} onSearch={() => { void searchSymbols() }} loading={symbolSearching} enterButton="搜索" />
      {symbolWarning && <Alert type="info" showIcon message={symbolWarning} style={{ marginTop: 12 }} />}
      <div className="symbol-search-results">{symbolResults.map(item => <div className="symbol-search-row" key={item.symbol}><div><strong>{item.symbol}</strong><span>{item.name} · {item.exchange}</span></div><Button disabled={!watchlistReady || Boolean(savingSymbol) || watchlist.includes(item.symbol)} loading={savingSymbol === item.symbol} onClick={() => { void toggleWatchlist(item.symbol, true) }}>{watchlist.includes(item.symbol) ? '已自选' : '加入自选'}</Button></div>)}</div>
      {/^[A-Za-z0-9][A-Za-z0-9.-]{0,19}$/.test(symbolQuery.trim()) && <Button style={{ marginTop: 12 }} disabled={!watchlistReady || Boolean(savingSymbol) || watchlist.includes(symbolQuery.trim().toUpperCase().replaceAll('.', '-'))} loading={Boolean(savingSymbol)} onClick={() => { void toggleWatchlist(symbolQuery.trim().toUpperCase().replaceAll('.', '-'), true) }}>按代码直接添加 {symbolQuery.trim().toUpperCase()}</Button>}
    </Modal>
    <Modal title="每日研究报告" open={reportOpen} onCancel={() => setReportOpen(false)} footer={null} width={760}><pre className="report-preview">{report}</pre></Modal>
  </div>
}
