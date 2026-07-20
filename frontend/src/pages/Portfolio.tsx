import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Col, Input, InputNumber, Popconfirm, Row, Spin, Statistic, Table, Tag, message } from 'antd'
import { DeleteOutlined, PlusOutlined, ReloadOutlined, SaveOutlined } from '@ant-design/icons'
import { getDailyDecision, getPortfolio, savePortfolio } from '../api'
import type { DailyDecision, DecisionAction, DecisionHolding, HoldingItem } from '../api'

const actionLabel: Record<DecisionAction, string> = { enter: '建仓', add: '加仓', hold: '持有', reduce: '减仓', exit: '退出', unavailable: '数据缺失' }
const actionColor: Record<DecisionAction, string> = { enter: 'var(--teal)', add: 'var(--accent)', hold: 'var(--blue)', reduce: 'var(--accent)', exit: 'var(--coral)', unavailable: 'var(--text-muted)' }
const money = (value?: number) => `$${(value || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
const pct = (value?: number) => `${((value || 0) * 100).toFixed(1)}%`

export default function Portfolio() {
  const [holdings, setHoldings] = useState<HoldingItem[]>([])
  const [decision, setDecision] = useState<DailyDecision | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    try {
      const [portfolio, snapshot] = await Promise.all([getPortfolio(), getDailyDecision()])
      setHoldings(portfolio.holdings || [])
      setDecision(snapshot)
    } catch { message.error('无法读取持仓或决策数据') } finally { setLoading(false) }
  }
  useEffect(() => { const timer = window.setTimeout(() => { void load() }, 0); return () => window.clearTimeout(timer) }, [])

  const persist = async (next: HoldingItem[]) => {
    setSaving(true)
    try {
      await savePortfolio(next)
      setHoldings(next)
      setDecision(await getDailyDecision())
    } catch (error: unknown) { message.error(error instanceof Error ? error.message : '持仓保存失败') } finally { setSaving(false) }
  }
  const update = (index: number, field: keyof HoldingItem, value: string | number) => setHoldings(current => current.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item))
  const add = () => setHoldings(current => [...current, { symbol: '', name: '', shares: 0, cost: 0 }])
  const remove = (index: number) => persist(holdings.filter((_, itemIndex) => itemIndex !== index))

  const allocation = useMemo(() => {
    const grouped: Record<string, number> = {}
    for (const item of decision?.holdings || []) grouped[item.sector || 'Unknown'] = (grouped[item.sector || 'Unknown'] || 0) + (item.market_value_usd || 0)
    const total = decision?.portfolio.current_value_usd || 0
    return Object.entries(grouped).sort((a, b) => b[1] - a[1]).map(([sector, value]) => ({ sector, value, pct: total ? value / total : 0 }))
  }, [decision])

  const columns = [
    { title: 'Ticker', dataIndex: 'symbol', width: 105, render: (_: unknown, __: HoldingItem, index: number) => <Input size="small" placeholder="AAPL" value={holdings[index].symbol} onChange={event => update(index, 'symbol', event.target.value.toUpperCase())} /> },
    { title: '名称', dataIndex: 'name', width: 125, render: (_: unknown, __: HoldingItem, index: number) => <Input size="small" placeholder="可留空" value={holdings[index].name || ''} onChange={event => update(index, 'name', event.target.value)} /> },
    { title: '股数', dataIndex: 'shares', width: 92, render: (_: unknown, __: HoldingItem, index: number) => <InputNumber size="small" min={0} value={holdings[index].shares} onChange={value => update(index, 'shares', value || 0)} style={{ width: '100%' }} /> },
    { title: '平均成本', dataIndex: 'cost', width: 112, render: (_: unknown, __: HoldingItem, index: number) => <InputNumber size="small" min={0} step={0.01} prefix="$" value={holdings[index].cost} onChange={value => update(index, 'cost', value || 0)} style={{ width: '100%' }} /> },
    { title: '', width: 52, render: (_: unknown, __: HoldingItem, index: number) => <Popconfirm title="删除这支持仓？" onConfirm={() => remove(index)}><Button size="small" danger icon={<DeleteOutlined />} aria-label="删除持仓" /></Popconfirm> },
  ]
  const holdingRows = (decision?.holdings || []).filter(item => item.action !== 'unavailable')

  if (loading) return <Spin size="large" style={{ display: 'block', marginTop: 120 }} />
  return <div className="portfolio-page">
    <div className="portfolio-toolbar"><div><Button icon={<PlusOutlined />} onClick={add}>添加持仓</Button><Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={() => persist(holdings)} style={{ marginLeft: 8 }}>保存并更新决策</Button></div><Button icon={<ReloadOutlined />} onClick={load}>刷新视图</Button></div>
    <Table dataSource={holdings} columns={columns} rowKey={(_, index) => String(index)} size="small" pagination={false} scroll={{ x: 650 }} />
    {!decision?.has_analysis && <Alert type="warning" showIcon message="尚无每日分析" description="持仓已保存；完成 NASDAQ 100 分析后，系统会显示动作与目标仓位。" style={{ marginTop: 16 }} />}
    {decision?.data_status.status === 'error' && <Alert type="error" showIcon message="最近刷新失败，正在使用上次成功的持仓决策" description={decision.data_status.message} style={{ marginTop: 16 }} />}
    <Row gutter={[12, 12]} className="decision-stats">
      <Col xs={12} lg={6}><Card size="small"><Statistic title="持仓市值" value={decision?.portfolio.current_value_usd || 0} prefix="$" precision={0} /></Card></Col>
      <Col xs={12} lg={6}><Card size="small"><Statistic title="当前仓位" value={pct(decision?.portfolio.current_pct)} /></Card></Col>
      <Col xs={12} lg={6}><Card size="small"><Statistic title="目标仓位" value={pct(decision?.portfolio.target_pct)} valueStyle={{ color: 'var(--accent)' }} /></Card></Col>
      <Col xs={12} lg={6}><Card size="small"><Statistic title="可投资资金" value={decision?.capital.investable_capital_usd || 0} prefix="$" precision={0} /></Card></Col>
    </Row>
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={17}><Card title="持仓动作"><Table dataSource={holdingRows} rowKey="symbol" size="small" pagination={false} scroll={{ x: 900 }} columns={[
        { title: 'Ticker', dataIndex: 'symbol', width: 92, render: (value: string) => <strong className="data-value">{value}</strong> },
        { title: '动作', dataIndex: 'action', width: 78, render: (value: DecisionAction) => <Tag className="action-tag" style={{ color: actionColor[value] }}>{actionLabel[value]}</Tag> },
        { title: '市值', dataIndex: 'market_value_usd', width: 98, render: (value: number) => <span className="data-value">{money(value)}</span> },
        { title: '当前 / 目标', key: 'weight', width: 130, render: (_: unknown, item: DecisionHolding) => <span className="data-value">{pct(item.current_pct)} <span className="muted-separator">/</span> {pct(item.target_pct)}</span> },
        { title: '调整金额', dataIndex: 'delta_value_usd', width: 105, render: (value: number) => <span className="data-value" style={{ color: value > 0 ? 'var(--teal)' : value < 0 ? 'var(--coral)' : 'var(--text-secondary)' }}>{value > 0 ? '+' : ''}{money(value)}</span> },
        { title: '止损', dataIndex: 'stop_loss', width: 82, render: (value: number) => <span className="data-value" style={{ color: 'var(--coral)' }}>{value ? `$${value.toFixed(2)}` : '-'}</span> },
        { title: '理由', dataIndex: 'reasons', render: (items: string[], item: DecisionHolding) => <span className="reason-text">{item.action === 'reduce' ? '当前权重超过单股 12% 上限' : items?.[0] || '-'}</span> },
      ]} /></Card></Col>
      <Col xs={24} xl={7}><Card title="行业暴露"><div className="allocation-list">{allocation.length ? allocation.map(item => <div key={item.sector}><div><span>{item.sector}</span><strong>{pct(item.pct)}</strong></div><div className="allocation-bar"><i style={{ width: `${Math.min(100, item.pct * 100)}%` }} /></div><small>{money(item.value)}</small></div>) : <div className="empty-decision">暂无可用持仓估值</div>}</div></Card></Col>
    </Row>
  </div>
}
