import { useEffect, useState, useCallback } from 'react'
import {
  Table, Button, InputNumber, Input, message, Spin,
  Card, Row, Col, Statistic, Tag, Popconfirm, Typography,
} from 'antd'
import { PlusOutlined, DeleteOutlined, ThunderboltOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { getPortfolio, savePortfolio, analyzePortfolio } from '../api'
import type { HoldingItem, PortfolioAnalysis } from '../api'

const { Text } = Typography

const adviceColors: Record<string, string> = {
  '建议买入': 'rgba(212, 164, 76, 0.12)',
  '可以关注': 'rgba(107, 159, 212, 0.12)',
  '建议观望': 'rgba(122, 120, 112, 0.12)',
  '建议回避': 'rgba(224, 112, 87, 0.12)',
}
const adviceTextColors: Record<string, string> = {
  '建议买入': '#c09040',
  '可以关注': '#6b9fd4',
  '建议观望': '#7a7870',
  '建议回避': '#e07057',
}

const LOCAL_KEY = 'topaz_portfolio'

export default function Portfolio() {
  const [holdings, setHoldings] = useState<HoldingItem[]>([])
  const [loading, setLoading] = useState(true)
  const [analysis, setAnalysis] = useState<PortfolioAnalysis | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [saving, setSaving] = useState(false)

  const loadFromLocal = useCallback(() => {
    const saved = localStorage.getItem(LOCAL_KEY)
    if (saved) {
      try { return JSON.parse(saved) as HoldingItem[] } catch { return null }
    }
    return null
  }, [])

  useEffect(() => {
    const local = loadFromLocal()
    if (local) {
      setHoldings(local)
      setLoading(false)
    }
    getPortfolio()
      .then(r => {
        if (r.holdings?.length) {
          setHoldings(r.holdings)
          localStorage.setItem(LOCAL_KEY, JSON.stringify(r.holdings))
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [loadFromLocal])

  const persistToBackend = useCallback((list: HoldingItem[]) => {
    setSaving(true)
    localStorage.setItem(LOCAL_KEY, JSON.stringify(list))
    savePortfolio(list)
      .catch(() => message.warning('后端保存失败，已保留本地数据'))
      .finally(() => setSaving(false))
  }, [])

  const addRow = () => {
    const newHolding: HoldingItem = { symbol: '', name: '', shares: 100, cost: 10 }
    const list = [...holdings, newHolding]
    setHoldings(list)
  }

  const deleteRow = (idx: number) => {
    const list = holdings.filter((_, i) => i !== idx)
    setHoldings(list)
    persistToBackend(list)
  }

  const updateField = (idx: number, field: keyof HoldingItem, value: string | number) => {
    const list = holdings.map((h, i) => (i === idx ? { ...h, [field]: value } : h))
    setHoldings(list)
  }

  const handleAnalyze = () => {
    if (!holdings.length) { message.warning('请先添加持仓'); return }
    setAnalyzing(true)
    persistToBackend(holdings)
    analyzePortfolio(holdings)
      .then(setAnalysis)
      .catch((e: any) => message.error(e?.response?.data?.detail || '分析失败'))
      .finally(() => setAnalyzing(false))
  }

  const columns = [
    {
      title: '代码', dataIndex: 'symbol', key: 'symbol', width: 110,
      render: (_: any, __: any, idx: number) => (
        <Input
          size="small"
          placeholder="如 600519"
          value={holdings[idx].symbol}
          onChange={e => updateField(idx, 'symbol', e.target.value)}
          onBlur={() => persistToBackend(holdings)}
        />
      ),
    },
    {
      title: '名称', dataIndex: 'name', key: 'name', width: 110,
      render: (_: any, __: any, idx: number) => (
        <Input
          size="small"
          placeholder="自动填充"
          value={holdings[idx].name}
          onChange={e => updateField(idx, 'name', e.target.value)}
          onBlur={() => persistToBackend(holdings)}
        />
      ),
    },
    {
      title: '股数', dataIndex: 'shares', key: 'shares', width: 90,
      render: (_: any, __: any, idx: number) => (
        <InputNumber
          size="small"
          min={1}
          value={holdings[idx].shares}
          onChange={v => updateField(idx, 'shares', v || 0)}
          onBlur={() => persistToBackend(holdings)}
          style={{ width: '100%' }}
        />
      ),
    },
    {
      title: '成本价', dataIndex: 'cost', key: 'cost', width: 100,
      render: (_: any, __: any, idx: number) => (
        <InputNumber
          size="small"
          min={0.01}
          step={0.01}
          value={holdings[idx].cost}
          onChange={v => updateField(idx, 'cost', v || 0)}
          onBlur={() => persistToBackend(holdings)}
          style={{ width: '100%' }}
          prefix="\u00a5"
        />
      ),
    },
    {
      title: '', key: 'action', width: 50,
      render: (_: any, __: any, idx: number) => (
        <Popconfirm title="删除这支持仓？" onConfirm={() => deleteRow(idx)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ]

  if (loading) return <Spin size="large" style={{ display: 'block', marginTop: 120 }} />

  return (
    <div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        marginBottom: 16,
      }}>
        <Button icon={<PlusOutlined />} onClick={addRow}>添加持仓</Button>
        <Button
          type="primary"
          icon={<ThunderboltOutlined />}
          loading={analyzing}
          onClick={handleAnalyze}
        >
          分析当前组合
        </Button>
        {saving && <Spin size="small" />}
      </div>

      <Table
        dataSource={holdings}
        columns={columns}
        rowKey={(_, idx) => String(idx)}
        size="small"
        pagination={false}
        style={{ marginBottom: 24 }}
      />

      {analysis && (
        <div className="fade-in-up">
          {(analysis as any).failed?.length > 0 && (
            <Card size="small" style={{ marginBottom: 16 }}>
              <Text type="danger" strong>以下股票分析失败：</Text>
              {(analysis as any).failed.map((f: any, i: number) => (
                <div key={i} style={{ marginTop: 4, color: 'var(--coral)' }}>代码 {f.code} — {f.reason}</div>
              ))}
            </Card>
          )}

          <Row gutter={12} style={{ marginBottom: 16 }} className="stagger-1">
            <Col span={4}><Card size="small"><Statistic title="总市值" value={analysis.total_value?.toFixed(2)} prefix="\u00a5" /></Card></Col>
            <Col span={4}><Card size="small"><Statistic title="总成本" value={analysis.total_cost?.toFixed(2)} prefix="\u00a5" /></Card></Col>
            <Col span={4}><Card size="small">
              <Statistic title="总盈亏" value={analysis.total_pnl?.toFixed(2)} prefix="\u00a5"
                valueStyle={{ color: analysis.total_pnl >= 0 ? 'var(--teal)' : 'var(--coral)' }} />
            </Card></Col>
            <Col span={4}><Card size="small">
              <Statistic title="盈亏%" value={analysis.total_pnl_pct?.toFixed(2)} suffix="%"
                valueStyle={{ color: analysis.total_pnl_pct >= 0 ? 'var(--teal)' : 'var(--coral)' }} />
            </Card></Col>
            <Col span={4}><Card size="small"><Statistic title="买入建议" value={analysis.buy_count} valueStyle={{ color: 'var(--accent)' }} /></Card></Col>
            <Col span={4}><Card size="small"><Statistic title="亏损数量" value={analysis.loss_count} valueStyle={{ color: 'var(--coral)' }} /></Card></Col>
          </Row>

          <Row gutter={16}>
            <Col xs={24} lg={8}>
              <Card title="行业分布" size="small" className="stagger-2">
                <ReactECharts
                  style={{ height: 280 }}
                  option={{
                    backgroundColor: 'transparent',
                    tooltip: {
                      trigger: 'item',
                      formatter: '{b}: {c}%',
                      backgroundColor: '#1e1e1c',
                      borderColor: '#2a2a28',
                      borderWidth: 1,
                      textStyle: { color: '#e8e6e1' },
                      extraCssText: 'box-shadow: 0 8px 24px rgba(0,0,0,0.4); border-radius: 6px;',
                    },
                    series: [{
                      type: 'pie',
                      radius: ['40%', '70%'],
                      itemStyle: {
                        borderRadius: 4,
                        borderColor: '#181816',
                        borderWidth: 2,
                      },
                      data: Object.entries(analysis.industry_allocation || {}).map(([k, v]) => ({
                        name: k,
                        value: +(v as any).pct?.toFixed(1) || 0,
                      })),
                      label: {
                        formatter: '{b}\n{d}%',
                        color: '#9a9890',
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 11,
                      },
                      emphasis: {
                        itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' },
                      },
                    }],
                  }}
                />
              </Card>
            </Col>
            <Col xs={24} lg={16}>
              <Card title="持仓建议" size="small" className="stagger-3">
                {analysis.holdings.map(h => (
                  <Card
                    key={h.symbol}
                    size="small"
                    style={{ marginBottom: 8 }}
                    className="glow-border"
                  >
                    <Row gutter={12} align="middle" style={{ marginBottom: 0 }}>
                      <Col flex="none" style={{ minWidth: 120 }}>
                        <Tag
                          style={{
                            borderRadius: 'var(--radius-sm)',
                            background: adviceColors[h.advice] || 'rgba(122,120,112,0.12)',
                            color: adviceTextColors[h.advice] || 'var(--text-secondary)',
                            border: 'none',
                            fontFamily: 'var(--font-mono)',
                            fontSize: 11,
                          }}
                        >{h.advice}</Tag>
                        <div style={{ marginTop: 4 }}>
                          <Text strong style={{ color: 'var(--text-primary)', fontSize: 14 }}>{h.name}</Text>
                          <Text style={{ color: 'var(--text-muted)', marginLeft: 6, fontSize: 12, fontFamily: 'var(--font-mono)' }}>{h.symbol}</Text>
                        </div>
                      </Col>
                      <Col flex="auto">
                        <Row gutter={16}>
                          <Col span={4}>
                            <div style={{ color: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>盈亏</div>
                            <span className="data-value" style={{ color: h.pnl >= 0 ? 'var(--teal)' : 'var(--coral)' }}>{h.pnl_pct?.toFixed(2)}%</span>
                          </Col>
                          <Col span={4}>
                            <div style={{ color: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>评分</div>
                            <span className="data-value" style={{ color: 'var(--text-primary)' }}>{h.composite_score?.toFixed(3)}</span>
                          </Col>
                          <Col span={4}>
                            <div style={{ color: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>现价</div>
                            <span className="data-value" style={{ color: 'var(--text-primary)' }}>\u00a5{h.current_price?.toFixed(2)}</span>
                          </Col>
                          <Col span={3}>
                            <div style={{ color: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>持股</div>
                            <span className="data-value" style={{ color: 'var(--text-primary)' }}>{h.shares}</span>
                          </Col>
                          <Col span={3}>
                            <div style={{ color: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>RSI</div>
                            <span className="data-value" style={{ color: 'var(--text-primary)' }}>{h.rsi?.toFixed(1)}</span>
                          </Col>
                          <Col span={6}>
                            <div style={{ color: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>理由</div>
                            <Text style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{h.reasons?.join('; ')}</Text>
                          </Col>
                        </Row>
                      </Col>
                    </Row>
                  </Card>
                ))}
              </Card>
            </Col>
          </Row>
        </div>
      )}
    </div>
  )
}
