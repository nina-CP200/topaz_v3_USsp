import { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Spin, Tag } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined, RiseOutlined, FallOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { getMarketOverview, getMarketHistory } from '../api'
import type { MarketOverview, KLineItem } from '../api'

const regimeColors: Record<string, string> = {
  bull: '#4ec9a8',
  recovery: '#6b9fd4',
  pullback: '#d4a44c',
  sideways: '#7a7870',
  bear: '#e07057',
}

const regimeLabels: Record<string, string> = {
  bull: '牛市',
  pullback: '回调',
  sideways: '震荡',
  bear: '熊市',
}

function formatDate(dateStr: string) {
  if (!dateStr) return ''
  return dateStr.slice(5)
}

export default function Dashboard() {
  const [overview, setOverview] = useState<MarketOverview | null>(null)
  const [klineData, setKlineData] = useState<KLineItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getMarketOverview(), getMarketHistory(60)])
      .then(([ov, hist]) => {
        setOverview(ov)
        setKlineData(hist.data || [])
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', marginTop: 120 }} />

  return (
    <div>
      {/* Hero Index Card */}
      <Card
        style={{ marginBottom: 16 }}
        className="fade-in-up stagger-1"
      >
        <Row align="middle" gutter={24}>
          <Col flex="none" style={{ minWidth: 220 }}>
            <div style={{
              color: 'var(--text-muted)',
              fontSize: 11,
              fontFamily: 'var(--font-mono)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              marginBottom: 4,
            }}>
              {overview?.index_name}
            </div>
            <div style={{
              fontSize: 42,
              fontWeight: 700,
              lineHeight: 1,
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)',
              letterSpacing: '-0.02em',
              fontVariantNumeric: 'tabular-nums',
            }}>
              {overview?.index_price?.toFixed(2)}
            </div>
            <Tag
              color={overview && overview.index_change_pct >= 0 ? 'rgba(78, 201, 168, 0.15)' : 'rgba(224, 112, 87, 0.15)'}
              style={{
                fontSize: 13,
                padding: '2px 10px',
                marginTop: 10,
                borderRadius: 'var(--radius-sm)',
                color: overview && overview.index_change_pct >= 0 ? 'var(--teal)' : 'var(--coral)',
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
              }}
            >
              {overview && overview.index_change_pct >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
              {' '}{overview ? Math.abs(overview.index_change_pct).toFixed(2) : '-'}%
            </Tag>
          </Col>
          <Col flex="auto">
            <Row gutter={32}>
              <Col span={6}>
                <Statistic
                  title="开盘"
                  value={overview?.index_open?.toFixed(2)}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="昨收"
                  value={overview?.index_prev_close?.toFixed(2)}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="最高"
                  value={overview?.index_high?.toFixed(2)}
                  valueStyle={{ color: 'var(--teal)' }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="最低"
                  value={overview?.index_low?.toFixed(2)}
                  valueStyle={{ color: 'var(--coral)' }}
                />
              </Col>
            </Row>
          </Col>
          <Col flex="none" style={{
            textAlign: 'right',
            paddingLeft: 24,
            borderLeft: '1px solid var(--border)',
          }}>
            <div style={{
              color: 'var(--text-muted)',
              fontSize: 11,
              fontFamily: 'var(--font-mono)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              marginBottom: 4,
            }}>
              市场状态
            </div>
            <Tag color={regimeColors[overview?.regime || ''] || 'var(--text-muted)'} style={{
              fontSize: 13,
              padding: '2px 10px',
              borderRadius: 'var(--radius-sm)',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
            }}>
              {regimeLabels[overview?.regime || ''] || overview?.regime}
            </Tag>
          </Col>
        </Row>
      </Card>

      {/* Chart + Thresholds */}
      <Row gutter={16}>
        <Col xs={24} lg={16}>
          <Card
            title="QQQ Daily Chart"
            style={{ marginBottom: 16 }}
            className="fade-in-up stagger-2"
          >
            <ReactECharts
              style={{ height: 380 }}
              option={{
                backgroundColor: 'transparent',
                tooltip: {
                  trigger: 'axis',
                  backgroundColor: '#1e1e1c',
                  borderColor: '#2a2a28',
                  borderWidth: 1,
                  textStyle: {
                    color: '#e8e6e1',
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 12,
                  },
                  extraCssText: 'box-shadow: 0 8px 24px rgba(0,0,0,0.4); border-radius: 6px;',
                },
                xAxis: {
                  type: 'category',
                  data: klineData.map(d => formatDate(d.date)),
                  axisLabel: {
                    color: '#5e5c56',
                    fontSize: 10,
                    fontFamily: "'JetBrains Mono', monospace",
                  },
                  axisLine: { lineStyle: { color: '#2a2a28', width: 1 } },
                  axisTick: { show: false },
                  splitLine: { show: false },
                },
                yAxis: {
                  type: 'value',
                  scale: true,
                  axisLabel: {
                    color: '#5e5c56',
                    fontSize: 10,
                    fontFamily: "'JetBrains Mono', monospace",
                  },
                  axisLine: { show: false },
                  axisTick: { show: false },
                  splitLine: {
                    lineStyle: { color: '#1e1e1c', type: 'solid', width: 1 },
                  },
                },
                grid: { left: 50, right: 20, bottom: 40, top: 10 },
                dataZoom: [{ type: 'inside' }],
                series: [{
                  type: 'candlestick',
                  data: klineData.map(d => [d.open, d.close, d.low, d.high]),
                  itemStyle: {
                    color: '#4ec9a8',
                    color0: '#e07057',
                    borderColor: '#4ec9a8',
                    borderColor0: '#e07057',
                  },
                }],
              }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Row gutter={[0, 16]}>
            <Col span={24} className="fade-in-up stagger-3">
              <Card>
                <Statistic
                  title="Buy Score Threshold"
                  value={overview?.buy_threshold?.toFixed(0)}
                  prefix={<RiseOutlined />}
                  valueStyle={{ color: 'var(--teal)' }}
                />
              </Card>
            </Col>
            <Col span={24} className="fade-in-up stagger-4">
              <Card>
                <Statistic
                  title="Avoid Score Threshold"
                  value={overview?.sell_threshold?.toFixed(0)}
                  prefix={<FallOutlined />}
                  valueStyle={{ color: 'var(--coral)' }}
                />
              </Card>
            </Col>
            <Col span={24} className="fade-in-up stagger-5">
              <Card>
                <Statistic
                  title="Suggested Gross Exposure"
                  value={overview?.position_max ? `${(overview.position_max * 100).toFixed(0)}%` : '-'}
                />
              </Card>
            </Col>
          </Row>
        </Col>
      </Row>

      {/* Market Sentiment */}
      <Card
        title="NASDAQ 100 Breadth"
        style={{ marginTop: 16 }}
        className="fade-in-up stagger-5"
      >
        <Row gutter={24}>
          <Col span={4}>
            <Statistic
              title="Advancing Ratio"
              value={overview?.sentiment_advance_ratio ? `${(overview.sentiment_advance_ratio * 100).toFixed(1)}%` : '-'}
            />
          </Col>
          <Col span={5}>
            <Statistic
              title="Advancing"
              value={overview?.sentiment_up_count || 0}
              valueStyle={{ color: 'var(--teal)' }}
            />
          </Col>
          <Col span={5}>
            <Statistic
              title="Declining"
              value={overview?.sentiment_down_count || 0}
              valueStyle={{ color: 'var(--coral)' }}
            />
          </Col>
          <Col span={5}>
            <Statistic
              title="Limit Up"
              value={overview?.sentiment_limit_up || 0}
              valueStyle={{ color: 'var(--teal)' }}
            />
          </Col>
          <Col span={5}>
            <Statistic
              title="Limit Down"
              value={overview?.sentiment_limit_down || 0}
              valueStyle={{ color: 'var(--coral)' }}
            />
          </Col>
        </Row>
      </Card>
    </div>
  )
}
