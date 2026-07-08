import { Card, Typography, Tag } from 'antd'

const { Title, Text, Paragraph } = Typography

const sectionStyle = { marginBottom: 16 }
const titleStyle = {
  marginTop: 0,
  color: 'var(--text-primary)',
  fontWeight: 700,
  fontFamily: 'var(--font-display)',
  fontSize: 16,
}
const textStyle = { color: 'var(--text-secondary)', marginBottom: 0 }
const labelStyle = { color: 'var(--text-primary)', fontWeight: 600, fontSize: 13 }

export default function About() {
  return (
    <div style={{ maxWidth: 760 }}>
      <Card style={sectionStyle} className="fade-in-up stagger-1">
        <Title level={4} style={titleStyle}>系统概述</Title>
        <Paragraph style={textStyle}>
          Topaz US 是一个本地运行的 NASDAQ 100 趋势质量筛选工具。第一版使用 yfinance 免费日线数据，
          以 QQQ 判断市场状态，只做多，不做机器学习训练。
        </Paragraph>
      </Card>

      <Card style={sectionStyle} className="fade-in-up stagger-2">
        <Title level={4} style={titleStyle}>页面说明</Title>
        <div style={{ marginBottom: 16 }}>
          <Text style={labelStyle}>市场总览</Text>
          <Paragraph style={{ ...textStyle, marginTop: 4 }}>
            展示 QQQ 行情、日线图、趋势状态、买入评分阈值和建议总仓位。
          </Paragraph>
        </div>
        <div style={{ marginBottom: 16 }}>
          <Text style={labelStyle}>NASDAQ 100</Text>
          <Paragraph style={{ ...textStyle, marginTop: 4 }}>
            对静态股票池进行评分排名。支持 ticker / 名称搜索、建议筛选、刷新分析、报告预览和 Slack 发送。
          </Paragraph>
        </div>
        <div style={{ marginBottom: 0 }}>
          <Text style={labelStyle}>我的组合</Text>
          <Paragraph style={{ ...textStyle, marginTop: 4 }}>
            管理本地持仓并按同一趋势质量体系计算盈亏、板块分布和持仓建议。
          </Paragraph>
        </div>
      </Card>

      <Card style={sectionStyle} className="fade-in-up stagger-3">
        <Title level={4} style={titleStyle}>评分体系</Title>
        <Paragraph style={textStyle}>
          综合评分 ={' '}
          <Tag style={{ borderRadius: 'var(--radius-sm)', background: 'rgba(212,164,76,0.12)', color: '#d4a44c', border: 'none' }}>趋势结构</Tag>{' '}
          <Tag style={{ borderRadius: 'var(--radius-sm)', background: 'rgba(107,159,212,0.12)', color: '#6b9fd4', border: 'none' }}>相对强弱</Tag>{' '}
          <Tag style={{ borderRadius: 'var(--radius-sm)', background: 'rgba(78,201,168,0.12)', color: '#4ec9a8', border: 'none' }}>动量</Tag>{' '}
          <Tag style={{ borderRadius: 'var(--radius-sm)', background: 'rgba(122,120,112,0.12)', color: '#7a7870', border: 'none' }}>入场质量</Tag>{' '}
          <Tag style={{ borderRadius: 'var(--radius-sm)', background: 'rgba(224,112,87,0.12)', color: '#e07057', border: 'none' }}>风险扣分</Tag>
        </Paragraph>
        <div style={{ marginBottom: 12 }}>
          <Text style={labelStyle}>趋势结构</Text>
          <Paragraph style={{ ...textStyle, marginTop: 2 }}>
            价格是否位于 MA20、MA50、MA200 上方，并检查 MA20 {'>'} MA50 {'>'} MA200。
          </Paragraph>
        </div>
        <div style={{ marginBottom: 12 }}>
          <Text style={labelStyle}>相对强弱与动量</Text>
          <Paragraph style={{ ...textStyle, marginTop: 2 }}>
            比较 20 日、60 日、120 日收益，并加入相对 QQQ 的横截面排名。
          </Paragraph>
        </div>
        <div style={{ marginBottom: 0 }}>
          <Text style={labelStyle}>市场过滤</Text>
          <Paragraph style={{ ...textStyle, marginTop: 2 }}>
            如果 QQQ 低于 MA200，系统不会给出主动买入信号，只保留关注或观望。
          </Paragraph>
        </div>
      </Card>

      <Card className="fade-in-up stagger-4">
        <Text style={{ color: 'var(--text-muted)', fontSize: 12 }}>
          免责声明：本工具仅供学习研究参考，不构成任何投资建议。免费数据源可能延迟、缺失或偶发失败。
        </Text>
      </Card>
    </div>
  )
}
