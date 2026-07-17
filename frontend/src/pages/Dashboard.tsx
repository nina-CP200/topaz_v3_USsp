import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Card, Col, Progress, Row, Spin, Statistic, Table, Tag, message } from 'antd'
import { ExclamationCircleOutlined, ReloadOutlined, SafetyCertificateOutlined, StopOutlined } from '@ant-design/icons'
import { getAnalysisStatus, getDailyDecision, refreshAnalysis } from '../api'
import type { DailyDecision, DecisionAction, DecisionCandidate } from '../api'

const actionLabel: Record<DecisionAction, string> = {
  enter: '建仓', add: '加仓', hold: '持有', reduce: '减仓', exit: '退出', unavailable: '数据缺失',
}
const actionColor: Record<DecisionAction, string> = {
  enter: 'var(--teal)', add: 'var(--accent)', hold: 'var(--blue)', reduce: 'var(--accent)', exit: 'var(--coral)', unavailable: 'var(--text-muted)',
}
const money = (value?: number) => `$${(value || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
const pct = (value?: number) => `${((value || 0) * 100).toFixed(0)}%`

export default function Dashboard() {
  const [data, setData] = useState<DailyDecision | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [progress, setProgress] = useState(0)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = async () => {
    try { setData(await getDailyDecision()) } catch { message.error('无法读取每日决策数据') } finally { setLoading(false) }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => { void load() }, 0)
    return () => { window.clearTimeout(timer); if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const refresh = async () => {
    setRefreshing(true)
    setProgress(2)
    try {
      await refreshAnalysis()
      pollRef.current = setInterval(async () => {
        try {
          const status = await getAnalysisStatus()
          if (status.status === 'done' || status.status === 'error') {
            if (pollRef.current) clearInterval(pollRef.current)
            pollRef.current = null
            setRefreshing(false)
            setProgress(100)
            await load()
            if (status.status === 'error') message.error(`分析失败：${status.message}`)
          } else {
            setProgress(value => Math.min(95, Math.max(value + 7, status.progress || 0)))
          }
        } catch { /* keep the existing snapshot visible while polling */ }
      }, 2200)
    } catch (error: unknown) {
      setRefreshing(false)
      message.error(error instanceof Error ? error.message : '触发分析失败')
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', marginTop: 120 }} />
  const market = data?.market || {}
  const candidates = data?.candidates || []
  const holdings = data?.holdings || []
  const urgent = holdings.filter(item => item.action === 'exit' || item.action === 'reduce')

  const candidateColumns = [
    { title: '#', dataIndex: 'rank', width: 48 },
    { title: 'Ticker', dataIndex: 'symbol', width: 92, render: (value: string) => <strong className="data-value">{value}</strong> },
    { title: '名称', dataIndex: 'name', width: 130 },
    { title: '动作', dataIndex: 'action', width: 80, render: (value: DecisionAction) => <Tag className="action-tag" style={{ color: actionColor[value] }}>{actionLabel[value]}</Tag> },
    { title: '目标仓位', dataIndex: 'target_pct', width: 92, render: (value: number) => <span className="data-value">{pct(value)}</span> },
    { title: '目标金额', dataIndex: 'target_value_usd', width: 110, render: (value: number) => <span className="data-value">{money(value)}</span> },
    { title: '入场 / 止损', key: 'levels', width: 150, render: (_: unknown, item: DecisionCandidate) => <span className="data-value">{item.entry_price ? `$${item.entry_price.toFixed(2)}` : '-'} <span className="muted-separator">/</span> <span style={{ color: 'var(--coral)' }}>{item.stop_loss ? `$${item.stop_loss.toFixed(2)}` : '-'}</span></span> },
    { title: '理由', dataIndex: 'reasons', render: (items: string[]) => <span className="reason-text">{items?.slice(0, 2).join(' · ') || '-'}</span> },
  ]

  return (
    <div className="decision-page">
      {refreshing && <div className="analysis-progress"><Progress percent={progress} size="small" showInfo={false} /><span>正在扫描 NASDAQ 100 日线信号…</span></div>}
      {!data?.has_analysis && <Alert type="warning" showIcon message="暂无可用分析" description="先运行一次分析，决策台会保留最近一次成功的结果。" style={{ marginBottom: 16 }} />}
      {data?.data_status.status === 'error' && <Alert type="error" showIcon message="最近一次刷新失败" description={data.data_status.message || '正在保留上一次成功的分析结果。'} style={{ marginBottom: 16 }} />}

      <section className={`market-gate ${market.entry_allowed ? 'gate-open' : 'gate-closed'}`}>
        <div>
          <div className="eyebrow">QQQ MARKET GATE</div>
          <div className="gate-title">{market.entry_allowed ? '允许寻找新的多头建仓' : '暂停新的多头建仓'}</div>
          <div className="gate-copy">{market.description || (market.entry_allowed ? 'QQQ 位于 MA200 上方，入场信号可以参与排序。' : 'QQQ 未通过 MA200 门槛，系统只保留观察和持仓管理。')}</div>
        </div>
        <div className="gate-metrics">
          <div><span>建议总仓位</span><strong>{pct(market.recommended_position_pct)}</strong></div>
          <div><span>当前已用</span><strong>{pct(data?.portfolio.current_pct)}</strong></div>
          <div><span>QQQ / MA200</span><strong>{market.qqq_above_ma200 ? 'Above' : 'Below'}</strong></div>
          <Button type="primary" icon={<ReloadOutlined />} loading={refreshing} onClick={refresh}>刷新分析</Button>
        </div>
      </section>

      <Row gutter={[12, 12]} className="decision-stats">
        <Col xs={12} lg={6}><Card size="small"><Statistic title="可投资资金" value={data?.capital.investable_capital_usd || 0} prefix="$" precision={0} /></Card></Col>
        <Col xs={12} lg={6}><Card size="small"><Statistic title="目标配置" value={data?.portfolio.target_value_usd || 0} prefix="$" precision={0} /></Card></Col>
        <Col xs={12} lg={6}><Card size="small"><Statistic title="有效候选" value={candidates.length} prefix={<SafetyCertificateOutlined />} valueStyle={{ color: 'var(--teal)' }} /></Card></Col>
        <Col xs={12} lg={6}><Card size="small"><Statistic title="需处理持仓" value={urgent.length} prefix={<ExclamationCircleOutlined />} valueStyle={{ color: urgent.length ? 'var(--coral)' : 'var(--text-secondary)' }} /></Card></Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={urgent.length ? 16 : 24}>
          <Card title="今日可执行候选" extra={<span className="card-meta">{data?.analysis_date || '未分析'}</span>}>
            {market.entry_allowed ? <Table dataSource={candidates} columns={candidateColumns} rowKey="symbol" size="small" pagination={false} scroll={{ x: 900 }} locale={{ emptyText: '今天没有符合策略条件的建仓候选' }} /> : <div className="empty-decision"><StopOutlined /> 市场门槛未通过。不会产生建仓或加仓建议。</div>}
          </Card>
        </Col>
        {urgent.length > 0 && <Col xs={24} xl={8}>
          <Card title="持仓优先处理">
            <div className="action-list">
              {urgent.map(item => <div className="action-row" key={item.symbol}>
                <div><Tag className="action-tag" style={{ color: actionColor[item.action] }}>{actionLabel[item.action]}</Tag><strong>{item.symbol}</strong><span>{item.name}</span></div>
                <div className="action-reason">{item.reasons?.[0] || (item.action === 'exit' ? 'Liquidity exit warning' : '仓位超过单股上限')}</div>
              </div>)}
            </div>
          </Card>
        </Col>}
      </Row>

      <div className="snapshot-footnote">数据时间：{data?.analysis_date || '暂无'} · 当前策略仅供研究与手工决策，不连接券商或自动下单。</div>
    </div>
  )
}
