import { useEffect, useState, useRef } from 'react'
import { Table, Tag, Spin, Input, Select, Button, message, Row, Col, Statistic, Card, Progress, Modal, Dropdown } from 'antd'
import { ReloadOutlined, ArrowUpOutlined, ArrowDownOutlined, SendOutlined, FileTextOutlined, DownOutlined } from '@ant-design/icons'
import { getDailyAnalysis, refreshAnalysis, getAnalysisReport, sendSlackReport, listSlackConfigs, getAnalysisStatus } from '../api'
import type { DailyAnalysis, SlackConfigItem } from '../api'

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

export default function Stocks() {
  const [data, setData] = useState<DailyAnalysis | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [search, setSearch] = useState('')
  const [adviceFilter, setAdviceFilter] = useState<string | undefined>(undefined)
  const [reportText, setReportText] = useState('')
  const [reportModal, setReportModal] = useState(false)
  const [sending, setSending] = useState(false)
  const [slackConfigs, setSlackConfigs] = useState<SlackConfigItem[]>([])
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = () => {
    setLoading(true)
    getDailyAnalysis()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  const doSend = async (config?: string) => {
    setSending(true)
    try {
      const r = await sendSlackReport(config)
      if (r.errors?.length) {
        message.warning({ content: r.message, duration: 4 })
        r.errors.forEach(e => message.error(e))
      } else {
        message.success(r.message)
      }
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '发送失败')
    }
    setSending(false)
  }

  useEffect(() => {
    load()
    listSlackConfigs().then(r => setSlackConfigs(r.configs || [])).catch(() => {})
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const pollStatus = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    setProgress(3)
    let tick = 0
    pollRef.current = setInterval(async () => {
      tick++
      try {
        const s = await getAnalysisStatus()
        if (s.status === 'done' || s.status === 'error') {
          if (pollRef.current) clearInterval(pollRef.current)
          pollRef.current = null
          setProgress(100)
          setRefreshing(false)
          setTimeout(load, 500)
          if (s.status === 'error') message.error(`分析失败: ${s.message}`)
          return
        }
      } catch {}
      setProgress(p => {
        const step = 100 - p
        const increment = Math.max(0.5, step * 0.08 + Math.random() * 1.5)
        return Math.min(p + increment, 99)
      })
    }, 2500)
  }

  const handleRefresh = () => {
    setRefreshing(true)
    setProgress(2)
    refreshAnalysis()
      .then(pollStatus)
      .catch(() => {
        setRefreshing(false)
        message.error('触发分析失败')
      })
  }

  const results = data?.results || []
  const filtered = results.filter(r => {
    if (search && !r.name.includes(search) && !r.symbol.includes(search)) return false
    if (adviceFilter && r.advice !== adviceFilter) return false
    return true
  })

  const columns = [
    { title: '排名', dataIndex: 'rank', key: 'rank', width: 56 },
    { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 100 },
    { title: '名称', dataIndex: 'name', key: 'name', width: 110 },
    { title: 'Sector', dataIndex: 'sector', key: 'sector', width: 150 },
    {
      title: 'Price', dataIndex: 'current_price', key: 'current_price', width: 76,
      render: (v: number) => <span className="data-value">{v?.toFixed(2)}</span>,
    },
    {
      title: 'Change', dataIndex: 'change_pct', key: 'change_pct', width: 80,
      render: (v: number) => (
        <span className="data-value" style={{ color: v >= 0 ? 'var(--teal)' : 'var(--coral)' }}>
          {v >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {Math.abs(v).toFixed(2)}%
        </span>
      ),
    },
    {
      title: 'Signal', dataIndex: 'signal_status', key: 'signal_status', width: 92,
      render: (v: string) => {
        const color = v === 'Active Long' ? 'var(--teal)' : v === 'Sweep' ? 'var(--accent)' : 'var(--text-muted)'
        return <span className="data-value" style={{ color }}>{v || 'No Signal'}</span>
      },
    },
    {
      title: 'Score', dataIndex: 'composite_score', key: 'composite_score', width: 86,
      sorter: (a: any, b: any) => a.composite_score - b.composite_score,
      render: (v: number) => {
        if (v == null) return '-'
        const color = v >= 75 ? 'var(--accent)' : v >= 65 ? 'var(--blue)' : 'var(--text-muted)'
        return <span className="data-value" style={{ color }}>{v?.toFixed(1)}</span>
      },
    },
    {
      title: 'Advice', dataIndex: 'advice', key: 'advice', width: 100,
      render: (v: string) => (
        <Tag
          style={{
            borderRadius: 'var(--radius-sm)',
            background: adviceColors[v] || 'rgba(122,120,112,0.12)',
            color: adviceTextColors[v] || 'var(--text-secondary)',
            border: 'none',
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
          }}
        >{v}</Tag>
      ),
    },
    {
      title: 'Position', dataIndex: 'position_pct', key: 'position_pct', width: 86,
      render: (v: number) => v ? <span className="data-value">{(v * 100).toFixed(0)}%</span> : '-',
    },
    {
      title: 'Entry', dataIndex: 'entry_price', key: 'entry_price', width: 76,
      render: (v: number | null) => v ? <span className="data-value">{v.toFixed(2)}</span> : '-',
    },
    {
      title: 'Stop', dataIndex: 'stop_loss', key: 'stop_loss', width: 76,
      render: (v: number | null) => v ? <span className="data-value" style={{ color: 'var(--coral)' }}>{v.toFixed(2)}</span> : '-',
    },
    {
      title: 'TP1', dataIndex: 'tp1', key: 'tp1', width: 76,
      render: (v: number | null) => v ? <span className="data-value" style={{ color: 'var(--teal)' }}>{v.toFixed(2)}</span> : '-',
    },
  ]

  return (
    <div>
      {refreshing && (
        <Card size="small" style={{ marginBottom: 16 }} className="fade-in-up">
          <Progress
            percent={progress}
            status="active"
            strokeColor={{
              '0%': '#d4a44c',
              '100%': '#e0b35e',
            }}
          />
          <div style={{
            textAlign: 'center',
            color: 'var(--text-muted)',
            marginTop: 4,
            fontSize: 12,
            fontFamily: 'var(--font-mono)',
            letterSpacing: '0.04em',
          }}>
            正在扫描 NASDAQ 100 回调吸筹与突破入场信号...
          </div>
        </Card>
      )}

      {data && (
        <Row gutter={12} style={{ marginBottom: 16 }} className="fade-in-up stagger-1">
          <Col span={6}><Card size="small"><Statistic title="Market Regime" value={data.market_regime} /></Card></Col>
          <Col span={6}><Card size="small"><Statistic title="Strategy" value="Moon + Liquidity Exit" /></Card></Col>
          <Col span={6}><Card size="small"><Statistic title="Breadth" value={`${(data.advance_ratio * 100).toFixed(1)}%`} /></Card></Col>
          <Col span={6}><Card size="small"><Statistic title="分析日期" value={data.date} /></Card></Col>
        </Row>
      )}

      <div style={{
        display: 'flex',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 8,
        marginBottom: 12,
      }}>
        <Input.Search
          placeholder="搜索 ticker / 名称"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ width: 200 }}
          allowClear
        />
        <Select
          placeholder="按建议筛选"
          value={adviceFilter}
          onChange={setAdviceFilter}
          allowClear
          style={{ width: 136 }}
          options={[
            { label: '建议买入', value: '建议买入' },
            { label: '可以关注', value: '可以关注' },
            { label: '建议观望', value: '建议观望' },
            { label: '建议回避', value: '建议回避' },
          ]}
        />
        <Button icon={<ReloadOutlined />} loading={refreshing} onClick={handleRefresh}>
          重新分析
        </Button>
        {data && (
          <>
            <Button icon={<FileTextOutlined />} onClick={async () => {
              const r = await getAnalysisReport()
              if (r.text) { setReportText(r.text); setReportModal(true) }
              else message.error(r.error || '暂无报告')
            }}>
              生成报告
            </Button>
            <Dropdown
              menu={{
                items: [
                  ...slackConfigs.map(c => ({
                    key: c.name, label: c.name,
                    onClick: () => doSend(c.name),
                  })),
                  slackConfigs.length > 1
                    ? { key: '__all__', label: '发送给全部', onClick: () => doSend() }
                    : null,
                ].filter(Boolean) as any,
              }}
              disabled={!slackConfigs.length}
            >
              <Button loading={sending} icon={<SendOutlined />}>
                {slackConfigs.length ? `Slack (${slackConfigs.length})` : 'Slack 未配置'} <DownOutlined />
              </Button>
            </Dropdown>
          </>
        )}
      </div>

      <Modal
        title="策略报告"
        open={reportModal}
        onCancel={() => setReportModal(false)}
        footer={null}
        width={700}
      >
        <pre style={{
          background: 'var(--bg-elevated)',
          color: 'var(--text-primary)',
          padding: 16,
          borderRadius: 'var(--radius)',
          fontSize: 12,
          lineHeight: 1.7,
          whiteSpace: 'pre-wrap',
          maxHeight: 500,
          overflow: 'auto',
          fontFamily: 'var(--font-mono)',
          border: '1px solid var(--border)',
        }}>{reportText}</pre>
      </Modal>

      {loading ? <Spin size="large" style={{ display: 'block', marginTop: 80 }} /> : (
        <Table
          dataSource={filtered}
          columns={columns}
          rowKey="symbol"
          size="small"
          scroll={{ y: 520 }}
          pagination={{ pageSize: 50, showSizeChanger: false }}
        />
      )}
    </div>
  )
}
