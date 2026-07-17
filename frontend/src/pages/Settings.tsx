import { useEffect, useState } from 'react'
import { Button, Card, Input, InputNumber, Popconfirm, Spin, Table, message } from 'antd'
import { DeleteOutlined, PlusOutlined, SaveOutlined } from '@ant-design/icons'
import { getDecisionSettings, listSlackConfigs, saveDecisionSettings, saveSlackConfigs } from '../api'
import type { SlackConfigItem } from '../api'

export default function Settings() {
  const [capital, setCapital] = useState(100_000)
  const [configs, setConfigs] = useState<SlackConfigItem[]>([])
  const [loading, setLoading] = useState(true)
  const [savingCapital, setSavingCapital] = useState(false)
  const [savingSlack, setSavingSlack] = useState(false)

  useEffect(() => {
    Promise.all([getDecisionSettings(), listSlackConfigs()])
      .then(([settings, slack]) => { setCapital(settings.investable_capital_usd); setConfigs(slack.configs || []) })
      .catch(() => message.warning('部分本地设置无法读取'))
      .finally(() => setLoading(false))
  }, [])

  const updateConfig = (index: number, field: keyof SlackConfigItem, value: string) => setConfigs(current => current.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item))
  const slackColumns = [
    { title: '配置名称', dataIndex: 'name', width: 140, render: (_: unknown, __: SlackConfigItem, index: number) => <Input size="small" value={configs[index].name} onChange={event => updateConfig(index, 'name', event.target.value)} /> },
    { title: 'Bot Token', dataIndex: 'token', render: (_: unknown, __: SlackConfigItem, index: number) => <Input.Password size="small" placeholder="xoxb-…" value={configs[index].token} onChange={event => updateConfig(index, 'token', event.target.value)} /> },
    { title: '频道 ID', dataIndex: 'channel', width: 150, render: (_: unknown, __: SlackConfigItem, index: number) => <Input size="small" placeholder="C0…" value={configs[index].channel} onChange={event => updateConfig(index, 'channel', event.target.value)} /> },
    { title: '', width: 52, render: (_: unknown, __: SlackConfigItem, index: number) => <Popconfirm title="删除此配置？" onConfirm={() => setConfigs(current => current.filter((__, itemIndex) => itemIndex !== index))}><Button size="small" danger icon={<DeleteOutlined />} aria-label="删除通知配置" /></Popconfirm> },
  ]

  if (loading) return <Spin size="large" style={{ display: 'block', marginTop: 120 }} />
  return <div className="settings-page">
    <Card title="决策资金">
      <div className="setting-line"><div><strong>可投资总额</strong><span>USD</span></div><InputNumber min={0} precision={0} prefix="$" value={capital} onChange={value => setCapital(value || 0)} style={{ width: 220 }} /><Button type="primary" icon={<SaveOutlined />} loading={savingCapital} onClick={async () => { setSavingCapital(true); try { await saveDecisionSettings({ investable_capital_usd: capital }); message.success('资金规模已保存') } catch { message.error('保存失败') } finally { setSavingCapital(false) } }}>保存</Button></div>
      <div className="settings-note">该金额只用于换算建议目标金额；系统不会连接券商或生成订单。</div>
    </Card>
    <Card title="Slack 通知" style={{ marginTop: 16 }}>
      <Table dataSource={configs} columns={slackColumns} rowKey={(_, index) => String(index)} size="small" pagination={false} scroll={{ x: 660 }} />
      <div style={{ marginTop: 12 }}><Button icon={<PlusOutlined />} onClick={() => setConfigs(current => [...current, { name: '', token: '', channel: '' }])}>添加配置</Button><Button type="primary" loading={savingSlack} onClick={async () => { if (configs.some(item => !item.name)) { message.warning('请填写每个配置的名称'); return }; setSavingSlack(true); try { await saveSlackConfigs(configs); message.success('通知配置已保存') } catch { message.error('保存失败') } finally { setSavingSlack(false) } }} style={{ marginLeft: 8 }}>保存通知配置</Button></div>
    </Card>
  </div>
}
