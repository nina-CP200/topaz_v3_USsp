import { useEffect, useMemo, useState } from 'react'
import { Alert, Card, Col, Row, Spin, Statistic, Tag } from 'antd'
import { ExperimentOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { getLatestResearch } from '../api'
import type { ResearchResult, ResearchSnapshot } from '../api'

const metric = (value: unknown, suffix = '%') => typeof value === 'number' ? `${value.toFixed(2)}${suffix}` : '-'

function SummaryCard({ title, result, experimental = false }: { title: string; result: ResearchResult; experimental?: boolean }) {
  const summary = result.summary
  return <Card title={<span>{title} {experimental && <Tag color="warning">实验性</Tag>}</span>} extra={<span className="card-meta">{result.source}</span>}>
    <Row gutter={[12, 16]}>
      <Col span={8}><Statistic title="组合收益" value={metric(summary.portfolio_return_pct)} valueStyle={{ color: Number(summary.portfolio_return_pct) >= 0 ? 'var(--teal)' : 'var(--coral)' }} /></Col>
      <Col span={8}><Statistic title="最大回撤" value={metric(summary.portfolio_max_drawdown_pct)} valueStyle={{ color: 'var(--coral)' }} /></Col>
      <Col span={8}><Statistic title="平均持仓" value={metric(summary.average_invested_pct)} /></Col>
      <Col span={8}><Statistic title="交易数量" value={Number(summary.trade_count) || 0} /></Col>
      <Col span={8}><Statistic title="最大持仓数" value={Number(summary.max_positions_used) || 0} /></Col>
      <Col span={8}><Statistic title="样本股票" value={Number(summary.symbols_tested) || 0} /></Col>
    </Row>
  </Card>
}

export default function Research() {
  const [data, setData] = useState<ResearchSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => { getLatestResearch().then(setData).finally(() => setLoading(false)) }, [])
  const chartOption = useMemo(() => {
    const baseline = data?.baseline?.daily_exposure || []
    const overlay = data?.momentum_overlay?.daily_exposure || []
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', backgroundColor: '#1e1e1c', borderColor: '#2a2a28', textStyle: { color: '#e8e6e1' } },
      legend: { data: ['基线持仓', '实验覆盖层'], textStyle: { color: '#9a9890' }, right: 8 },
      grid: { left: 48, right: 24, top: 38, bottom: 32 },
      xAxis: { type: 'category', data: baseline.map(item => item.date.slice(5)), axisLabel: { color: '#5e5c56', fontSize: 10 }, axisLine: { lineStyle: { color: '#2a2a28' } }, axisTick: { show: false } },
      yAxis: { type: 'value', min: 0, max: 100, axisLabel: { color: '#5e5c56', formatter: '{value}%' }, splitLine: { lineStyle: { color: '#202020' } } },
      series: [
        { name: '基线持仓', type: 'line', smooth: true, symbol: 'none', data: baseline.map(item => item.invested_pct), lineStyle: { color: '#d4a44c', width: 2 }, areaStyle: { color: 'rgba(212,164,76,0.08)' } },
        ...(overlay.length ? [{ name: '实验覆盖层', type: 'line', smooth: true, symbol: 'none', data: overlay.map(item => item.invested_pct), lineStyle: { color: '#6b9fd4', width: 2 } }] : []),
      ],
    }
  }, [data])

  if (loading) return <Spin size="large" style={{ display: 'block', marginTop: 120 }} />
  if (!data?.available || !data.baseline) return <Alert type="info" showIcon icon={<ExperimentOutlined />} message="尚无当前策略的已保存回测" description={data?.message || '研究页不会自动运行耗时回测。'} />
  const lowExposure = data.baseline.summary.low_exposure_periods as Array<Record<string, unknown>> | undefined
  return <div className="research-page">
    <Alert type="warning" showIcon message="研究信息不参与实时建仓门槛" description="实验性市场动量覆盖层仅用于比较，实时决策继续使用 QQQ MA200 与 Moon + Liquidity Exit。" style={{ marginBottom: 16 }} />
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={data.momentum_overlay ? 12 : 24}><SummaryCard title="Moon + Liquidity 基线" result={data.baseline} /></Col>
      {data.momentum_overlay && <Col xs={24} xl={12}><SummaryCard title="市场动量覆盖层" result={data.momentum_overlay} experimental /></Col>}
    </Row>
    <Card title="组合持仓暴露" style={{ marginTop: 16 }}><ReactECharts option={chartOption} style={{ height: 340 }} /></Card>
    <Card title="低暴露区间" style={{ marginTop: 16 }}>
      <div className="period-list">{lowExposure?.length ? lowExposure.slice(0, 12).map((period, index) => <div key={`${period.start}-${index}`}><strong>{String(period.start)} - {String(period.end)}</strong><span>{Number(period.average_invested_pct || 0).toFixed(1)}% 平均持仓 · {String(period.trading_days)} 个交易日</span></div>) : <span className="reason-text">该回测文件没有保存低暴露区间。</span>}</div>
    </Card>
  </div>
}
